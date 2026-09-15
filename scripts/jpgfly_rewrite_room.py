"""Rewrite the latest archived JPGFLY room text with the current FLM context.

The drawing, replay, and original provenance are preserved. A text revision record
keeps the previous displayed copy so the archive remains auditable.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flm_text_provider import configured_text_provider, generate_room_text


def data_root() -> Path:
    return Path(os.environ.get("JPGFLY_DATA_DIR", str(ROOT / ".jpgfly"))).expanduser().resolve()


def choose_record(session_id: str | None) -> Path:
    archive = data_root() / "artworks"
    files = list(archive.glob("*.json"))
    if not files:
        raise SystemExit(f"No archived rooms found in {archive}")
    if session_id:
        path = archive / f"{session_id}.json"
        if not path.is_file():
            raise SystemExit(f"Room not found: {session_id}")
        return path

    def completed(path: Path) -> str:
        try:
            return str(json.loads(path.read_text(encoding="utf-8")).get("completed_at") or "")
        except Exception:
            return ""

    return max(files, key=completed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", help="Rewrite one archived session; defaults to the latest room.")
    args = parser.parse_args()

    if configured_text_provider() != "flm":
        raise SystemExit("Set JPGFLY_TEXT_PROVIDER=flm before running this tool.")

    path = choose_record(args.session_id)
    record = json.loads(path.read_text(encoding="utf-8"))

    context = {
        "room_code": record.get("room_code"),
        "concept": record.get("concept"),
        "completion_reason": record.get("completion_reason"),
        "decision_count": record.get("decision_count"),
        "duration_ms": record.get("duration"),
        "thought_fragments": record.get("thought_fragments") or [],
        "public_commentary": record.get("public_commentary") or [],
        "structural_metrics": record.get("structural_metrics") or {},
        "previous_room_record": {
            "room_title": record.get("room_title"),
            "room_description": record.get("room_description"),
            "anomaly_report": record.get("anomaly_report"),
            "fly_statement": record.get("fly_statement"),
        },
    }

    seed = int(record.get("seed", 0) or 0)
    generated = generate_room_text(context, seed)
    if not generated:
        raise SystemExit("FLM did not return a room record.")

    revisions = list(record.get("text_revisions") or [])
    revisions.append(
        {
            "revised_at": datetime.now(timezone.utc).isoformat(),
            "previous": {
                "room_title": record.get("room_title"),
                "room_description": record.get("room_description"),
                "anomaly_report": record.get("anomaly_report"),
                "fly_statement": record.get("fly_statement"),
                "text_provider": record.get("text_provider"),
            },
        }
    )
    record["text_revisions"] = revisions[-8:]
    record.update(generated)
    record["text_provider"] = "FLM_REWRITE"

    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)

    print(f"Rewrote {record.get('room_code')} / {record.get('room_title')}")
    print(f"Archive file: {path}")
    print("Restart JPGFLY so its in-memory archive summary reloads the revised room text.")


if __name__ == "__main__":
    main()
