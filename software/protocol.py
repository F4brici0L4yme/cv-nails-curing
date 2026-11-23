"""Shared newline-delimited JSON framing for the host and simulator."""

import json
import math

BAUD_RATE = 115200
MAX_CURE_MS = 15000


def encode(message):
    return (json.dumps(message, allow_nan=False, separators=(",", ":")) + "\n").encode()


def decode(line):
    message = json.loads(line)
    if not isinstance(message, dict):
        raise ValueError("Expected a JSON object")
    return message


def cure_command(nail_id, theta1, theta2, duration_ms):
    if type(nail_id) is not int or nail_id < 1:
        raise ValueError("Invalid nail ID")
    if type(duration_ms) is not int or not 1 <= duration_ms <= MAX_CURE_MS:
        raise ValueError("Invalid cure duration")
    if any(type(angle) not in (float, int) or not math.isfinite(angle)
           for angle in (theta1, theta2)):
        raise ValueError("Invalid joint angle")
    return dict(cmd="CURE", nail_id=nail_id, theta1=theta1, theta2=theta2,
                duration_ms=duration_ms)


def done_fields(message, nail_id):
    if message.get("status") != "DONE" or message.get("nail_id") != nail_id:
        raise ValueError(f"Unexpected completion message: {message}")
    fields = {}
    for key, minimum, maximum in (("actual_ms", 1, math.inf),
                                  ("uv_adc_avg", 0, math.inf),
                                  ("skin_spill_est", 0, 1)):
        value = message.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"Invalid telemetry field: {key}")
        fields[key] = value
    return fields
