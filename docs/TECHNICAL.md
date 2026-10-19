# Technical notes

## Swipe versus press

The upstream `elanspi` driver models HV sensors as swipe sensors:

- each processed frame is capped at `ELANSPI_MAX_FRAME_HEIGHT = 43` rows;
- multiple frames are collected in `fp_frame_list`;
- movement estimation stitches them;
- enrollment requires `ELANSPI_MIN_FRAMES_SWIPE` frames.

The X1605ZA reader is an 80×80 area sensor used in press mode. Holding a finger
still produces frames with little movement, so the swipe path discards them as
“too small” or reports a short swipe.

## Press path

The local patch adds:

- `ELANSPI_PRESS_MODE` in `driver_data`;
- `scan_type = FP_SCAN_TYPE_PRESS`;
- `nr_enroll_stages = 8`;
- a press state machine:
  1. wait for two fingerprint frames;
  2. report finger down;
  3. wait 120 ms for the finger to settle;
  4. capture two full frames;
  5. process and submit the second 80×80 image;
  6. wait for the finger to lift.

## Image processing

`elanspi_process_full_frame()` processes all 80×80 pixels:

- subtracts the calibrated background;
- applies the 90° right rotation;
- normalizes the histogram;
- applies a light Gaussian smoothing.

The 160×160 bilinear upscale experiment was removed: it was slower and did not
improve matching.

## Matching

SIGFM (SIFT-based) is used instead of NBIS/Bozorth3. On small ELAN images,
NBIS genuine and impostor score distributions overlap; SIGFM separates them.
The local threshold remains 100. Lowering it is not a substitute for a good
capture.

## SPI buffer

The default `spidev.bufsiz=4096` splits the image transfer. The installer sets
`options spidev bufsiz=32768` so the full frame is transferred in one message.

## Isolation

The patched library is installed in `/opt/elan3212` and loaded only by fprintd
through `LD_LIBRARY_PATH`. The distribution libfprint remains untouched.

## Known lifecycle assertion

`g_object_unref` can appear during stage transitions. It is non-fatal in the
tested build. The patch also uses a null `GCancellable` for press-mode HV
captures to avoid repeated `fpi_device_get_cancellable` assertions.
