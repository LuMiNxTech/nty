#!/usr/bin/env sh
# Crate dependency boundary check (see scripts/check_boundaries.py).
set -eu
cd "$(dirname "$0")/.."
exec python3 scripts/check_boundaries.py "$@"
