# Contributing

Contributions are welcome, especially:

- testing on other ASUS Vivobook models with `ELAN7001` or `eFSA80SC`;
- improving capture stability and SIGFM matching;
- reducing the known `g_object_unref` lifecycle assertion;
- packaging for other distributions.

## Rules

- Do not include fingerprint images, templates or biometric captures.
- Keep the patch limited to the tested hardware unless you add a clear device
  entry and test results.
- Include kernel, fprintd, libfprint and hardware IDs in bug reports.
- Keep the distribution libfprint untouched; the local library must remain
  isolated under `/opt/elan3212`.

## Development build

```bash
sudo ./scripts/build.sh
```

The script clones the pinned SIGFM fork, applies the patch and runs the SIGFM
unit tests.
