from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check JPGFLY deployment readiness.")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    problems: list[str] = []
    for name in ("Dockerfile", ".dockerignore", "requirements.txt", "app.py"):
        if not (ROOT / name).is_file():
            problems.append(f"missing {name}")

    # Public-release hygiene: current tracked files must not contain local
    # workstation identities or obvious credential material.
    try:
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    except (OSError, subprocess.CalledProcessError):
        tracked = []

    source_patterns = {
        "Windows user home": re.compile(r"C:\\Users\\(?!path\\)[^\\\s\"']+", re.I),
        "Unix user home": re.compile(r"/home/(?!user(?:/|$)|runner(?:/|$))[^/\s\"']+"),
        "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
        "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    }

    for raw in tracked:
        if not raw:
            continue
        path = ROOT / raw.decode("utf-8", "replace")
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in source_patterns.items():
            if pattern.search(content):
                problems.append(f"{label} found in tracked file: {path.relative_to(ROOT)}")

    if not args.source_only:
        public = enabled("JPGFLY_PUBLIC_DEPLOYMENT") or bool(os.environ.get("RAILWAY_ENVIRONMENT", "").strip())
        if public:
            if len(os.environ.get("JPGFLY_CONTROL_TOKEN", "").strip()) < 32:
                problems.append("JPGFLY_CONTROL_TOKEN must be at least 32 characters")

            if os.environ.get("RAILWAY_ENVIRONMENT") and not os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") and not enabled("JPGFLY_ALLOW_EPHEMERAL_STORAGE"):
                problems.append("attach a Railway Volume before production deployment")

            provider = os.environ.get("JPGFLY_TEXT_PROVIDER", "procedural").strip().lower()
            if provider in {"flm", "hybrid"}:
                url = os.environ.get("JPGFLY_FLM_URL", "").strip()
                if not url:
                    problems.append(f"JPGFLY_TEXT_PROVIDER={provider} requires JPGFLY_FLM_URL")
                elif os.environ.get("RAILWAY_ENVIRONMENT") and any(host in url.casefold() for host in ("127.0.0.1", "localhost", "[::1]")):
                    problems.append("Railway cannot reach the local WSL FLM bridge")
                elif not any(host in url.casefold() for host in ("127.0.0.1", "localhost", "[::1]")) and len(os.environ.get("JPGFLY_FLM_AUTH_TOKEN", "").strip()) < 32:
                    problems.append("remote FLM requires JPGFLY_FLM_AUTH_TOKEN of at least 32 characters")

            if provider in {"ollama", "hybrid"}:
                url = os.environ.get("JPGFLY_OLLAMA_URL", "").strip()
                if not url:
                    problems.append(f"JPGFLY_TEXT_PROVIDER={provider} requires JPGFLY_OLLAMA_URL")
                elif os.environ.get("RAILWAY_ENVIRONMENT") and any(host in url.casefold() for host in ("127.0.0.1", "localhost", "[::1]")):
                    problems.append("Railway cannot reach a local Ollama URL")

        data = os.environ.get("JPGFLY_DATA_DIR", "").strip() or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
        if data:
            archive = Path(data).expanduser() / "artworks"
            if archive.is_dir():
                for pattern in ("*.replay.json.gz", "*.mp4", "*.webm", "*.mov"):
                    count = sum(1 for _ in archive.glob(pattern))
                    if count:
                        problems.append(f"archive contains {count} forbidden {pattern} file(s)")

    if problems:
        print("JPGFLY PREDEPLOY: FAILED")
        for item in problems:
            print(f" - {item}")
        return 1

    print("JPGFLY PREDEPLOY: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
