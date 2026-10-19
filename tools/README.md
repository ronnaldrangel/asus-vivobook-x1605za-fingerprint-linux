# Diagnostic tools

These tools are optional. The driver and installer do not require them.

## Enable image dumps

Image dumps are disabled by default. Add a temporary fprintd drop-in:

```bash
sudo tee /etc/systemd/system/fprintd.service.d/99-elan3212-debug.conf >/dev/null <<'EOF'
[Service]
Environment="ELANSPI_DEBUG_DUMP=1"
EOF
sudo systemctl daemon-reload
sudo systemctl restart fprintd
```

Captures are written to `/var/lib/fprint/debug` with root-only access.

## Publish the latest capture

Run as root:

```bash
sudo ./publish-captures.sh
```

It copies the newest PGM to `/run/elan3212/latest.pgm` for the local user. Stop
it with Ctrl-C when finished.

## Web viewer

```bash
python3 ./visor_web_elan3212.py
```

Open <http://127.0.0.1:8765/>. Pages:

- `/` — one-shot capture viewer
- `/enroll` — 8-stage enrollment with preview
- `/test` — 5 genuine + 5 impostor checks

The viewer keeps the fprintd device claimed while it runs. Stop it before using
fingerprint login or sudo.

## Privacy

Do not publish captures, `/var/lib/fprint` or `/run/elan3212`. They contain
biometric data.
