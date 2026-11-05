#!/usr/bin/env sh
# Guard against private workspace content leaking into the public repo.
set -eu
cd "$(dirname "$0")/.."
exec python3 scripts/check_no_private.py "$@"
