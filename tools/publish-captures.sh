#!/usr/bin/env bash
set -euo pipefail

DEST=/run/elan3212
install -d -m 0755 "$DEST"

last=""
while true; do
  latest="$(ls -t /var/lib/fprint/debug/*.pgm 2>/dev/null | head -1 || true)"
  if [[ -n "$latest" && "$latest" != "$last" ]]; then
    tmp="$DEST/.latest.pgm.tmp"
    cp -f "$latest" "$tmp"
    chmod 0644 "$tmp"
    mv -f "$tmp" "$DEST/latest.pgm"
    last="$latest"
    echo "PUBLICADO $(basename "$latest") $(stat -c %s "$latest") bytes"
  fi
  sleep 0.5
done
