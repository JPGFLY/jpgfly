"""Small local CLI for JPGFLY long-term experience."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experience_memory import compact_experience, record_reading, sync_artwork_archive, sync_reading_folder


def add_reading(path: Path) -> None:
    paths = []
    if path.is_dir():
        paths = [p for p in sorted(path.iterdir()) if p.is_file() and p.suffix.casefold() in {".txt", ".md"}]
    elif path.is_file():
        paths = [path]
    else:
        raise SystemExit(f"Reading path not found: {path}")

    if not paths:
        raise SystemExit("No .txt or .md readings found.")

    for item in paths:
        text = item.read_text(encoding="utf-8")
        record_reading(text, source=str(item.resolve()), title=item.stem)
        print(f"learned reading: {item}")


def main() -> None:
    parser = argparse.ArgumentParser(description="JPGFLY long-term experience")
    sub = parser.add_subparsers(dest="command", required=True)

    read = sub.add_parser("read", help="learn from a .txt/.md file or folder")
    read.add_argument("path", type=Path)

    sub.add_parser("sync", help="sync completed rooms and .jpgfly/readings")
    sub.add_parser("status", help="show compact accumulated experience")

    args = parser.parse_args()
    if args.command == "read":
        add_reading(args.path)
    elif args.command == "sync":
        sync_artwork_archive()
        sync_reading_folder()
        print("experience synchronized")
    elif args.command == "status":
        print(json.dumps(compact_experience(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
