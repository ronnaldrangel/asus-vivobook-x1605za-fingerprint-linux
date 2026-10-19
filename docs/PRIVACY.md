# Privacy and biometric data

- This repository contains no fingerprint images, templates or captured
  biometric data.
- The diagnostic image dump is disabled by default.
- When `ELANSPI_DEBUG_DUMP=1` is enabled, captures are written to
  `/var/lib/fprint/debug` on the local machine, readable only by root.
- The optional web viewer publishes only the latest capture to
  `/run/elan3212/latest.pgm` for the local user; it does not upload anything.
- Do not commit or publish `/var/lib/fprint`, `/var/lib/fprint/debug` or
  `/run/elan3212`.
- Fingerprint templates are stored by fprintd under `/var/lib/fprint/<user>`.
  They are biometric data and should be treated as sensitive.
