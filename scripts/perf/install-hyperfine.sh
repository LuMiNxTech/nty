#!/usr/bin/env bash
# Install a pinned, checksum-verified hyperfine release into a directory.
# Usage: install-hyperfine.sh <dest-dir>
# Platform comes from RUNNER_OS / RUNNER_ARCH (GitHub Actions) or uname.
set -euo pipefail

VERSION="2.0.0"
dest="$1"
mkdir -p "$dest"

os="${RUNNER_OS:-$(uname -s)}"
arch="${RUNNER_ARCH:-$(uname -m)}"
case "$os/$arch" in
  Linux/X64 | Linux/x86_64)            target=x86_64-unknown-linux-musl;  ext=tar.gz; sha=38e59087bd65520930a13cf513d8a493b7043741e8ad62349a8a9929eb61bc5c ;;
  Linux/ARM64 | Linux/aarch64)         target=aarch64-unknown-linux-musl; ext=tar.gz; sha=f0591c2cb8f66f2d2624d23979cf96dc99a67cb935f9925c82b9a4e3ffe5b2e1 ;;
  macOS/X64 | Darwin/x86_64)           target=x86_64-apple-darwin;        ext=tar.gz; sha=8afe204926afefa406ad320cef0672b739e5f676c623fbd6d43d779bacd684e3 ;;
  macOS/ARM64 | Darwin/arm64)          target=aarch64-apple-darwin;       ext=tar.gz; sha=590b839cfea386b384ce0b42d16daf2910277cf30950656194bb3a5f20dea81e ;;
  Windows/X64)                         target=x86_64-pc-windows-msvc;     ext=zip;    sha=3dec51acee1060908e67948838d6bc0a7aacde0774acebfa4afb220dcf0bc078 ;;
  Windows/ARM64)                       target=aarch64-pc-windows-msvc;    ext=zip;    sha=c2d2568368d32d0f2a000e604e10cd9fa8d98e2d04cb78f2aa7ab1a8c11b8118 ;;
  *) echo "unsupported platform: $os/$arch" >&2; exit 1 ;;
esac

name="hyperfine-v${VERSION}-${target}"
url="https://github.com/sharkdp/hyperfine/releases/download/v${VERSION}/${name}.${ext}"
tmp="$(mktemp -d)"
curl -fsSL --retry 3 -o "$tmp/archive.$ext" "$url"

if command -v sha256sum >/dev/null; then
  actual="$(sha256sum "$tmp/archive.$ext" | cut -d' ' -f1)"
else
  actual="$(shasum -a 256 "$tmp/archive.$ext" | cut -d' ' -f1)"
fi
if [ "$actual" != "$sha" ]; then
  echo "checksum mismatch for $url: expected $sha, got $actual" >&2
  exit 1
fi

if [ "$ext" = zip ]; then
  unzip -q "$tmp/archive.$ext" -d "$tmp"
  cp "$tmp/$name/hyperfine.exe" "$dest/"
else
  tar -xzf "$tmp/archive.$ext" -C "$tmp"
  cp "$tmp/$name/hyperfine" "$dest/"
fi
rm -rf "$tmp"
echo "installed hyperfine $VERSION ($target) to $dest" >&2
