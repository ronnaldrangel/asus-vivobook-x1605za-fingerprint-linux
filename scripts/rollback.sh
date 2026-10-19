#!/usr/bin/env bash
set -Eeuo pipefail

PREFIX="/opt/elan3212"
DROPIN="/etc/systemd/system/fprintd.service.d/90-elan3212.conf"
MODPROBE_FILE="/etc/modprobe.d/elanspi-fingerprint.conf"
INITRAMFS_MODULES="/etc/initramfs-tools/modules"
PAM_FILE="/etc/pam.d/common-auth"

if [[ $EUID -ne 0 ]]; then
  echo "Run this script with sudo: sudo $0" >&2
  exit 1
fi

echo "==> Stopping fprintd"
systemctl stop fprintd.service 2>/dev/null || true
systemctl stop elan3212-publisher.service 2>/dev/null || true

echo "==> Removing local library and configuration"
rm -f -- "$DROPIN"
rm -rf -- "$PREFIX"
rm -f -- "$MODPROBE_FILE"
rm -rf -- /var/lib/fprint/debug /run/elan3212

if [[ -f "$INITRAMFS_MODULES.elan3212.bak" ]]; then
  cp -a "$INITRAMFS_MODULES.elan3212.bak" "$INITRAMFS_MODULES"
else
  sed -i '/^idma64$/d;/^spidev$/d' "$INITRAMFS_MODULES"
fi

if [[ -f "$PAM_FILE.elan3212.bak" ]]; then
  cp -a "$PAM_FILE.elan3212.bak" "$PAM_FILE"
fi

update-initramfs -u -k "$(uname -r)"
systemctl daemon-reload
systemctl start fprintd.service 2>/dev/null || true

cat <<'EOF'

Rollback complete. Reboot to return to the stock libfprint.
Enrolled fingerprint data was not deleted. Remove it manually if desired:
  fprintd-delete "$USER" -f right-index-finger
EOF
