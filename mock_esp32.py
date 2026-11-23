"""POSIX pseudo-terminal simulator for the ESP32 JSON contract."""

import argparse
import errno
import os
import pty
import select
import time
import tty

from software.protocol import cure_command, decode, encode


def serve(master, speed):
    buffer = b""
    pending = None
    while True:
        timeout = None if pending is None else max(0, pending[0] - time.monotonic())
        ready, _, _ = select.select([master], [], [], timeout)
        if ready:
            buffer += os.read(master, 4096)
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                try:
                    message = decode(line)
                    if message.get("cmd") == "ABORT":
                        pending = None
                    elif message.get("cmd") == "CURE" and pending is None:
                        command = cure_command(*(message[key] for key in
                            ("nail_id", "theta1", "theta2", "duration_ms")))
                        pending = (time.monotonic() + command["duration_ms"] / (1000 * speed),
                                   command)
                except (KeyError, ValueError):
                    continue
            if len(buffer) > 4096:
                buffer = b""
        if pending and time.monotonic() >= pending[0]:
            command = pending[1]
            os.write(master, encode(dict(status="DONE", nail_id=command["nail_id"],
                                         actual_ms=command["duration_ms"], uv_adc_avg=3120,
                                         skin_spill_est=0.04)))
            pending = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speed", type=float, default=1)
    args = parser.parse_args()
    if not 0 < args.speed < float("inf"):
        parser.error("--speed must be finite and positive")
    master, slave = pty.openpty()
    try:
        tty.setraw(slave)
        print(os.ttyname(slave), flush=True)
        serve(master, args.speed)
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        if exc.errno != errno.EIO:
            raise
    finally:
        os.close(slave)
        os.close(master)


if __name__ == "__main__":
    main()
