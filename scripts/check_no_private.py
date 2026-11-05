#!/usr/bin/env python3
"""Fail if files from the private planning workspace leak into this public repo.

This repository is published. Planning documents, internal specs, research
archives and agent instructions live in a separate private workspace and must
never be committed here. The check covers tracked files and untracked,
non-ignored files, so it also catches mistakes before they are committed.
"""
import fnmatch
import pathlib
import subprocess
import sys

# Path patterns (matched against repo-relative POSIX paths).
FORBIDDEN_PATHS = [
    "TODO.md",
    "**/TODO.md",
    "AGENTS.md",
    "**/AGENTS.md",
    "CLAUDE.md",
    "**/CLAUDE.md",
    "docs/design.md",
    "docs/research/*",
    "**/decisions-log.md",
    "**/context-cache-analysis.md",
]

# Text markers that only appear in private workspace material.
FORBIDDEN_MARKERS = [
    "nty-workspace",
    "decisions-log",
    "docs/research/",
]

SELF = "scripts/check_no_private.py"


def repo_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    )
    return [p for p in out.decode().split("\0") if p]


def matches(path: str) -> bool:
    return any(
        fnmatch.fnmatch(path, pat) or fnmatch.fnmatch("/" + path, "*/" + pat)
        for pat in FORBIDDEN_PATHS
    )


def main() -> int:
    errors = []
    for path in repo_files():
        if matches(path):
            errors.append(f"private file must not be in the public repo: {path}")
            continue
        if path == SELF:
            continue
        try:
            text = pathlib.Path(path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for marker in FORBIDDEN_MARKERS:
            if marker in text:
                errors.append(f"private marker {marker!r} found in {path}")
    for e in errors:
        print(f"privacy check: {e}", file=sys.stderr)
    if not errors:
        print("privacy check OK: no private workspace content found")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
