"""Persistent experience for JPGFLY.

This is deliberately a slow-learning layer. Completed rooms build visual habits;
readings build conceptual memory. It does not rewrite model weights and it never
stores private chain-of-thought.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
SCHEMA_VERSION = 1
ROOM_LAUNCH_ID = "20260913-0218"
ROOT = Path(__file__).resolve().parent

TOPIC_TERMS = {
    "art": ("art", "artist", "painting", "painter", "drawing", "sculpture", "canvas", "museum", "aesthetic", "aesthetics"),
    "poetry": ("poetry", "poem", "poet", "verse", "metaphor", "lyric"),
    "philosophy": ("philosophy", "philosopher", "existence", "existential", "meaning", "identity", "self", "freedom", "consciousness", "absurdism", "nihilism", "ethics", "ontology", "epistemology", "aesthetics"),
    "desire_body": ("desire", "sex", "sexual", "erotic", "eroticism", "lust", "body", "bodies", "flesh", "skin", "intimacy", "attraction", "naked", "nude"),
    "life_death": ("life", "death", "mortality", "dead", "funeral", "birth", "decay"),
    "money_value": ("money", "coin", "coins", "value", "price", "scarcity", "greed", "wealth", "market"),
    "crypto": ("bitcoin", "crypto", "cryptocurrency", "cryptocurrencies", "memecoin", "memecoins", "speculation"),
    "crypto_terminal": ("terminal", "shell", "cli", "command", "command-line", "address", "addresses", "hash", "hashes", "block", "blocks", "transaction", "transactions", "tx", "nonce", "gas", "rpc", "mempool", "contract", "contracts", "chain", "onchain", "sign", "signature", "burn", "swap"),
    "luck_risk": ("luck", "risk", "gamble", "chance", "fortune", "bet"),
    "dreams_memory": ("dream", "dreams", "memory", "memories", "remember"),
    "humor_absurdity": ("humor", "joke", "jokes", "funny", "absurd", "absurdity", "satire", "sarcasm", "deadpan", "punchline", "ridiculous"),
    "insects": ("fly", "flies", "insect", "insects", "moth", "beetle", "spider"),
}


# Readings never become literal drawing instructions. Their topic memory is
# compressed into low-strength abstract pressures that can bias composition
# (return, rupture, void, system, organic rhythm, etc.) without asking the fly
# to illustrate the source text.
TOPIC_PRESSURES = {
    "art": ("STRUCTURE", "REVISION"),
    "poetry": ("RHYTHM", "ECHO"),
    "philosophy": ("VOID", "TENSION"),
    "desire_body": ("ORGANIC", "FIGURE_FIELD"),
    "life_death": ("EROSION", "RETURN"),
    "money_value": ("SYSTEM", "SCARCITY"),
    "crypto": ("SYSTEM", "NOISE"),
    "crypto_terminal": ("SYSTEM", "NETWORK"),
    "luck_risk": ("CHANCE", "RUPTURE"),
    "dreams_memory": ("RETURN", "ECHO"),
    "humor_absurdity": ("ABSURD", "RUPTURE"),
    "insects": ("NETWORK", "ORGANIC"),
}

def _data_root() -> Path:
    configured = os.environ.get("JPGFLY_DATA_DIR", "").strip() or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    return Path(configured).expanduser().resolve() if configured else (ROOT / ".jpgfly").resolve()

def memory_path() -> Path:
    return _data_root() / "experience.json"

def _empty() -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "rooms_seen": 0,
        "readings_seen": 0,
        "learned_rooms": [],
        "reading_hashes": [],
        "visual": {
            "motifs": {},
            "palettes": {},
            "composition_modes": {},
            "goals": {},
            "subject_programs": {},
            "techniques": {},
            "brushes": {},
        },
        "topics": {},
        "topic_passages": {},
        "reading_sources": [],
        "recent_reading_notes": [],
        "recent_rooms": [],
        "room_launch_id": ROOM_LAUNCH_ID,
        "updated_at": None,
    }

def load_experience() -> dict[str, Any]:
    path = memory_path()
    with _LOCK:
        if not path.is_file():
            return _empty()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return _empty()
        if not isinstance(data, dict) or data.get("schema") != SCHEMA_VERSION:
            return _empty()
        base = _empty()
        base.update(data)
        base["visual"] = {**_empty()["visual"], **(data.get("visual") or {})}
        base["learned_rooms"] = list(data.get("learned_rooms") or [])
        base["reading_hashes"] = list(data.get("reading_hashes") or [])
        base["topic_passages"] = dict(data.get("topic_passages") or {})
        if data.get("room_launch_id") != ROOM_LAUNCH_ID:
            base["rooms_seen"] = 0
            base["learned_rooms"] = []
            base["visual"] = _empty()["visual"]
            base["recent_rooms"] = []
            base["room_launch_id"] = ROOM_LAUNCH_ID
        return base

def _save(data: dict[str, Any]) -> dict[str, Any]:
    path = memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["schema"] = SCHEMA_VERSION
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)
    return data

def _bump(table: dict[str, int], key: Any, amount: int = 1) -> None:
    value = str(key or "").strip()
    if not value or value in {"NONE", "none", "None"}:
        return
    table[value] = int(table.get(value, 0) or 0) + int(amount)

def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_$-]+", str(text or "").casefold())


def _source_label(value: Any) -> str:
    raw = str(value or "reading").strip()
    if not raw:
        return "reading"
    try:
        name = Path(raw).name
    except (TypeError, ValueError):
        name = raw
    return (name or "reading")[:160]

def _topic_counts(text: str) -> Counter:
    words = _words(text)
    bag = Counter(words)
    result = Counter()
    for topic, terms in TOPIC_TERMS.items():
        score = sum(bag[t.casefold()] for t in terms)
        if score:
            result[topic] = score
    return result

def _representative_passage(text: str, topic: str) -> str:
    terms = tuple(term.casefold() for term in TOPIC_TERMS.get(topic, ()))
    chunks = re.split(r"(?<=[.!?])\\s+|\\n+", text)
    for chunk in chunks:
        candidate = " ".join(chunk.split()).strip()
        folded = candidate.casefold()
        if 40 <= len(candidate) and any(re.search(r"(?<!\\w)" + re.escape(term) + r"(?!\\w)", folded) for term in terms):
            return candidate[:320]
    return " ".join(text.split())[:320]


def record_reading(text: str, *, source: str = "reading", title: str = "", document_hash: str = "") -> dict[str, Any]:
    clean = " ".join(str(text or "").split())
    if not clean:
        raise ValueError("reading text is empty")
    if len(clean) > 200_000:
        raise ValueError("reading text is too large")

    topics = _topic_counts(clean)
    content_hash = document_hash or hashlib.sha256(clean.encode("utf-8")).hexdigest()
    with _LOCK:
        data = load_experience()
        if content_hash in set(data.get("reading_hashes") or []):
            return data
        data["reading_hashes"] = (data.get("reading_hashes") or [])[-1023:] + [content_hash]
        data["readings_seen"] = int(data.get("readings_seen", 0) or 0) + 1
        for topic, count in topics.items():
            _bump(data["topics"], topic, count)
            passage = _representative_passage(clean, topic)
            if passage:
                existing = list((data.get("topic_passages") or {}).get(topic) or [])
                if passage not in existing:
                    existing = existing[-3:] + [passage]
                data.setdefault("topic_passages", {})[topic] = existing

        source_entry = {
            "source": _source_label(source),
            "title": str(title or "")[:240],
            "topics": dict(topics),
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        data["reading_sources"] = (data.get("reading_sources") or [])[-63:] + [source_entry]

        note = {
            "source": source_entry["source"],
            "title": source_entry["title"],
            "topics": list(topics.most_common(6)),
            "excerpt": clean[:800],
        }
        data["recent_reading_notes"] = (data.get("recent_reading_notes") or [])[-23:] + [note]
        return _save(data)

def _actions_from_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    # During finalization the authoritative history is still available at the
    # top level. Legacy archives may instead carry it inside provenance.
    provenance = record.get("provenance") or {}
    history = record.get("brain_decisions") or provenance.get("completeFlyActionHistory") or []
    actions = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        action = entry.get("action") if isinstance(entry.get("action"), dict) else entry
        if action.get("intent") == "MOVE":
            actions.append(action)
    return actions

def record_room_experience(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("launch_eligible") is False:
        return load_experience()
    room_code = str(record.get("room_code") or "")
    actions = _actions_from_record(record)

    with _LOCK:
        data = load_experience()
        # Idempotence: do not learn twice from the same room.
        room_key = str(record.get("session_id") or room_code or "")
        known = set(data.get("learned_rooms") or [])
        if room_key and room_key in known:
            return data
        if room_key:
            data["learned_rooms"] = (data.get("learned_rooms") or [])[-4095:] + [room_key]

        data["rooms_seen"] = int(data.get("rooms_seen", 0) or 0) + 1
        visual = data["visual"]

        fields = (
            ("motifs", "motifHint"),
            ("palettes", "paletteName"),
            ("composition_modes", "compositionMode"),
            ("goals", "autonomyGoal"),
            ("subject_programs", "subjectProgram"),
            ("techniques", "technique"),
            ("brushes", "brushTool"),
        )
        for memory_key, action_key in fields:
            counts = Counter(
                str(action.get(action_key) or "")
                for action in actions
                if action.get(action_key) not in (None, "", "NONE", "none")
            )
            for value, count in counts.items():
                # A long room may repeat a motif hundreds of times; cap its vote
                # so learning reflects history across rooms instead of one session.
                _bump(visual[memory_key], value, 1 + min(3, int(math.log1p(count))))

        # Compact room manifests intentionally discard the full action history.
        # Keep enough signature data in visual_context/structural_metrics so the
        # experience file can still be rebuilt after a restore or corruption.
        if not actions:
            metrics = record.get("structural_metrics") or {}
            context = record.get("visual_context") or {}
            compact_fields = (
                ("palettes", context.get("palette_name")),
                ("composition_modes", context.get("composition_mode")),
                ("goals", context.get("current_goal")),
                ("subject_programs", context.get("subject_program")),
            )
            for memory_key, value in compact_fields:
                _bump(visual[memory_key], value, 1)

            for memory_key, table in (
                ("brushes", metrics.get("brushCounts") or context.get("brush_counts") or {}),
                ("techniques", metrics.get("techniqueCounts") or context.get("technique_counts") or {}),
            ):
                for value, count in table.items():
                    try:
                        vote = 1 + min(3, int(math.log1p(max(0, int(count or 0)))))
                    except (TypeError, ValueError):
                        vote = 1
                    _bump(visual[memory_key], value, vote)

        lore = " ".join(
            str(record.get(key) or "")
            for key in ("room_title", "room_description", "memory_thread", "anomaly_report", "fly_statement", "concept")
        )
        for topic, count in _topic_counts(lore).items():
            # Room lore counts lightly so readings remain the main conceptual source.
            _bump(data["topics"], topic, max(1, math.ceil(count * 0.35)))

        metrics = record.get("structural_metrics") or {}
        context = record.get("visual_context") or {}
        def compact_pairs(action_key: str, metric_key: str, context_key: str, limit: int):
            if actions:
                return Counter(a.get(action_key) for a in actions if a.get(action_key) not in (None, "", "NONE")).most_common(limit)
            table = metrics.get(metric_key) or context.get(context_key) or {}
            if isinstance(table, dict):
                return Counter({str(k): int(v or 0) for k, v in table.items() if k}).most_common(limit)
            return []

        room_note = {
            "room_code": room_code,
            "room_title": record.get("room_title"),
            "agent_profile": str(record.get("agent_profile") or "jpgfly"),
            "agent_name": str(record.get("agent_name") or "JPGFLY"),
            "spawned_from": record.get("spawned_from"),
            "motifs": Counter(a.get("motifHint") for a in actions if a.get("motifHint") not in (None, "NONE")).most_common(6),
            "palette": Counter(a.get("paletteName") for a in actions if a.get("paletteName")).most_common(2) if actions else ([(context.get("palette_name"), 1)] if context.get("palette_name") else []),
            "composition": Counter(a.get("compositionMode") for a in actions if a.get("compositionMode")).most_common(2) if actions else ([(context.get("composition_mode"), 1)] if context.get("composition_mode") else []),
            "styles": compact_pairs("movementStyle", "familyCounts", "style_counts", 6),
            "brushes": compact_pairs("brushTool", "brushCounts", "brush_counts", 4),
            "techniques": compact_pairs("technique", "techniqueCounts", "technique_counts", 4),
            "decision_modes": compact_pairs("decisionMode", "decisionModeCounts", "decision_mode_counts", 5),
            "context_passes": compact_pairs("contextPass", "contextPassCounts", "context_pass_counts", 5),
            "room_tension": Counter(a.get("roomTension") for a in actions if a.get("roomTension")).most_common(2) if actions else ([(context.get("room_tension"), 1)] if context.get("room_tension") else []),
            "subject_program": context.get("subject_program"),
            "archetype": context.get("archetype"),
            "spatial_program": context.get("spatial_program"),
            "stroke_dialect": context.get("stroke_dialect"),
            "duration_profile": context.get("duration_profile"),
            "tempo_mode": context.get("tempo_mode"),
            "content_register": context.get("content_register"),
            "artistic_temperament": context.get("artistic_temperament"),
            "art_policy": context.get("art_policy"),
            "topics": list(_topic_counts(lore).most_common(6)),
            "completed_at": record.get("completed_at"),
        }
        data["recent_rooms"] = (data.get("recent_rooms") or [])[-63:] + [room_note]
        return _save(data)

def sync_artwork_archive() -> dict[str, Any]:
    directory = _data_root() / "artworks"
    if not directory.is_dir():
        return load_experience()
    records = []
    for path in directory.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(record, dict):
                records.append(record)
        except (OSError, ValueError):
            continue
    records.sort(key=lambda r: r.get("completed_at", "") or "")
    data = load_experience()
    known = set(data.get("learned_rooms") or [])
    for record in records:
        key = str(record.get("session_id") or record.get("room_code") or "")
        if key and key not in known:
            data = record_room_experience(record)
            known.add(key)
    return data


def sync_reading_folder() -> dict[str, Any]:
    directory = _data_root() / "readings"
    directory.mkdir(parents=True, exist_ok=True)
    data = load_experience()
    known = set(data.get("reading_hashes") or [])
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.casefold() not in {".txt", ".md"}:
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if digest in known:
            continue
        data = record_reading(raw, source=str(path), title=path.stem, document_hash=digest)
        known.add(digest)
    return data


def bootstrap_rooms(records: list[dict[str, Any]]) -> dict[str, Any]:
    data = load_experience()
    if int(data.get("rooms_seen", 0) or 0) > 0:
        return data
    ordered = sorted(
        (r for r in records if isinstance(r, dict)),
        key=lambda r: r.get("completed_at", "") or "",
    )
    for record in ordered:
        data = record_room_experience(record)
    return data

def _normalized_top(table: dict[str, Any], limit: int = 8) -> dict[str, float]:
    counts = [(str(k), max(0, int(v or 0))) for k, v in (table or {}).items()]
    counts = [(k, v) for k, v in counts if v > 0]
    counts.sort(key=lambda item: (-item[1], item[0]))
    counts = counts[:limit]
    total = sum(v for _, v in counts) or 1
    return {k: round(v / total, 4) for k, v in counts}

def _conceptual_pressures(topics: dict[str, Any]) -> dict[str, float]:
    raw = Counter()
    for topic, count in (topics or {}).items():
        try:
            weight = max(0.0, float(count or 0))
        except (TypeError, ValueError):
            continue
        for pressure in TOPIC_PRESSURES.get(str(topic), ()):
            raw[pressure] += weight
    total = sum(raw.values()) or 1.0
    return {key: round(value / total, 4) for key, value in raw.most_common(10)}

def visual_bias() -> dict[str, Any]:
    # Keep both forms of memory current. Visual habits come from finished rooms;
    # reading memory contributes only abstract compositional pressure.
    data = sync_artwork_archive()
    data = sync_reading_folder()
    rooms = int(data.get("rooms_seen", 0) or 0)
    readings = int(data.get("readings_seen", 0) or 0)
    # Learning grows slowly and caps below 0.4 so novelty always remains dominant.
    strength = min(0.38, 0.04 + math.log1p(rooms) * 0.055) if rooms else 0.0
    conceptual_strength = min(0.22, 0.025 + math.log1p(readings) * 0.035) if readings else 0.0
    visual = data.get("visual") or {}
    recent = []
    for item in (data.get("recent_rooms") or [])[-8:]:
        recent.append({
            "room_code": item.get("room_code"),
            "agent_profile": item.get("agent_profile") or "jpgfly",
            "agent_name": item.get("agent_name") or "JPGFLY",
            "spawned_from": item.get("spawned_from"),
            "palette": (item.get("palette") or [])[:2],
            "composition": (item.get("composition") or [])[:2],
            "styles": (item.get("styles") or [])[:5],
            "brushes": (item.get("brushes") or [])[:3],
            "techniques": (item.get("techniques") or [])[:3],
            "decision_modes": (item.get("decision_modes") or [])[:4],
            "context_passes": (item.get("context_passes") or [])[:4],
            "room_tension": (item.get("room_tension") or [])[:2],
            "subject_program": item.get("subject_program"),
            "archetype": item.get("archetype"),
            "spatial_program": item.get("spatial_program"),
            "stroke_dialect": item.get("stroke_dialect"),
            "duration_profile": item.get("duration_profile"),
            "tempo_mode": item.get("tempo_mode"),
            "content_register": item.get("content_register"),
            "artistic_temperament": item.get("artistic_temperament"),
        })
    return {
        "rooms_seen": rooms,
        "readings_seen": readings,
        "strength": round(strength, 4),
        "conceptual_strength": round(conceptual_strength, 4),
        "conceptual_pressures": _conceptual_pressures(data.get("topics") or {}),
        "motifs": _normalized_top(visual.get("motifs") or {}, 12),
        "palettes": _normalized_top(visual.get("palettes") or {}, 8),
        "composition_modes": _normalized_top(visual.get("composition_modes") or {}, 8),
        "goals": _normalized_top(visual.get("goals") or {}, 7),
        "subject_programs": _normalized_top(visual.get("subject_programs") or {}, 6),
        "techniques": _normalized_top(visual.get("techniques") or {}, 8),
        "brushes": _normalized_top(visual.get("brushes") or {}, 8),
        "recent_rooms": recent,
    }

def compact_experience() -> dict[str, Any]:
    sync_artwork_archive()
    sync_reading_folder()
    data = load_experience()
    readings = []
    for item in (data.get("recent_reading_notes") or [])[-4:]:
        readings.append({
            "title": item.get("title"),
            "topics": (item.get("topics") or [])[:6],
            "excerpt": str(item.get("excerpt") or "")[:320],
        })
    topics = _normalized_top(data.get("topics") or {}, 10)
    topic_memory = {}
    for topic in list(topics)[:6]:
        passages = (data.get("topic_passages") or {}).get(topic) or []
        if passages:
            topic_memory[topic] = str(passages[-1])[:260]
    return {
        "rooms_seen": int(data.get("rooms_seen", 0) or 0),
        "readings_seen": int(data.get("readings_seen", 0) or 0),
        "topics": topics,
        "topic_memory": topic_memory,
        "visual_bias": visual_bias(),
        "recent_readings": readings[-2:],
        "updated_at": data.get("updated_at"),
    }
