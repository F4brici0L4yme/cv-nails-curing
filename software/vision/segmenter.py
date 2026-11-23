"""Detect fingertips with MediaPipe and refine nail masks with local contours."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
import time

import cv2
import numpy as np


@dataclass
class Nail:
    nail_id: int
    mask: np.ndarray
    centroid: tuple[float, float]
    radius_px: float
    confidence: float | None = None


def nail_from_mask(nail_id, mask, confidence=None):
    mask = np.asarray(mask != 0, dtype=np.uint8)
    moments = cv2.moments(mask, binaryImage=True)
    area = moments["m00"]
    if not area:
        raise ValueError("Nail mask is empty")
    centroid = (moments["m10"] / area, moments["m01"] / area)
    return Nail(nail_id, mask, centroid, math.sqrt(area / math.pi), confidence)


class BaseNailSegmenter(ABC):
    @abstractmethod
    def segment(self, frame: np.ndarray) -> list[Nail]:
        """Return masks in the input frame coordinates, with sequential IDs."""


class PretrainedNailSegmenter(BaseNailSegmenter):
    def __init__(self, model_path):
        import mediapipe as mp

        self.mp = mp
        vision = mp.tasks.vision
        self.detector = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
            )
        )
        self.last_ms = -1

    def close(self):
        self.detector.close()

    def segment(self, frame):
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        now_ms = max(self.last_ms + 1, time.monotonic_ns() // 1_000_000)
        self.last_ms = now_ms
        result = self.detector.detect_for_video(
            self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), now_ms
        )
        if not result.hand_landmarks:
            return []
        points = np.array([(p.x * width, p.y * height) for p in result.hand_landmarks[0]])
        nails = []
        for nail_id, tip in enumerate((4, 8, 12, 16, 20), start=1):
            nail = self._refine(frame, nail_id, points[tip], points[tip - 1])
            if nail is not None:
                nails.append(nail)
        return nails

    @staticmethod
    def _refine(frame, nail_id, tip, joint):
        direction = tip - joint
        length = np.linalg.norm(direction)
        if not np.isfinite(length) or length < 6:
            return None
        center = tip - 0.20 * direction
        margin = int(np.ceil(0.65 * length))
        cx, cy = np.rint(center).astype(int)
        height, width = frame.shape[:2]
        x0, y0 = max(0, cx-margin), max(0, cy-margin)
        x1, y1 = min(width, cx+margin+1), min(height, cy+margin+1)
        if x0 >= x1 or y0 >= y1:
            return None
        crop = frame[y0:y1, x0:x1]
        lightness = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)[:, :, 0]
        edges = cv2.Canny(cv2.GaussianBlur(lightness, (3, 3), 0), 25, 65)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        local_center = (float(center[0] - x0), float(center[1] - y0))
        best = None
        best_score = 0
        expected_area = 0.28 * length**2
        for contour in contours:
            area = cv2.contourArea(contour)
            if not 0.08 * length**2 <= area <= 0.60 * length**2:
                continue
            if cv2.pointPolygonTest(contour, local_center, False) < 0:
                continue
            perimeter = cv2.arcLength(contour, True)
            compactness = min(1, 4 * math.pi * area / perimeter**2)
            score = compactness * math.exp(-abs(math.log(area / expected_area)))
            if score > best_score:
                best, best_score = contour, score
        if best is None or best_score < 0.20:
            return None
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.drawContours(mask[y0:y1, x0:x1], [best], -1, 1, cv2.FILLED)
        return nail_from_mask(nail_id, mask, best_score)
