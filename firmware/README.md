# ESP32 servo controller

This firmware moves the two servos and leaves the rechargeable UV lamp autonomous. It does not switch the lamp, time the cure, or read a photodiode. The operator presses the lamp button and measures exposure time.

## Hardware

- ESP32 DevKit V1: servo 1 PWM on GPIO18; servo 2 PWM on GPIO19.
- Servos: separate regulated 5–6 V supply sized for their stall current. Join supply ground to ESP32 GND. Never power a servo from an ESP32 GPIO.
- Host: USB serial at 115200 baud; one newline-delimited JSON object per line.
- Calibrate servo ranges, zero offsets, and mechanical starting angles in `include/config.h` before attaching the mechanism.

## Serial interface

Request a target with the existing host command name:

```json
{"cmd":"CURE","nail_id":1,"theta1":45.2,"theta2":30.8,"duration_ms":5000}
```

`duration_ms` is ignored because lamp timing is manual. Once motion completes, firmware returns:

```json
{"status":"READY","nail_id":1,"move_ms":812}
```

`ABORT` stops an in-progress movement; it does not turn off the lamp. Errors return `status: ERROR` and a `reason`. The Python controller currently expects timed `DONE` telemetry, so it must be updated to wait for `READY` and operator confirmation before sending the next target. Do not integrate with that controller until its protocol behavior is aligned.

## Build

Install PlatformIO and run from this directory:

```sh
pio run -e esp32dev
pio run -e esp32dev -t upload
pio device monitor -b 115200
```
