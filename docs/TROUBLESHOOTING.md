# Troubleshooting

## First checks

```bash
cat /sys/class/dmi/id/product_name
ls /sys/bus/spi/devices/ | grep -i ELAN
ls -l /dev/spidev0.0
cat /sys/module/spidev/parameters/bufsiz
fprintd-list "$USER"
journalctl -u fprintd -b --no-pager | tail -100
```

## `No devices available`

- Confirm `spi-ELAN7001:00` exists.
- Confirm the SPI device is bound to `spidev`.
- Confirm fprintd loads `/opt/elan3212/lib/libfprint-2.so.2.0.0`.
- Restart fprintd: `sudo systemctl restart fprintd`.

## `timed out waiting for image`

- `bufsiz` must be `32768`.
- Reboot after the installer changes initramfs.
- Check that another program is not claiming the device.

## `swipe too short`

The press patch is not active. Check `ELANSPI_PRESS_MODE` and
`FP_SCAN_TYPE_PRESS`; the stock driver uses the swipe state machine.

## `No enough keypoints found`

The image reached SIGFM but had too few ridges. Hold the finger flat over the
whole sensor, keep it still, and retry. Eight enrollment samples and PAM
retries reduce the impact.

## `verify-no-match` immediately

The template is likely bad. Delete and re-enroll:

```bash
fprintd-delete "$USER" -f right-index-finger
fprintd-enroll -f right-index-finger
```

## `Cannot run while suspended`

An action was interrupted or the device was left suspended:

```bash
sudo systemctl restart fprintd
```

## `Device was already claimed`

Close fingerprint test windows, GNOME Settings and any script holding the
device, then restart fprintd.

## `g_object_unref` assertion

Known non-fatal assertion in this local build. It does not prevent enrollment
or verification. Collect the journal if it becomes frequent.

## Debug image dumps

Image dumps are off by default. To enable them temporarily:

```bash
sudo install -d /etc/systemd/system/fprintd.service.d
sudo tee /etc/systemd/system/fprintd.service.d/99-elan3212-debug.conf >/dev/null <<'EOF'
[Service]
Environment="ELANSPI_DEBUG_DUMP=1"
EOF
sudo systemctl daemon-reload
sudo systemctl restart fprintd
```

Images are written to `/var/lib/fprint/debug` (root-only). Remove them after
diagnosis. Never publish them.
