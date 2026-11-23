"""Preview, confirm and dispatch one sequential curing run."""

import argparse
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4

from software.protocol import BAUD_RATE, cure_command, decode, done_fields, encode

LOG_FIELDS = ("run_id", "utc", "source", "nail_id", "u_px", "v_px", "radius_px",
              "confidence", "x_mm", "y_mm", "theta1", "theta2", "duration_ms",
              "status", "actual_ms", "uv_adc_avg", "skin_spill_est")


def append_log(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
        if handle.tell() == 0:
            writer.writeheader()
        writer.writerow(row)


def execute(port, targets, log_path, source, is_cancelled):
    run_id = str(uuid4())
    port.reset_input_buffer()
    for nail, xy, command in targets:
        if is_cancelled():
            return
        row = dict(run_id=run_id, utc=datetime.now(timezone.utc).isoformat(),
                   source=source, nail_id=nail.nail_id, u_px=nail.centroid[0],
                   v_px=nail.centroid[1], radius_px=nail.radius_px, confidence=nail.confidence,
                   x_mm=xy[0], y_mm=xy[1], theta1=command["theta1"], theta2=command["theta2"],
                   duration_ms=command["duration_ms"])
        status = "ERROR"
        try:
            port.write(encode(command))
            deadline = time.monotonic() + command["duration_ms"] / 1000 + 5
            buffer = bytearray()
            while time.monotonic() < deadline:
                if is_cancelled():
                    status = "ABORT"
                    return
                buffer.extend(port.read(port.in_waiting or 1))
                if len(buffer) > 4096:
                    raise ValueError("Oversized serial response")
                if b"\n" in buffer:
                    line, _, trailing = buffer.partition(b"\n")
                    if trailing.strip():
                        raise ValueError("Unexpected extra serial data")
                    row.update(done_fields(decode(line), nail.nail_id))
                    status = "DONE"
                    break
            else:
                status = "TIMEOUT"
                raise TimeoutError(f"No DONE for nail {nail.nail_id}")
        finally:
            try:
                if status != "DONE":
                    port.write(encode({"cmd": "ABORT"}))
            finally:
                append_log(log_path, dict(row, status=status))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--port")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--segmenter", choices=("onnx", "contours"), default="onnx")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--log", type=Path, default=Path("data/experiment_logs.csv"))
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--duration-ms", type=int, default=5000)
    parser.add_argument("--demo", action="store_true", help="Synthetic frame and fixed points")
    parser.add_argument("--yes", action="store_true", help="Run a headless synthetic demo")
    parser.add_argument("--preview-only", action="store_true", help="Save a still image without UART")
    args = parser.parse_args()
    if args.preview_only and (not (args.image or args.demo) or not args.capture or args.port or args.yes):
        parser.error("--preview-only requires --image or --demo and --capture, without --port or --yes")
    headless = args.yes or args.preview_only
    if args.yes and not args.demo:
        parser.error("--yes requires --demo")
    if args.demo and args.image:
        parser.error("--demo and --image are mutually exclusive")
    if args.demo and args.port and not args.port.startswith("/dev/pts/"):
        parser.error("Demo targets require a pseudo-terminal")

    import cv2
    import numpy as np
    from software.calibration.homography_ik import Arm, Homography
    from software.vision.segmenter import PretrainedNailSegmenter, nail_from_mask

    source = ("synthetic" if args.demo else
              "vision_onnx" if args.segmenter == "onnx" else "vision_contours")
    config = json.loads(args.config.read_text())
    if config.get("simulation_only") and not args.demo:
        parser.error("Use a hardware calibration configuration for real images")
    arm = Arm(**config["arm"])
    spot_radius = float(config["spot_radius_mm"])
    if not 0 < spot_radius < float("inf"):
        parser.error("spot_radius_mm must be finite and positive")
    cure_command(1, 0, 0, args.duration_ms)
    calibration = config["calibration"]
    mapper = None
    if "image_px" in calibration:
        mapper = Homography(calibration["image_px"], calibration["world_mm"])

    window = "Curado selectivo | SPACE curar | S captura | ESC salir"

    def cancelled():
        return (cv2.waitKey(1) & 0xff == 27 or
                cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1)

    with ExitStack() as stack:
        camera = None
        model = None
        fixed_frame = None
        if not headless:
            stack.callback(cv2.destroyAllWindows)
        if args.demo:
            fixed_frame = np.full((480, 640, 3), (55, 48, 48), np.uint8)
            points = [(185, 286), (240, 183), (309, 149), (374, 172), (435, 225)]
            palm = np.array([(170, 305), (242, 258), (381, 255), (442, 284),
                             (416, 400), (226, 409)], np.int32)
            cv2.fillPoly(fixed_frame, [palm], (145, 169, 202))
            demo_nails = []
            for nail_id, (x, y) in enumerate(points, start=1):
                cv2.line(fixed_frame, (x, y), (max(x, 250), 330), (145, 169, 202), 40)
                mask = np.zeros(fixed_frame.shape[:2], np.uint8)
                cv2.ellipse(mask, (x, y), (11, 16), 0, 0, 360, 1, -1)
                demo_nails.append(nail_from_mask(nail_id, mask))
            for nail in demo_nails:
                fixed_frame[nail.mask != 0] = (159, 156, 218)
        else:
            if args.segmenter == "onnx":
                from software.vision.onnx_segmenter import OnnxNailSegmenter

                model = OnnxNailSegmenter(args.model or Path("models/nail-seg.onnx"))
            else:
                model = PretrainedNailSegmenter(args.model or Path("models/hand_landmarker.task"))
                stack.callback(model.close)
            if args.image:
                fixed_frame = cv2.imread(str(args.image))
                if fixed_frame is None:
                    parser.error("Could not read image")
            else:
                camera = cv2.VideoCapture(args.camera)
                stack.callback(camera.release)
                if not camera.isOpened():
                    parser.error("Could not open camera")
        port = None
        if args.port:
            import serial
            port = stack.enter_context(serial.Serial(args.port, BAUD_RATE, timeout=0.05,
                                                       write_timeout=0.5))

        projected_angles = np.linspace(0, 2*np.pi, 64, endpoint=False)
        spot_offsets = spot_radius * np.column_stack(
            (np.cos(projected_angles), np.sin(projected_angles)))
        static_detection = None
        while True:
            start = time.monotonic()
            frame = fixed_frame
            if camera is not None:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError("Camera frame unavailable")
            expected_size = calibration.get("image_size_px")
            if expected_size and list(frame.shape[1::-1]) != expected_size:
                raise ValueError(f"Calibration requires image size {expected_size}")
            if mapper is None:
                mapper = Homography.from_aruco(frame, calibration["markers"],
                                               calibration.get("dictionary", "DICT_4X4_50"))
            hud = frame.copy()
            if args.demo:
                nails = demo_nails
            elif static_detection is not None:
                nails = static_detection
            else:
                x, y, width, height = config.get("roi_px", [0, 0, frame.shape[1], frame.shape[0]])
                if not (0 <= x < x + width <= frame.shape[1] and
                        0 <= y < y + height <= frame.shape[0]):
                    raise ValueError("ROI lies outside the frame")
                nails = model.segment(frame[y:y+height, x:x+width])
                for nail in nails:
                    u, v = nail.centroid
                    nail.centroid = (u+x, v+y)
                    mask = np.zeros(frame.shape[:2], np.uint8)
                    mask[y:y+height, x:x+width] = nail.mask
                    nail.mask = mask
                if camera is None:
                    static_detection = nails
                cv2.rectangle(hud, (x, y), (x+width-1, y+height-1), (180, 180, 180), 1)

            targets = []
            for nail in nails:
                pixels = nail.mask != 0
                hud[pixels] = (0.55 * hud[pixels] + 0.45 * np.array([70, 225, 120])).astype(np.uint8)
                center = tuple(np.rint(nail.centroid).astype(int))
                try:
                    xy = tuple(map(float, mapper.to_world([nail.centroid])[0]))
                    theta1, theta2 = arm.solve(xy)
                    polygon = np.rint(mapper.to_image(spot_offsets + xy)).astype(np.int32)
                except ValueError:
                    cv2.circle(hud, center, 9, (0, 0, 255), 2)
                    continue
                targets.append((nail, xy, cure_command(nail.nail_id, theta1, theta2, args.duration_ms)))
                cv2.polylines(hud, [polygon], True, (255, 185, 80), 2)
                cv2.putText(hud, str(nail.nail_id), center, cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, (255, 255, 255), 1, cv2.LINE_AA)
            ready = (len(nails) == len(targets) == 5
                     and {n.nail_id for n, _, _ in targets} == set(range(1, 6)))
            label = "SIMULACION" if args.demo else "VISION"
            status = f"{label} | {len(targets)}/5 objetivos validos"
            if camera is not None:
                status += f" | {1/max(time.monotonic()-start, 0.0001):.1f} FPS"
            cv2.putText(hud, status, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.64,
                        (255, 255, 255), 1, cv2.LINE_AA)

            def capture():
                args.capture.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(str(args.capture), hud):
                    raise OSError(f"Could not save {args.capture}")
                bundle = args.capture.with_suffix(".npz")
                masks = np.stack([n.mask for n in nails]) if nails else np.empty((0, *frame.shape[:2]), np.uint8)
                metadata = {}
                if args.demo:
                    metadata["hand_bbox_px"] = (149, 128, 464, 410)
                elif "hand_bbox_px" in config:
                    metadata["hand_bbox_px"] = config["hand_bbox_px"]
                np.savez_compressed(bundle, ids=[n.nail_id for n in nails], masks=masks,
                                    confidence=[n.confidence if n.confidence is not None else np.nan
                                                for n in nails],
                                    source=source,
                                    matrix=mapper.matrix, spot_radius_mm=spot_radius, **metadata)

            if args.preview_only:
                capture()
                return
            if not args.yes:
                cv2.imshow(window, hud)
            key = 32 if args.yes else cv2.waitKey(1) & 0xff
            if key == 27:
                return
            if key == ord("s") and args.capture:
                capture()
            if key == 32 and (ready or args.yes):
                if args.capture:
                    capture()
                if not ready:
                    raise ValueError("Demo targets failed reach validation")
                if port:
                    execute(port, targets, args.log, source,
                            lambda: not headless and cancelled())
                elif not args.yes:
                    print("Sin puerto serial. Usa --port para enviar las órdenes.")
                if args.yes or port:
                    return


if __name__ == "__main__":
    main()
