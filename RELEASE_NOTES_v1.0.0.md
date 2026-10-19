# v1.0.0

First public release of the ASUS Vivobook 16 X1605ZA / ELAN7001 / 04F3:3212
press-mode fingerprint driver for Linux.

## Included

- `patches/0001-elan3212-press-mode.patch`
- modified `elanspi.c` / `elanspi.h` reference files
- build, install, optional PAM and rollback scripts
- English and Spanish documentation
- optional web diagnostic tools

## Tested

- Ubuntu 26.04.1 LTS, kernel 7.0.0-38-generic, fprintd 1.94.5.
- 8/8 enrollment stages.
- 5/5 genuine and 5/5 impostor checks in the 80×80 test run.
- `sudo` fingerprint authentication with password fallback.

## Known limitations

- Occasional `No enough keypoints found`; hold the finger flat and retry.
- Non-fatal `g_object_unref` assertion in some stage transitions.
- Only tested on the X1605ZA with `ELAN7001` + `04F3:3212`.
