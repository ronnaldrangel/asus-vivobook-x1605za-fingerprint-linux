# ASUS Vivobook 16 X1605ZA fingerprint reader on Linux

**ELAN7001 / 04F3:3212 / eFSA80SC press-mode driver for libfprint + SIGFM.**

[English](README.md) | [Español](README.es.md)

[![Linux](https://img.shields.io/badge/Linux-Ubuntu%2026.04-2b6cb0)](#compatibility)
[![License: LGPL-2.1-or-later](https://img.shields.io/badge/License-LGPL--2.1--or--later-blue.svg)](LICENSE)
[![Status: working](https://img.shields.io/badge/status-working-2f855a)](#test-results)

This repository contains a local libfprint patch, a reproducible installer and
troubleshooting notes for the **ASUS Vivobook 16 X1605ZA** fingerprint reader
(**ELAN7001**, HID **04F3:3212**, sensor **eFSA80SC 80×80**) on Linux.

On Windows the reader is a **press** sensor: place your finger on the power
button and the laptop unlocks. The stock `elanspi` driver treats it as a
**swipe** sensor, so Linux reports:

```text
No devices available
timed out waiting for image
swipe too short
No enough keypoints found
Cannot run while suspended
```

This project adds a **press-mode** path that captures one complete 80×80 image,
uses SIGFM for matching, and exposes the device as `FP_SCAN_TYPE_PRESS`.

## Table of contents

- [Does this apply to you?](#does-this-apply-to-you)
- [Symptoms](#symptoms)
- [Compatibility](#compatibility)
- [Quick install](#quick-install)
- [Enroll and verify](#enroll-and-verify)
- [Optional PAM retries](#optional-pam-retries)
- [What the installer changes](#what-the-installer-changes)
- [Troubleshooting](#troubleshooting)
- [Technical notes](#technical-notes)
- [Privacy](#privacy)
- [Uninstall](#uninstall)
- [FAQ](#faq)
- [Credits](#credits)
- [License](#license)

## Does this apply to you?

Run:

```bash
cat /sys/class/dmi/id/product_name
ls /sys/bus/spi/devices/ | grep -i ELAN
grep -i '^HID_ID' /sys/bus/hid/devices/*/uevent | grep -i 04F3
fprintd-list "$USER"
```

Expected hardware fingerprint:

```text
Vivobook_ASUSLaptop X1605ZA_X1605ZA
spi-ELAN7001:00
HID_ID=0018:000004F3:00003212
```

If you see `No devices available` and the IDs above, this repository targets
your machine. If you have a different ELAN PID or a different laptop, the patch
may not apply unchanged.

## Symptoms

Typical reports from affected users:

- `fprintd-list` says `No devices available`.
- GNOME Settings has no fingerprint enrollment entry.
- `fprintd-enroll` reaches one or two stages and then says
  `enroll-swipe-too-short`.
- The daemon logs `timed out waiting for image`.
- After an interrupted enrollment, the daemon says
  `Cannot run while suspended`.
- Verification sometimes logs `No enough keypoints found`.

The sensor itself is usually fine. The problem is that this area sensor is
being driven through the swipe state machine.

## Compatibility

| Item | Tested value |
| --- | --- |
| Laptop | ASUS Vivobook 16 X1605ZA (`Vivobook_ASUSLaptop X1605ZA_X1605ZA`) |
| Fingerprint ACPI ID | `ELAN7001` |
| Touchpad/HID PID | `04F3:3212` |
| Sensor | `eFSA80SC`, 80×80 |
| Bus | SPI (`spi-ELAN7001:00`, `/dev/spidev0.0`) |
| OS | Ubuntu 26.04.1 LTS |
| Kernel | 7.0.0-38-generic |
| fprintd | 1.94.5 |
| libfprint base | 1.95.1 + SIGFM fork |
| Desktop | GNOME 50 / Wayland |

The patch is intentionally limited to `ELAN7001` + `04F3:3212`. Similar
`eFSA80SC` sensors may work with a different PID entry, but they are untested.

## Quick install

Requirements: Ubuntu/Debian with `apt`, `initramfs-tools`, sudo, and a reboot.

```bash
git clone https://github.com/ronnaldrangel/asus-vivobook-x1605za-fingerprint-linux.git
cd asus-vivobook-x1605za-fingerprint-linux
sudo ./scripts/install.sh
sudo reboot
```

The installer builds a patched libfprint + SIGFM fork, installs it under
`/opt/elan3212`, and configures fprintd to load only that copy. The distribution
libfprint is not replaced.

After reboot:

```bash
cat /sys/module/spidev/parameters/bufsiz   # must print 32768
fprintd-list "$USER"
```

## Enroll and verify

```bash
fprintd-enroll -f right-index-finger
```

Place the **right index finger** flat on the reader and hold it still for
1–2 seconds. Repeat **8 times**, varying the position slightly:

1. center
2. slightly up
3. slightly down
4. slightly left
5. slightly right
6. center
7. slightly up
8. slightly down

Then:

```bash
fprintd-verify right-index-finger
```

For a wrong-finger check, run the same command and use a different finger; it
must report `verify-no-match`.

## Optional PAM retries

The default Ubuntu PAM line allows one fingerprint attempt before falling back
to the password. If the first capture has few keypoints, you can opt in to
three attempts:

```bash
sudo ./scripts/install-pam-retries.sh
```

The script backs up `/etc/pam.d/common-auth` first. The password remains a
fallback. This is optional and is not installed by default.

## What the installer changes

- Builds libfprint from `goodix-fp-linux-dev/libfprint` at commit
  `07306bbc9256942595e31fb0f407b364ffa24d07`.
- Applies `patches/0001-elan3212-press-mode.patch`.
- Installs the library to `/opt/elan3212/lib`.
- Creates `/etc/systemd/system/fprintd.service.d/90-elan3212.conf` with
  `LD_LIBRARY_PATH=/opt/elan3212/lib`.
- Creates `/etc/modprobe.d/elanspi-fingerprint.conf` with
  `options spidev bufsiz=32768`.
- Adds `idma64` and `spidev` to `/etc/initramfs-tools/modules`.

It does **not** modify PAM unless you run the optional PAM script.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `No devices available` | `ls /sys/bus/spi/devices/` must contain `spi-ELAN7001:00`; the udev rule must bind it to `spidev`. |
| `No devices available` after install | Check `fprintd` loads `/opt/elan3212/lib/libfprint-2.so.2.0.0` and the drop-in is active. |
| `timed out waiting for image` | Confirm `cat /sys/module/spidev/parameters/bufsiz` is `32768`; reboot after install. |
| `swipe too short` | The driver is still using the swipe path. Check that `04F3:3212` has `ELANSPI_PRESS_MODE` and `FP_SCAN_TYPE_PRESS`. |
| `No enough keypoints found` | A capture had too few ridges. Hold the finger flat, cover the whole sensor and retry; PAM retries help. |
| `Cannot run while suspended` | Restart fprintd after an interrupted action: `sudo systemctl restart fprintd`. |
| Verification says `verify-no-match` immediately | The template may be bad; delete and re-enroll `right-index-finger`. |
| Enrollment finishes instantly | The finger may still be on the sensor; lift fully between the 8 presses. |
| `g_object_unref` assertion in journal | Known non-fatal lifecycle assertion in this local build; it does not prevent enrollment or verification. |

Useful diagnostics:

```bash
journalctl -u fprintd -b --no-pager | tail -100
ls -l /dev/spidev0.0
cat /sys/module/spidev/parameters/bufsiz
fprintd-list "$USER"
```

## Technical notes

- The `elanspi` driver normally treats HV sensors as swipe sensors and caps a
  frame at 43 rows.
- The press path processes the full 80×80 `last_image`, corrects the background,
  rotates 90° right, normalizes the histogram and applies a light Gaussian
  smoothing.
- A 120 ms settle delay runs after finger-down; two frames are captured and the
  second is submitted.
- SIGFM is used instead of NBIS/Bozorth3 because NBIS does not discriminate
  fingers reliably on these small ELAN images.
- `spidev.bufsiz=32768` is required because the default 4096-byte buffer splits
  the image transfer.
- The 160×160 upscale experiment was discarded: it was slower and did not
  improve matching.

The diagnostic web viewer in `tools/` is optional. Image dumps are disabled by
default; set `ELANSPI_DEBUG_DUMP=1` in the fprintd drop-in only when debugging.

## Privacy

This repository contains **no fingerprint images, templates or biometric data**.
The diagnostic tools can dump images only when explicitly enabled, and the
captures stay on the local machine. Do not publish `/var/lib/fprint` or debug
captures.

## Uninstall

```bash
sudo ./scripts/rollback.sh
sudo reboot
```

The rollback restores PAM from its backup if the optional script was used and
returns fprintd to the distribution library. It does not automatically delete
enrolled fingerprints; remove them with:

```bash
fprintd-delete "$USER" -f right-index-finger
```

## FAQ

### Why does Windows unlock with a touch but Linux asks for a swipe?

Windows uses the ELAN area sensor in press mode. The stock Linux `elanspi`
driver exposes it as a swipe sensor. This patch adds a press-mode path.

### Does this replace the Ubuntu libfprint package?

No. The patched library is isolated in `/opt/elan3212` and loaded only by
fprintd through a systemd drop-in.

### Does it work on other ASUS Vivobook models?

It is tested only on the X1605ZA with `ELAN7001` + `04F3:3212`. Other
`eFSA80SC` variants may need a different PID entry and testing.

### Why eight enrollment samples?

SIGFM stores multiple images. Eight presses with slight position changes gave
better tolerance to finger placement than five.

### Why not lower the SIGFM threshold?

Most failures are capture failures (`No enough keypoints found`), not threshold
failures. Lowering the threshold would not fix a bad image and could increase
false accepts.

### Does it work with sudo and the login screen?

Yes, once fprintd detects the press device. PAM is already configured on Ubuntu;
the optional PAM script only increases the retry count.

## Credits

- [libfprint](https://gitlab.freedesktop.org/libfprint/libfprint) and the
  original ELAN SPI reverse engineering by
  [mincrmatt12](https://github.com/mincrmatt12/elan-spi-fingerprint).
- [goodix-fp-linux-dev/libfprint](https://github.com/goodix-fp-linux-dev/libfprint)
  for the SIGFM branch.
- [r4nd3l/elan-3104-fingerprint-linux](https://github.com/r4nd3l/elan-3104-fingerprint-linux)
  for the eFSA80SC reference work.
- [pesoiq/asus-expertbook-elan322d-fingerprint-linux](https://github.com/pesoiq/asus-expertbook-elan322d-fingerprint-linux)
  for ELAN 322D capture and SIGFM validation.

## License

The driver changes and patch are distributed under the **GNU Lesser General
Public License, version 2.1 or later**, matching libfprint. See [LICENSE](LICENSE)
and [NOTICE](NOTICE).
