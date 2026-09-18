"""Localhost-only FLM bridge for JPGFLY.

Run this file with the nftechie/flm virtualenv inside WSL. It keeps the trained
FLM model warm and exposes only a tiny local HTTP generation API to the native
Windows JPGFLY server.
"""
from __future__ import annotations

import ipaddress
import json
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_MODEL = None
_MODEL_KEY = None
_MODEL_LOCK = threading.Lock()
_GENERATE_LOCK = threading.Lock()

HOST = os.environ.get("JPGFLY_FLM_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = int(os.environ.get("JPGFLY_FLM_BRIDGE_PORT", "4680"))
ALLOW_REMOTE = os.environ.get("JPGFLY_FLM_BRIDGE_ALLOW_REMOTE", "").strip().lower() == "true"
AUTH_TOKEN = os.environ.get("JPGFLY_FLM_AUTH_TOKEN", "").strip()
MAX_BODY = 64 * 1024
MAX_PROMPT = 20000
MAX_TOKENS = 512


def _complete_run(path: Path) -> bool:
    return (path / "adapter.safetensors").is_file() and (path / "run.json").is_file()


def _paths() -> tuple[Path, Path, Path]:
    root = Path(os.environ.get("JPGFLY_FLM_ROOT", "~/flm")).expanduser().resolve()

    if not (root / "flm" / "model.py").is_file():
        raise RuntimeError(f"FLM root is invalid: {root}")

    requested = os.environ.get("JPGFLY_FLM_RUN", "").strip()
    candidates = []
    if requested:
        candidates.append(Path(requested).expanduser().resolve())
    candidates.extend([
        (root / "runs" / "jpgfly-room-v2").resolve(),
        (root / "runs" / "jpgfly-style-v1").resolve(),
    ])

    seen = set()
    checked = []
    for run in candidates:
        key = str(run)
        if key in seen:
            continue
        seen.add(key)
        checkpoint = run / "adapter.safetensors"
        manifest = run / "run.json"
        checked.append(
            f"{run} [adapter={'yes' if checkpoint.is_file() else 'no'}, run.json={'yes' if manifest.is_file() else 'no'}]"
        )
        if checkpoint.is_file() and manifest.is_file():
            if requested and run != Path(requested).expanduser().resolve():
                print(f"Requested FLM run is incomplete; falling back to {run}", flush=True)
            return root, run, checkpoint

    raise RuntimeError("No completed JPGFLY FLM run found. Checked: " + "; ".join(checked))


def _model():
    global _MODEL, _MODEL_KEY
    root, run, checkpoint = _paths()
    device = os.environ.get("JPGFLY_FLM_DEVICE", "cuda").strip().lower() or "cuda"
    key = (str(root), str(run), device)

    with _MODEL_LOCK:
        if _MODEL is not None and _MODEL_KEY == key:
            return _MODEL
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from flm.model import FLM

        print(f"Loading FLM from {run} on {device} ...", flush=True)
        model = FLM(device=device, checkpoint=checkpoint, profile="conversation")
        if not model.trained:
            raise RuntimeError("FLM conversational adapter is not trained")
        _MODEL = model
        _MODEL_KEY = key
        print("FLM bridge model ready.", flush=True)
        return model


def _generate(prompt: str, seed: int, max_tokens: int) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt is required")
    prompt = prompt.strip()
    if len(prompt) > MAX_PROMPT:
        raise ValueError("prompt too large")

    max_tokens = max(1, min(MAX_TOKENS, int(max_tokens)))
    seed = int(seed) & 0x7FFFFFFF
    model = _model()

    text = ""
    with _GENERATE_LOCK:
        for event in model.generate(
            [{"role": "user", "content": prompt}],
            mode="intact",
            max_tokens=max_tokens,
            seed=seed,
            telemetry=False,
        ):
            if event.get("type") in {"token", "done"}:
                text = event.get("text", text)
    return " ".join(str(text or "").split()).strip()


def _is_loopback_address(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return value == "localhost"


class Handler(BaseHTTPRequestHandler):
    server_version = "JPGFLY-FLM-Bridge/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[flm-bridge] {self.address_string()} {fmt % args}", flush=True)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _local_only(self) -> bool:
        if ALLOW_REMOTE or _is_loopback_address(self.client_address[0]):
            return True
        self._json(403, {"error": "remote FLM bridge access is disabled"})
        return False

    def _authorized(self) -> bool:
        # Local-only development remains frictionless. Any bridge deliberately
        # opened beyond loopback requires the shared Bearer token.
        if _is_loopback_address(self.client_address[0]) and not ALLOW_REMOTE:
            return True
        if not AUTH_TOKEN:
            self._json(401, {"error": "FLM bridge authorization required"})
            return False
        supplied=self.headers.get("Authorization","")
        expected="Bearer "+AUTH_TOKEN
        if secrets.compare_digest(supplied,expected):
            return True
        self._json(401, {"error": "FLM bridge authorization required"})
        return False

    def do_GET(self) -> None:
        if not self._local_only() or not self._authorized():
            return
        if self.path != "/health":
            self._json(404, {"error": "not found"})
            return
        try:
            root, run, _ = _paths()
            loaded = _MODEL is not None
            self._json(
                200,
                {
                    "ok": True,
                    "provider": "FLM",
                    "loaded": loaded,
                    "run": run.name,
                },
            )
        except Exception as exc:
            self._json(503, {"ok": False, "error": str(exc)[:500]})

    def do_POST(self) -> None:
        if not self._local_only() or not self._authorized():
            return
        if self.path != "/generate":
            self._json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "invalid content length"})
            return

        if length <= 0 or length > MAX_BODY:
            self._json(413, {"error": "request body too large"})
            return

        try:
            data = json.loads(self.rfile.read(length))
            prompt = data.get("prompt", "")
            seed = data.get("seed", 0)
            max_tokens = data.get("max_tokens", 180)
            text = _generate(prompt, seed, max_tokens)
            self._json(200, {"text": text, "provider": "FLM"})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)[:500]})
        except Exception as exc:
            self._json(500, {"error": str(exc)[:500]})


def main() -> None:
    if not ALLOW_REMOTE and HOST not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError("FLM bridge must bind to loopback unless JPGFLY_FLM_BRIDGE_ALLOW_REMOTE=true")
    if ALLOW_REMOTE and len(AUTH_TOKEN) < 32:
        raise RuntimeError("Remote FLM bridge requires JPGFLY_FLM_AUTH_TOKEN with at least 32 characters")
    # Fail fast and eagerly load the trained model before opening the health port.
    # A healthy bridge now always means the FLM model is actually resident and ready.
    root, run, _ = _paths()
    print(f"JPGFLY FLM bridge preparing: http://{HOST}:{PORT}", flush=True)
    print(f"FLM root: {root}", flush=True)
    print(f"FLM run:  {run}", flush=True)
    print("Eager-loading trained FLM model before serving...", flush=True)
    _model()
    print("JPGFLY FLM bridge READY / model loaded.", flush=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
