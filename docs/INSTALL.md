# Installation

## Requirements

- Ubuntu 26.04 or a compatible Debian-based distribution.
- sudo access.
- `initramfs-tools`.
- A reboot.
- The exact reader `ELAN7001` + `04F3:3212` (see `docs/HARDWARE.md`).

## Automated install

```bash
git clone https://github.com/ronnaldrangel/asus-vivobook-x1605za-fingerprint-linux.git
cd asus-vivobook-x1605za-fingerprint-linux
sudo ./scripts/install.sh
sudo reboot
```

The installer:

1. Installs build dependencies with `apt`.
2. Clones the SIGFM libfprint fork at the pinned commit.
3. Applies the press-mode patch.
4. Builds with `-Ddrivers=elanspi` only.
5. Installs `/opt/elan3212/lib/libfprint-2.so.2.0.0`.
6. Creates the fprintd drop-in.
7. Configures `spidev.bufsiz=32768`.
8. Adds `idma64` and `spidev` to the initramfs.

## Manual build

```bash
sudo apt install git meson ninja-build build-essential pkg-config \
  libglib2.0-dev libgusb-dev libgudev-1.0-dev libudev-dev \
  libpixman-1-dev libcairo2-dev libnss3-dev \
  libpolkit-gobject-1-dev libsystemd-dev libopencv-dev doctest-dev

sudo ./scripts/build.sh
```

The built library is:

```text
/var/tmp/elan3212-build/build/libfprint/libfprint-2.so.2.0.0
```

## Verify the installation

```bash
cat /sys/module/spidev/parameters/bufsiz   # 32768
ls -l /dev/spidev0.0
fprintd-list "$USER"
```

`fprintd-list` should show:

```text
Fingerprints for user ... on ElanTech Embedded Fingerprint Sensor (press):
```

## Enroll

```bash
fprintd-enroll -f right-index-finger
```

Hold the finger still for 1–2 seconds. Repeat 8 times, changing the position
slightly as described in the README.

## Verify

```bash
fprintd-verify right-index-finger
```

Use a different finger for the negative test; it must report `verify-no-match`.

## Optional PAM retries

```bash
sudo ./scripts/install-pam-retries.sh
```

This is optional. It backs up `/etc/pam.d/common-auth` and changes the
fingerprint retry count from 1 to 3.

## Rollback

```bash
sudo ./scripts/rollback.sh
sudo reboot
```
