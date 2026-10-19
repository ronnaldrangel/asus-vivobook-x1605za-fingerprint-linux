# Security

## Scope

This project is a local libfprint driver patch for a specific fingerprint
reader. It is not a security boundary and does not replace the security
properties of fprintd, PAM or the sensor.

## Reporting

For driver crashes, protocol issues or build problems, open a GitHub issue with:

- laptop model and `product_name`;
- `ls /sys/bus/spi/devices/`;
- `HID_ID` line for the `04F3` touchpad;
- fprintd version, libfprint version and kernel;
- relevant `journalctl -u fprintd` lines.

Do **not** attach fingerprint images, templates or `/var/lib/fprint`.

## PAM

`scripts/install-pam-retries.sh` is optional and changes the number of
fingerprint attempts before password fallback. Review it before running it.
The password fallback should remain enabled.

## Biometric data

Diagnostic image dumps are disabled by default. If you enable
`ELANSPI_DEBUG_DUMP=1`, treat the generated files as sensitive biometric data
and delete them after debugging.
