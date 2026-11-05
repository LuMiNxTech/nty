#!/usr/bin/env python3
"""Enforce crate dependency boundaries (design: nty-core is provider/tool/frontend
agnostic; nty-proto carries no runtime). Exits non-zero on any violation.

Rules are checked against every dependency kind (normal, build, dev) so that
test-only shortcuts cannot erode the architecture either.
"""
import json
import subprocess
import sys

WORKSPACE_PREFIX = "nty"

# crate -> set of workspace crates it may depend on (None = no restriction)
ALLOWED_WORKSPACE_DEPS = {
    "nty-proto": set(),
    "nty-core": {"nty-proto"},
}

# crate -> allowlist of external crates (None = no restriction)
ALLOWED_EXTERNAL_DEPS = {
    "nty-proto": {"serde", "serde_json", "schemars"},
}


def main() -> int:
    meta = json.loads(
        subprocess.check_output(
            ["cargo", "metadata", "--format-version", "1", "--no-deps"], text=True
        )
    )
    members = {p["name"] for p in meta["packages"]}
    errors = []
    for pkg in meta["packages"]:
        name = pkg["name"]
        for dep in pkg["dependencies"]:
            dep_name = dep["name"]
            kind = dep.get("kind") or "normal"
            if dep_name in members:
                allowed = ALLOWED_WORKSPACE_DEPS.get(name)
                if allowed is not None and dep_name not in allowed:
                    errors.append(f"{name} must not depend on {dep_name} ({kind})")
            else:
                allowed = ALLOWED_EXTERNAL_DEPS.get(name)
                if allowed is not None and dep_name not in allowed:
                    errors.append(
                        f"{name} may only use {sorted(allowed)}; found {dep_name} ({kind})"
                    )
    for e in errors:
        print(f"boundary violation: {e}", file=sys.stderr)
    if not errors:
        print(f"crate boundaries OK ({len(members)} workspace crates)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
