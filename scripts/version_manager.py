#!/usr/bin/env python3
"""Atomic version manager for fraiseql-seed monorepo.

Keeps version.json, and both packages' pyproject.toml files in sync.

Usage:
    python3 scripts/version_manager.py show
    python3 scripts/version_manager.py patch [--dry-run]
    python3 scripts/version_manager.py minor [--dry-run]
    python3 scripts/version_manager.py major [--dry-run]
"""

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

MIN_ARGS = 2

ROOT = Path(__file__).resolve().parent.parent
VERSION_JSON = ROOT / "version.json"
PYPROJECT_FILES = [
    ROOT / "pyproject.toml",
    ROOT / "packages" / "fraiseql-uuid" / "pyproject.toml",
    ROOT / "packages" / "fraiseql-data" / "pyproject.toml",
]


def current_version() -> str:
    data = json.loads(VERSION_JSON.read_text())
    return data["version"]


def bump(version: str, part: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"Unknown bump part: {part}")
    return f"{major}.{minor}.{patch}"


def git_short_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def git_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def write_version_json(version: str) -> None:
    data = {
        "version": version,
        "commit": git_short_sha(),
        "branch": git_branch(),
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    VERSION_JSON.write_text(json.dumps(data, indent=2) + "\n")


def write_native_versions(version: str) -> None:
    """Update version = "..." in all pyproject.toml files."""
    pattern = re.compile(r'^(version\s*=\s*")[^"]*(")', re.MULTILINE)
    for pyproject in PYPROJECT_FILES:
        if not pyproject.exists():
            continue
        text = pyproject.read_text()
        new_text, count = pattern.subn(rf"\g<1>{version}\2", text, count=1)
        if count:
            pyproject.write_text(new_text)
            print(f"  Updated {pyproject.relative_to(ROOT)}")


def main() -> None:
    if len(sys.argv) < MIN_ARGS:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    old = current_version()

    if action == "show":
        print(f"Current version: {old}")
        sys.exit(0)

    if action not in ("patch", "minor", "major"):
        print(f"Unknown action: {action}")
        print(__doc__)
        sys.exit(1)

    new = bump(old, action)

    if dry_run:
        print(f"Would bump: {old} → {new}")
        sys.exit(0)

    print(f"Bumping: {old} → {new}")
    write_version_json(new)
    write_native_versions(new)
    print(f"Done: {new}")


if __name__ == "__main__":
    main()
