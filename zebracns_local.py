"""Local ZebraCNS service using real ZAPBench whole-brain activity traces.

The biological signal source is ZAPBench's public 2024-09-30 trace volume
(~71,721 neurons across 7,879 time points). JPGFLY does not claim that the
engineered game/action decoder is a biological motor readout: real activity is
sampled from the dataset, then mapped into bounded behavioral state variables
for the Escape Tank side experiment and for high-level Fly Brain modulation.

No synthetic neural activity is emitted. If the real dataset cannot be opened,
the service stays visibly dormant.
"""
from __future__ import annotations

import json
import math
import os
import random
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import FastAPI

app = FastAPI(title="JPGFLY ZebraCNS", docs_url=None, redoc_url=None)

DATASET = "ZAPBench 240930 whole-brain traces"
SOURCE = "gs://zapbench-release/volumes/20240930/traces/"
PUBLIC_HTTPS_SOURCE = "https://storage.googleapis.com/zapbench-release/volumes/20240930/traces/"
LICENSE = "CC-BY 4.0"
TOTAL_NEURONS = 71721
TOTAL_TIMESTEPS = 7879
TRACE_MIN = -0.25
TRACE_MAX = 1.5
SAMPLE_BLOCKS = 16
BLOCK_WIDTH = 64
VISIBLE_NODES = 256
TICK_SECONDS = max(0.15, float(os.environ.get("JPGFLY_ZEBRACNS_TICK_SECONDS", "0.50")))
CACHE_DIR = Path(os.environ.get(
    "JPGFLY_ZEBRACNS_CACHE_DIR",
    str(Path(__file__).resolve().parent / ".jpgfly" / "zebracns"),
)).expanduser()
CACHE_TRACES = CACHE_DIR / "zapbench_240930_sample.npy"
CACHE_META = CACHE_DIR / "zapbench_240930_sample.json"


def clamp(value: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    if not math.isfinite(value):
        value = 0.0
    return max(lo, min(hi, value))


def dist(a: list[float], b: list[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


class ZebraCNSRuntime:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.rng = random.Random(20240930)
        self.store = None
        self.trace_sample = None
        self.np = None
        self.activity_loaded = False
        self.last_error = ""
        self.frame = 0
        self.prev_sample = None
        self.sample_ids: list[int] = []
        self.fish = [0.42, 0.55]
        self.food = [0.80, 0.25]
        self.predator = [0.18, 0.74]
        self.score = 0
        self.episode = 0
        self.action = "NONE"
        self.signals = self._zero_signals()
        self.nodes: list[dict[str, Any]] = []
        self.started_at = time.time()
        self.last_update = 0.0
        self.retry_at = 0.0
        self.cache_path = str(CACHE_TRACES)
        self.cache_loaded = False

    @staticmethod
    def _zero_signals() -> dict[str, float]:
        return {
            "visual_salience": 0.0,
            "arousal": 0.0,
            "persistence": 0.0,
            "inhibition": 0.0,
            "exploration": 0.0,
            "motor_left": 0.0,
            "motor_right": 0.0,
            "novelty_seek": 0.0,
            "attention_lock": 0.0,
            "escape_drive": 0.0,
            "repetition_drive": 0.0,
            "state_instability": 0.0,
            "completion_pressure": 0.0,
            "tempo": 0.0,
        }

    def _spec(self) -> dict[str, Any]:
        # Use the public HTTPS object endpoint rather than gs:// so a normal
        # Windows machine does not need Google Cloud credentials.
        return {
            "driver": "zarr3",
            "kvstore": {
                "driver": "http",
                "base_url": PUBLIC_HTTPS_SOURCE,
            },
        }

    def _expected_sample_ids(self) -> list[int]:
        starts = [
            round(i * (TOTAL_NEURONS - BLOCK_WIDTH) / max(1, SAMPLE_BLOCKS - 1))
            for i in range(SAMPLE_BLOCKS)
        ]
        return [
            idx
            for start in starts
            for idx in range(int(start), int(start) + BLOCK_WIDTH)
        ]

    def _load_local_cache(self) -> bool:
        try:
            import numpy as np
            if not CACHE_TRACES.exists() or not CACHE_META.exists():
                return False
            meta=json.loads(CACHE_META.read_text(encoding="utf-8"))
            sample_ids=[int(v) for v in meta.get("sample_ids",[])]
            if sample_ids != self._expected_sample_ids():
                return False
            traces=np.load(CACHE_TRACES,allow_pickle=False)
            expected=(TOTAL_TIMESTEPS,len(sample_ids))
            if tuple(traces.shape) != expected:
                return False
            if str(traces.dtype) != "float32":
                traces=traces.astype(np.float32,copy=False)
            self.np=np
            self.store=None
            self.trace_sample=traces
            self.sample_ids=sample_ids
            self.activity_loaded=True
            self.cache_loaded=True
            self.retry_at=0.0
            self.last_error=""
            return True
        except Exception as exc:
            self.cache_loaded=False
            self.last_error=f"local cache load failed: {type(exc).__name__}: {exc}"[:300]
            return False

    def _save_local_cache(self) -> None:
        if self.trace_sample is None or self.np is None or not self.sample_ids:
            return
        CACHE_DIR.mkdir(parents=True,exist_ok=True)
        tmp_traces=CACHE_TRACES.with_suffix(".npy.tmp")
        tmp_meta=CACHE_META.with_suffix(".json.tmp")
        with tmp_traces.open("wb") as handle:
            self.np.save(handle,self.trace_sample,allow_pickle=False)
        meta={
            "dataset":DATASET,
            "source":SOURCE,
            "public_https_source":PUBLIC_HTTPS_SOURCE,
            "license":LICENSE,
            "total_neurons":TOTAL_NEURONS,
            "total_timesteps":TOTAL_TIMESTEPS,
            "sampled_neurons":len(self.sample_ids),
            "sample_ids":self.sample_ids,
            "dtype":"float32",
        }
        tmp_meta.write_text(json.dumps(meta,indent=2),encoding="utf-8")
        os.replace(tmp_traces,CACHE_TRACES)
        os.replace(tmp_meta,CACHE_META)
        self.cache_path=str(CACHE_TRACES)
        self.cache_loaded=True

    def _open_real_data(self) -> None:
        if self._load_local_cache():
            return
        try:
            import numpy as np
            import tensorstore as ts

            self.np = np
            self.store = ts.open(self._spec()).result()
            self.sample_ids = self._expected_sample_ids()
            starts = self.sample_ids[::BLOCK_WIDTH]
            # Cache a small distributed biological trace matrix once. This avoids
            # repeated cloud reads during the live game while keeping the sample
            # spread across the complete 71,721-neuron feature axis.
            pieces = []
            for start in starts:
                block = self.store[:, int(start):int(start) + BLOCK_WIDTH].read().result()
                pieces.append(np.asarray(block, dtype=np.float32))
            self.trace_sample = np.concatenate(pieces, axis=1)
            if self.trace_sample.shape != (TOTAL_TIMESTEPS, len(self.sample_ids)):
                raise RuntimeError(f"unexpected trace sample shape {self.trace_sample.shape}")
            self.activity_loaded = True
            self.retry_at = 0.0
            self.last_error = ""
            self._save_local_cache()
        except Exception as exc:
            self.store = None
            self.trace_sample = None
            self.np = None
            self.activity_loaded = False
            self.cache_loaded = False
            self.retry_at = time.monotonic() + 30.0
            self.last_error = f"{type(exc).__name__}: {exc}"[:300]

    def _read_sample(self, frame: int):
        if not self.activity_loaded or self.trace_sample is None or self.np is None:
            raise RuntimeError("real ZAPBench trace sample is not loaded")
        return self.trace_sample[int(frame)].copy()

    def _display_point(self, neuron_id: int) -> tuple[float, float]:
        # Display-only layout. This is intentionally not presented as anatomy.
        a = (neuron_id * 0.6180339887498949) % 1.0
        b = (neuron_id * 0.4142135623730950) % 1.0
        angle = math.tau * a
        radius = 0.12 + 0.34 * b
        x = 0.5 + math.cos(angle) * radius * 0.72
        y = 0.5 + math.sin(angle) * radius
        return clamp(x, 0.08, 0.92), clamp(y, 0.08, 0.92)

    def _decode(self, raw):
        np = self.np
        norm = np.clip((raw - TRACE_MIN) / (TRACE_MAX - TRACE_MIN), 0.0, 1.0)
        positive = np.clip(raw, 0.0, None)
        negative_fraction = float(np.mean(raw < 0.0))
        arousal = clamp(float(np.mean(positive)) / 0.36)
        visual = clamp(float(np.std(raw)) / 0.34)

        if self.prev_sample is None:
            persistence = 0.5
            delta = 0.0
        else:
            prev = self.prev_sample
            if float(np.std(raw)) > 1e-8 and float(np.std(prev)) > 1e-8:
                corr = float(np.corrcoef(raw, prev)[0, 1])
                if not math.isfinite(corr):
                    corr = 0.0
                persistence = clamp((corr + 1.0) * 0.5)
            else:
                persistence = 0.5
            delta = float(np.mean(np.abs(raw - prev)))
        exploration = clamp(delta / 0.22)
        inhibition = clamp(negative_fraction * 1.7)

        # Engineered population split over real sampled traces. These are not
        # claims about anatomical left/right motor populations.
        half = max(1, len(norm) // 2)
        left = clamp(float(np.mean(norm[:half])))
        right = clamp(float(np.mean(norm[half:])))

        novelty_seek = clamp(0.18 + exploration * 0.58 + visual * 0.24)
        attention_lock = clamp(persistence * (1.0 - exploration * 0.58))
        escape_drive = clamp(arousal * 0.42 + inhibition * 0.26 + exploration * 0.32)
        repetition_drive = clamp(persistence * 0.72 + (1.0 - exploration) * 0.28)
        instability = clamp(exploration * 0.72 + abs(left - right) * 0.28)
        completion_pressure = clamp(
            0.22 + persistence * 0.44 + inhibition * 0.18
            - novelty_seek * 0.30 - instability * 0.12
        )
        tempo = clamp(0.15 + arousal * 0.72 + exploration * 0.20)

        signals = {
            "visual_salience": visual,
            "arousal": arousal,
            "persistence": persistence,
            "inhibition": inhibition,
            "exploration": exploration,
            "motor_left": left,
            "motor_right": right,
            "novelty_seek": novelty_seek,
            "attention_lock": attention_lock,
            "escape_drive": escape_drive,
            "repetition_drive": repetition_drive,
            "state_instability": instability,
            "completion_pressure": completion_pressure,
            "tempo": tempo,
        }
        self.prev_sample = raw.copy()

        if inhibition > 0.76 and arousal < 0.36:
            action = "FREEZE"
        elif left - right > 0.075:
            action = "LEFT"
        elif right - left > 0.075:
            action = "RIGHT"
        else:
            action = "FORWARD"

        top_count = min(VISIBLE_NODES, len(norm))
        top = np.argsort(norm)[-top_count:][::-1]
        nodes = []
        for local_index in top:
            neuron_id = int(self.sample_ids[int(local_index)])
            x, y = self._display_point(neuron_id)
            nodes.append({
                "id": str(neuron_id),
                "x": round(x, 5),
                "y": round(y, 5),
                "activity": round(float(norm[int(local_index)]), 5),
                "region": "sampled whole-brain trace",
            })
        return signals, action, nodes

    def _update_game(self, action: str, signals: dict[str, float]) -> None:
        step = 0.010 + signals["tempo"] * 0.016
        if action == "LEFT":
            self.fish[0] -= step
        elif action == "RIGHT":
            self.fish[0] += step
        elif action == "FORWARD":
            dx = self.food[0] - self.fish[0]
            dy = self.food[1] - self.fish[1]
            mag = max(1e-6, math.hypot(dx, dy))
            self.fish[0] += dx / mag * step
            self.fish[1] += dy / mag * step
        elif action == "FREEZE":
            pass

        self.fish[0] = clamp(self.fish[0], 0.04, 0.96)
        self.fish[1] = clamp(self.fish[1], 0.06, 0.94)

        chase = 0.004 + signals["arousal"] * 0.006
        dx = self.fish[0] - self.predator[0]
        dy = self.fish[1] - self.predator[1]
        mag = max(1e-6, math.hypot(dx, dy))
        self.predator[0] = clamp(self.predator[0] + dx / mag * chase, 0.03, 0.97)
        self.predator[1] = clamp(self.predator[1] + dy / mag * chase, 0.04, 0.96)

        self.score += 1
        if dist(self.fish, self.food) < 0.07:
            self.score += 25
            self.food = [self.rng.uniform(0.10, 0.90), self.rng.uniform(0.12, 0.88)]

        if dist(self.fish, self.predator) < 0.065:
            self.episode += 1
            self.score = 0
            self.fish = [0.42, 0.55]
            self.predator = [0.18, 0.74]
            self.food = [self.rng.uniform(0.58, 0.90), self.rng.uniform(0.12, 0.88)]

    def step(self) -> None:
        with self.lock:
            if not self.activity_loaded:
                if time.monotonic() >= self.retry_at:
                    self._open_real_data()
                return
            try:
                raw = self._read_sample(self.frame)
                signals, action, nodes = self._decode(raw)
                self.signals = {k: round(clamp(v), 5) for k, v in signals.items()}
                self.action = action
                self.nodes = nodes
                self._update_game(action, self.signals)
                self.frame = (self.frame + 1) % TOTAL_TIMESTEPS
                self.last_update = time.time()
                self.last_error = ""
            except Exception as exc:
                self.activity_loaded = False
                self.store = None
                self.trace_sample = None
                self.retry_at = time.monotonic() + 30.0
                self.last_error = f"{type(exc).__name__}: {exc}"[:300]
                self.action = "NONE"
                self.signals = self._zero_signals()
                self.nodes = []

    def loop(self) -> None:
        while not self.stop_event.is_set():
            started = time.monotonic()
            self.step()
            elapsed = time.monotonic() - started
            self.stop_event.wait(max(0.03, TICK_SECONDS - elapsed))

    def start(self) -> None:
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.stop_event.clear()
            self.thread = threading.Thread(target=self.loop, name="jpgfly-zebracns", daemon=True)
            self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        thread = self.thread
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def reset_game(self) -> None:
        with self.lock:
            self.fish = [0.42, 0.55]
            self.food = [0.80, 0.25]
            self.predator = [0.18, 0.74]
            self.score = 0
            self.episode = 0

    def state(self) -> dict[str, Any]:
        with self.lock:
            loaded = bool(self.activity_loaded)
            note = (
                "Real ZAPBench whole-brain calcium traces drive the state. "
                "Behavior/game decoding and displayed node layout are engineered JPGFLY mappings, "
                "not anatomical motor labels or a consciousness claim."
                if loaded else
                "No biological activity is being emitted because the real ZAPBench trace store is unavailable."
            )
            return {
                "status": "RUNNING_REAL_ACTIVITY" if loaded else "WAITING_FOR_REAL_ACTIVITY",
                "dataset": DATASET if loaded else "NONE",
                "source": SOURCE,
                "public_https_source": PUBLIC_HTTPS_SOURCE,
                "license": LICENSE,
                "activity_loaded": loaded,
                "biological_data_loaded": loaded,
                "connectome_loaded": False,
                "frame": int(self.frame),
                "total_timesteps": TOTAL_TIMESTEPS,
                "sampled_neurons": len(self.sample_ids) if loaded else 0,
                "visible_nodes": len(self.nodes) if loaded else 0,
                "total_neurons": TOTAL_NEURONS,
                "cache_loaded": bool(self.cache_loaded),
                "cache_path": self.cache_path,
                "action": self.action if loaded else "NONE",
                "signals": deepcopy(self.signals) if loaded else self._zero_signals(),
                "game": {
                    "name": "ESCAPE TANK",
                    "fish": [round(v, 5) for v in self.fish],
                    "food": [round(v, 5) for v in self.food],
                    "predator": [round(v, 5) for v in self.predator],
                    "score": int(self.score),
                    "episode": int(self.episode),
                },
                "nodes": deepcopy(self.nodes) if loaded else [],
                "last_update": self.last_update,
                "last_error": self.last_error,
                "note": note,
            }


RUNTIME = ZebraCNSRuntime()


@app.on_event("startup")
def _startup() -> None:
    RUNTIME.start()


@app.on_event("shutdown")
def _shutdown() -> None:
    RUNTIME.stop()


@app.get("/state")
def state():
    return RUNTIME.state()


@app.get("/health")
def health():
    value = RUNTIME.state()
    return {
        "ok": True,
        "system": "ZebraCNS",
        "mode": "ZAPBENCH_ACTIVITY",
        "dataset": value["dataset"],
        "activity_loaded": value["activity_loaded"],
        "biological_data_loaded": value["biological_data_loaded"],
        "connectome_loaded": False,
        "sampled_neurons": value["sampled_neurons"],
        "visible_nodes": value.get("visible_nodes",0),
        "total_neurons": TOTAL_NEURONS,
        "cache_loaded": value["cache_loaded"],
        "cache_path": value["cache_path"],
        "source": SOURCE,
        "public_https_source": PUBLIC_HTTPS_SOURCE,
        "license": LICENSE,
        "last_error": value["last_error"],
    }


@app.post("/step")
def step():
    RUNTIME.step()
    return RUNTIME.state()


@app.post("/reset")
def reset():
    RUNTIME.reset_game()
    return RUNTIME.state()
