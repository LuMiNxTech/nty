#!/usr/bin/env sh
# Verify that an ELF binary is fully statically linked: no program interpreter
# and no shared-library dependencies. Usage: check-static.sh <binary>
set -eu
bin="$1"
file "$bin"
if readelf -lW "$bin" | grep -q 'INTERP'; then
  echo "error: $bin requests a dynamic loader (PT_INTERP present)" >&2
  exit 1
fi
if readelf -dW "$bin" | grep -q '(NEEDED)'; then
  echo "error: $bin depends on shared libraries:" >&2
  readelf -dW "$bin" | grep '(NEEDED)' >&2
  exit 1
fi
echo "OK: $bin is statically linked"
