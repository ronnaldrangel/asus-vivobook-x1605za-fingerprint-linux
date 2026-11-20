#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_ROOT="${BUILD_ROOT:-/var/tmp/elan3212-build}"
PREFIX="/opt/elan3212"
LIBDIR="$PREFIX/lib"
DROPIN="/etc/systemd/system/fprintd.service.d/90-elan3212.conf"
MODPROBE_FILE="/etc/modprobe.d/elanspi-fingerprint.conf"
INITRAMFS_MODULES="/etc/initramfs-tools/modules"

if [[ $EUID -ne 0 ]]; then
  echo "Run this installer with sudo: sudo $REPO_DIR/scripts/install.sh" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "Cannot detect Linux distribution (/etc/os-release missing)." >&2
  exit 1
fi

if grep -q '^ID=ubuntu\|^ID=debian' /etc/os-release; then
  DISTRO="debian"
elif grep -q '^ID=arch\|^ID_LIKE=.*arch' /etc/os-release; then
  DISTRO="arch"
else
  echo "This installer targets Ubuntu/Debian or Arch Linux." >&2
  exit 1
fi

echo "==> Installing build dependencies ($DISTRO)"
if [[ "$DISTRO" == "debian" ]]; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    git meson ninja-build build-essential pkg-config \
    libglib2.0-dev libgusb-dev libgudev-1.0-dev libudev-dev \
    libpixman-1-dev libcairo2-dev libnss3-dev \
    libpolkit-gobject-1-dev libsystemd-dev libopencv-dev doctest-dev
else
  pacman -S --needed --noconfirm \
    git meson ninja base-devel pkgconf \
    glib2 glib2-devel libgusb libgudev systemd \
    pixman cairo nss polkit opencv doctest fprintd
fi

echo "==> Building libfprint + SIGFM + ELAN 04F3:3212 press mode"
BUILD_ROOT="$BUILD_ROOT" "$REPO_DIR/scripts/build.sh"
LIBRARY="$BUILD_ROOT/build/libfprint/libfprint-2.so.2.0.0"
[[ -f "$LIBRARY" ]] || { echo "Missing built library: $LIBRARY" >&2; exit 1; }

echo "==> Installing isolated library in $LIBDIR"
install -d -m 0755 "$LIBDIR"
install -m 0755 "$LIBRARY" "$LIBDIR/libfprint-2.so.2.0.0"
ln -sfn libfprint-2.so.2.0.0 "$LIBDIR/libfprint-2.so.2"
ln -sfn libfprint-2.so.2 "$LIBDIR/libfprint-2.so"

echo "==> Configuring fprintd to load the isolated library"
install -d -m 0755 "$(dirname "$DROPIN")"
cat > "$DROPIN" <<'EOF'
[Service]
Environment="LD_LIBRARY_PATH=/opt/elan3212/lib"
Restart=on-failure
RestartSec=1s
EOF
chmod 0644 "$DROPIN"

echo "==> Configuring spidev buffer"
printf 'options spidev bufsiz=32768\n' > "$MODPROBE_FILE"
chmod 0644 "$MODPROBE_FILE"

if [[ "$DISTRO" == "debian" ]]; then
  if [[ ! -f "$INITRAMFS_MODULES.elan3212.bak" ]]; then
    cp -a "$INITRAMFS_MODULES" "$INITRAMFS_MODULES.elan3212.bak"
  fi
  grep -qx 'idma64' "$INITRAMFS_MODULES" || echo 'idma64' >> "$INITRAMFS_MODULES"
  grep -qx 'spidev' "$INITRAMFS_MODULES" || echo 'spidev' >> "$INITRAMFS_MODULES"
  update-initramfs -u -k "$(uname -r)"
else
  modprobe -r spidev 2>/dev/null || true
  modprobe spidev bufsiz=32768 2>/dev/null || true
  udevadm trigger /sys/bus/spi/devices/spi-ELAN7001:00 2>/dev/null || true
fi

systemctl daemon-reload
systemctl restart fprintd

cat <<'EOF'

Installation complete.

Reboot once so spidev loads with bufsiz=32768. After reboot:
  cat /sys/module/spidev/parameters/bufsiz
  fprintd-list "$USER"
  fprintd-enroll -f right-index-finger

Enrollment: place the right index finger flat on the reader and hold it
still for 1-2 seconds. Repeat 8 times. Optional PAM retries:
  sudo scripts/install-pam-retries.sh
EOF
