"""Instance segmentation for the austingg/finger-nail-seg YOLOv8 ONNX model."""

import cv2
import numpy as np

from software.vision.segmenter import BaseNailSegmenter, nail_from_mask


class OnnxNailSegmenter(BaseNailSegmenter):
    def __init__(self, model_path):
        if not model_path.is_file():
            raise FileNotFoundError(f"Modelo ONNX no encontrado: {model_path}. Consulta README.txt.")
        import onnxruntime as ort

        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        model_input, = self.session.get_inputs()
        self.input_name = model_input.name
        self.input_height, self.input_width = map(int, model_input.shape[2:])

    def segment(self, frame):
        height, width = frame.shape[:2]
        scale = min(self.input_width / width, self.input_height / height)
        resized_width = max(1, round(width * scale))
        resized_height = max(1, round(height * scale))
        left = (self.input_width - resized_width) // 2
        top = (self.input_height - resized_height) // 2
        right, bottom = left + resized_width, top + resized_height
        canvas = np.full((self.input_height, self.input_width, 3), 114, dtype=np.uint8)
        canvas[top:bottom, left:right] = cv2.resize(frame, (resized_width, resized_height))
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        batch = np.ascontiguousarray(rgb.transpose(2, 0, 1)[None], dtype=np.float32) / 255
        outputs = self.session.run(None, {self.input_name: batch})
        detections = next((value[0].T for value in outputs if value.ndim == 3), None)
        prototypes = next((value[0] for value in outputs if value.ndim == 4), None)
        if detections is None or prototypes is None:
            raise ValueError("El ONNX debe producir predicciones y prototipos YOLOv8-seg")
        channels = prototypes.shape[0]
        score_end = detections.shape[1] - channels
        if score_end <= 4:
            raise ValueError("El ONNX no contiene puntuaciones de detección")
        scores = detections[:, 4:score_end].max(axis=1)
        candidates = (np.isfinite(detections).all(axis=1) & (scores > 0.25)
                      & (detections[:, 2:4] > 0).all(axis=1))
        detections, scores = detections[candidates], scores[candidates]
        if not len(detections):
            return []
        sizes = detections[:, 2:4]
        boxes = np.column_stack((detections[:, :2] - sizes / 2, sizes))
        integer_boxes = np.rint(boxes).astype(int)
        integer_boxes[:, 2:] = np.maximum(integer_boxes[:, 2:], 1)
        kept = cv2.dnn.NMSBoxes(integer_boxes.tolist(), scores.tolist(), 0.25, 0.45)
        masks = []
        for index in np.asarray(kept, dtype=int).ravel():
            x, y, box_width, box_height = boxes[index]
            x0 = int(np.clip(np.floor((x - left) * width / resized_width), 0, width))
            x1 = int(np.clip(np.ceil((x + box_width - left) * width / resized_width), 0, width))
            y0 = int(np.clip(np.floor((y - top) * height / resized_height), 0, height))
            y1 = int(np.clip(np.ceil((y + box_height - top) * height / resized_height), 0, height))
            if x0 >= x1 or y0 >= y1:
                continue
            logits = np.einsum("c,chw->hw", detections[index, score_end:], prototypes)
            probabilities = 1 / (1 + np.exp(-np.clip(logits, -80, 80)))
            padded = cv2.resize(probabilities, (self.input_width, self.input_height))
            unpadded = cv2.resize(padded[top:bottom, left:right], (width, height))
            crop = np.asarray(unpadded[y0:y1, x0:x1] > 0.5, dtype=np.uint8)
            count, labels, stats, _ = cv2.connectedComponentsWithStats(crop)
            if count < 2:
                continue
            component = 1 + stats[1:, cv2.CC_STAT_AREA].argmax()
            if stats[component, cv2.CC_STAT_AREA] < 8:
                continue
            mask = np.zeros((height, width), dtype=np.uint8)
            mask[y0:y1, x0:x1] = labels == component
            masks.append(nail_from_mask(0, mask, float(scores[index])))

        masks.sort(key=lambda nail: nail.centroid)
        for nail_id, nail in enumerate(masks, start=1):
            nail.nail_id = nail_id
        return masks


def annotate(frame, nails):
    frame = frame.copy()
    for nail in nails:
        visible = nail.mask != 0
        frame[visible] = (0.55 * frame[visible] + 0.45 * np.array([60, 230, 90])).astype(np.uint8)
        u, v = (round(value) for value in nail.centroid)
        cv2.circle(frame, (u, v), 4, (0, 0, 255), -1)
        cv2.putText(frame, str(nail.nail_id), (u + 5, v), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


def main():
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Vista previa de uñas segmentadas sin calibración")
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path, default=Path("models/nail-seg.onnx"))
    parser.add_argument("--output", type=Path, default=Path("data/deteccion_onnx.png"))
    args = parser.parse_args()
    frame = cv2.imread(str(args.image))
    if frame is None:
        parser.error("No se pudo leer la imagen")
    nails = OnnxNailSegmenter(args.model).segment(frame)
    frame = annotate(frame, nails)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), frame):
        parser.error(f"No se pudo guardar {args.output}")
    print(f"{len(nails)} uñas detectadas. Vista previa: {args.output}")


if __name__ == "__main__":
    main()
