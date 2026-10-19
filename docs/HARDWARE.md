# Hardware identification

Tested machine:

```text
ASUSTeK COMPUTER INC.
Vivobook_ASUSLaptop X1605ZA_X1605ZA
Board: X1605ZA
Firmware: X1605ZA.316 (2024-03-15)
```

## Fingerprint reader

```bash
cat /sys/class/dmi/id/product_name
ls /sys/bus/spi/devices/
grep -i '^HID_ID' /sys/bus/hid/devices/*/uevent | grep -i 04F3
ls -l /dev/spidev0.0
```

Expected:

```text
Vivobook_ASUSLaptop X1605ZA_X1605ZA
spi-ELAN7001:00
HID_ID=0018:000004F3:00003212
crw------- 1 root root ... /dev/spidev0.0
```

| Property | Value |
| --- | --- |
| ACPI ID | `ELAN7001` |
| HID VID:PID | `04F3:3212` |
| HID name | `ASUE1305:00 04F3:3212` |
| Sensor | `eFSA80SC` |
| Sensor size | 80×80 |
| Sensor ID in driver | 14 (`0xE`) |
| Rotation | 90° right |
| Bus | SPI |

## Related Linux devices

```bash
lspci -nnk | grep -A3 -i -E 'VGA|Network|Audio'
lsusb
```

The fingerprint reader is not a USB device. It appears on the SPI bus as
`spi-ELAN7001:00`; the paired touchpad appears as `04F3:3212`.

## Why the IDs matter

The press-mode patch is keyed to:

```c
{.spi_acpi_id = "ELAN7001",
 .hid_id = {.vid = 0x04f3, .pid = 0x3212},
 .driver_data = ELANSPI_90RIGHT_ROTATE | ELANSPI_PRESS_MODE}
```

Another ELAN PID needs its own entry and validation.
