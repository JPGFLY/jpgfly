from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as jpgfly


def size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def archive_bytes(root: Path) -> int:
    return sum(
        size(path)
        for path in root.iterdir()
        if path.is_file() and not path.name.endswith(".tmp")
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate JPGFLY rooms to image + LLM text only storage."
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="copy legacy JSON manifests before compacting",
    )
    args = parser.parse_args()

    root = jpgfly.storage_root()
    root.mkdir(parents=True, exist_ok=True)
    backup = (
        root.parent
        / "storage-migration-backup"
        / datetime.now().strftime("%Y%m%d_%H%M%S")
    )

    before = archive_bytes(root)
    seen = compacted = skipped = failed = 0

    for path in sorted(root.glob("*.json")):
        seen += 1
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            schema = (record.get("storage") or {}).get("schema")
            if schema == 4:
                skipped += 1
                continue

            if args.backup:
                backup.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup / path.name)

            jpgfly.persist_artwork(record)
            compacted += 1
        except Exception as exc:
            failed += 1
            print(f"FAILED {path.name}: {exc}")

    removed_replays = 0
    removed_videos = 0

    for path in root.glob("*.replay.json.gz"):
        try:
            path.unlink()
            removed_replays += 1
        except OSError:
            pass

    for pattern in ("*.mp4", "*.webm", "*.mov"):
        for path in root.glob(pattern):
            try:
                path.unlink()
                removed_videos += 1
            except OSError:
                pass

    after = archive_bytes(root)
    stats = jpgfly.archive_storage_stats()

    print()
    print("JPGFLY image + text migration complete")
    print(f"records seen:          {seen}")
    print(f"compacted:             {compacted}")
    print(f"already image+text:    {skipped}")
    print(f"failed:                {failed}")
    print(f"replay files removed:  {removed_replays}")
    print(f"video files removed:   {removed_videos}")
    print(f"archive bytes before:  {before:,}")
    print(f"archive bytes after:   {after:,}")
    if before:
        print(f"after / before:        {after / before:.3f}")
    print(f"active archive mode:   {stats['mode']}")
    print(f"active archive bytes:  {stats['totalBytes']:,}")
    if args.backup:
        print(f"backup:                {backup}")


if __name__ == "__main__":
    main()
