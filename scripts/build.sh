#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_ROOT="${BUILD_ROOT:-/var/tmp/elan3212-build}"
SRC_DIR="$BUILD_ROOT/libfprint-sigfm"
BUILD_DIR="$BUILD_ROOT/build"
UPSTREAM="https://github.com/goodix-fp-linux-dev/libfprint.git"
COMMIT="07306bbc9256942595e31fb0f407b364ffa24d07"
PATCH="$REPO_DIR/patches/0001-elan3212-press-mode.patch"

for tool in git meson ninja pkg-config; do
  command -v "$tool" >/dev/null || {
    echo "Missing build tool: $tool" >&2
    echo "On Ubuntu: sudo apt install git meson ninja-build build-essential pkg-config libglib2.0-dev libgusb-dev libgudev-1.0-dev libudev-dev libcairo2-dev libopencv-dev doctest-dev" >&2
    exit 1
  }
done

mkdir -p "$BUILD_ROOT"

if [[ ! -d "$SRC_DIR/.git" ]]; then
  git clone "$UPSTREAM" "$SRC_DIR"
else
  git -C "$SRC_DIR" fetch --all --tags
fi

git -C "$SRC_DIR" checkout -f "$COMMIT"
git -C "$SRC_DIR" apply --check "$PATCH"
git -C "$SRC_DIR" apply "$PATCH"

# Debian/Ubuntu ships doctest without a pkg-config file.
PKG_CONFIG_DIR="$BUILD_ROOT/pkgconfig"
mkdir -p "$PKG_CONFIG_DIR"
cat > "$PKG_CONFIG_DIR/doctest.pc" <<'EOF'
prefix=/usr
includedir=${prefix}/include
Name: doctest
Description: Doctest C++ testing framework
Version: 2.4.12
Cflags: -I${includedir}
EOF

rm -rf -- "$BUILD_DIR"
PKG_CONFIG_PATH="$PKG_CONFIG_DIR:${PKG_CONFIG_PATH:-}" \
  meson setup "$BUILD_DIR" "$SRC_DIR" \
    --buildtype=release \
    -Ddrivers=elanspi \
    -Dudev_rules=disabled \
    -Dudev_hwdb=disabled \
    -Ddoc=false \
    -Dintrospection=false

ninja -C "$BUILD_DIR"
"$BUILD_DIR/libfprint/sigfm/sigfm-tests"

echo
echo "Built library: $BUILD_DIR/libfprint/libfprint-2.so.2.0.0"
