"""Verify a JPGFLY local autonomy proof bundle offline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from launch_proof import verify_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a JPGFLY local autonomy proof bundle.")
    parser.add_argument("bundle", type=Path, help="Path to the exported .json proof bundle")
    args = parser.parse_args()

    try:
        payload = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"verified": False, "result": "FAIL", "errors": [str(exc)]}, indent=2))
        return 2

    result = verify_bundle(payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("verified") is True else 1


if __name__ == "__main__":
    sys.exit(main())
