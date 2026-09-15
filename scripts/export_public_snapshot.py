from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALWAYS_EXCLUDE_PREFIXES = (
    ".git/",
    ".jpgfly/",
    ".venv/",
    "venv/",
    "node_modules/",
    "artifacts/",
    "cache/",
    "deployments/",
    "public-release/",
)
ALWAYS_EXCLUDE_NAMES = {
    ".env",
    ".DS_Store",
}
PRIVATE_EXTENSIONS = {
    ".safetensors",
    ".pt",
    ".pth",
    ".ckpt",
    ".onnx",
    ".pem",
    ".key",
}


def tracked_files() -> list[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [item.decode("utf-8") for item in raw.split(b"\0") if item]


def allowed(path: str, include_training: bool) -> bool:
    normalized = path.replace("\\", "/")
    if normalized in ALWAYS_EXCLUDE_NAMES:
        return False
    if normalized.startswith(ALWAYS_EXCLUDE_PREFIXES):
        return False
    if Path(normalized).suffix.lower() in PRIVATE_EXTENSIONS:
        return False
    if not include_training:
        if normalized.startswith("training/"):
            return False
        if normalized == "scripts/install_flm_room_training.py":
            return False
    return True


def run(cmd: list[str], cwd: Path) -> None:
    subprocess.check_call(cmd, cwd=cwd)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a fresh-history JPGFLY snapshot suitable for a public repository."
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "public-release"),
        help="destination directory (default: ./public-release)",
    )
    parser.add_argument(
        "--include-training",
        action="store_true",
        help="include synthetic FLM training examples and training installer",
    )
    parser.add_argument(
        "--init-git",
        action="store_true",
        help="initialize the exported snapshot as a new Git repository with one fresh root commit",
    )
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    if output == ROOT or ROOT in output.parents and output.name in {".git", ".jpgfly"}:
        raise SystemExit("Refusing unsafe export destination.")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    copied = 0
    for rel in tracked_files():
        if not allowed(rel, args.include_training):
            continue
        source = ROOT / rel
        if not source.is_file():
            continue
        target = output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1

    # Never let a copied local env file or model checkpoint survive a future
    # change to tracked-file policy.
    for candidate in list(output.rglob("*")):
        if not candidate.is_file():
            continue
        rel = candidate.relative_to(output).as_posix()
        if candidate.name == ".env" or candidate.suffix.lower() in PRIVATE_EXTENSIONS:
            candidate.unlink()
        elif rel.startswith(".jpgfly/"):
            candidate.unlink()

    if args.init_git:
        run(["git", "init"], output)
        run(["git", "config", "user.name", "jpgfly"], output)
        run(["git", "config", "user.email", "jpgfly@localhost"], output)
        run(["git", "add", "."], output)
        run(["git", "commit", "-m", "Initial public release"], output)

    print("JPGFLY PUBLIC SNAPSHOT: OK")
    print(f"destination: {output}")
    print(f"files copied: {copied}")
    print(f"training included: {'yes' if args.include_training else 'no'}")
    print(f"fresh git history: {'yes' if args.init_git else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
