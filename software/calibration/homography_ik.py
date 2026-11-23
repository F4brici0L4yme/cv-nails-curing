"""Planar calibration and analytical two-link inverse kinematics."""

from dataclasses import dataclass
import math

import cv2
import numpy as np


class Homography:
    def __init__(self, image_points, world_points):
        image = np.asarray(image_points, dtype=np.float32)
        world = np.asarray(world_points, dtype=np.float32)
        for points in (image, world):
            if points.shape != (4, 2) or not np.isfinite(points).all():
                raise ValueError("Expected four finite coordinate pairs")
            hull = cv2.convexHull(points)
            if len(hull) != 4 or cv2.contourArea(hull) <= 0:
                raise ValueError("Calibration points must form a convex quadrilateral")
        self.matrix = cv2.getPerspectiveTransform(image, world)
        if not np.isfinite(self.matrix).all() or np.linalg.matrix_rank(self.matrix) != 3:
            raise ValueError("Degenerate homography")
        denominators = np.column_stack((image, np.ones(4))) @ self.matrix[2]
        if not (np.all(denominators > 0) or np.all(denominators < 0)):
            raise ValueError("Calibration point correspondence crosses the projective horizon")

    @classmethod
    def from_aruco(cls, frame, markers, dictionary="DICT_4X4_50"):
        """Use one configured corner per marker, on the same plane as the nails."""
        marker_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary))
        detector = cv2.aruco.ArucoDetector(marker_dict, cv2.aruco.DetectorParameters())
        corners, ids, _ = detector.detectMarkers(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        detected = {} if ids is None else dict(zip(ids.ravel().tolist(), corners))
        if len(markers) != 4 or len({item["id"] for item in markers}) != 4:
            raise ValueError("Expected four distinct ArUco IDs")
        image = []
        for item in markers:
            marker_id, corner = item["id"], item["corner"]
            if marker_id not in detected or corner not in range(4):
                raise ValueError(f"Missing or invalid ArUco corner for marker {marker_id}")
            image.append(detected[marker_id].reshape(4, 2)[corner])
        return cls(image, [item["world_mm"] for item in markers])

    @staticmethod
    def transform(points, matrix):
        points = np.asarray(points, dtype=np.float64).reshape(-1, 2)
        projected = np.column_stack((points, np.ones(len(points)))) @ matrix.T
        if not np.isfinite(projected).all() or np.any(np.abs(projected[:, 2]) < 1e-12):
            raise ValueError("Point outside the valid projective plane")
        return projected[:, :2] / projected[:, 2, None]

    def to_world(self, points):
        return self.transform(points, self.matrix)

    def to_image(self, points):
        return self.transform(points, np.linalg.inv(self.matrix))

    def reprojection_errors_mm(self, image_points, reference_mm):
        reference = np.asarray(reference_mm, dtype=float)
        projected = self.to_world(image_points)
        if not len(projected) or projected.shape != reference.shape or not np.isfinite(reference).all():
            raise ValueError("Provide paired independent grid points")
        return np.linalg.norm(projected - reference, axis=1)


@dataclass(frozen=True)
class Arm:
    lengths_mm: tuple
    origin_mm: tuple
    workspace_mm: tuple
    joint_limits_deg: tuple
    elbow: int = 1

    def __post_init__(self):
        l1, l2 = self.lengths_mm
        x0, y0 = self.origin_mm
        xmin, ymin, xmax, ymax = self.workspace_mm
        (j1min, j1max), (j2min, j2max) = self.joint_limits_deg
        values = (l1, l2, x0, y0, xmin, ymin, xmax, ymax, j1min, j1max, j2min, j2max)
        if not all(map(math.isfinite, values)) or min(l1, l2) <= 0:
            raise ValueError("Invalid arm geometry")
        if xmin >= xmax or ymin >= ymax or j1min >= j1max or j2min >= j2max:
            raise ValueError("Invalid workspace or joint limits")
        if self.elbow not in (-1, 1):
            raise ValueError("Invalid elbow branch")

    def solve(self, point_mm):
        x, y = point_mm
        xmin, ymin, xmax, ymax = self.workspace_mm
        if not (xmin <= x <= xmax and ymin <= y <= ymax):
            raise ValueError("Target outside workspace")
        x -= self.origin_mm[0]
        y -= self.origin_mm[1]
        l1, l2 = self.lengths_mm
        cos2 = (x*x + y*y - l1*l1 - l2*l2) / (2*l1*l2)
        if abs(cos2) > 1 + 1e-9 or math.hypot(x, y) < 1e-9:
            raise ValueError("Target outside arm reach or at an ambiguous origin")
        theta2 = self.elbow * math.acos(max(-1, min(1, cos2)))
        theta1 = math.atan2(y, x) - math.atan2(l2 * math.sin(theta2), l1 + l2 * math.cos(theta2))
        angles = ((math.degrees(theta1) + 180) % 360 - 180, math.degrees(theta2))
        if any(not low <= value <= high
               for value, (low, high) in zip(angles, self.joint_limits_deg)):
            raise ValueError("Target exceeds joint limits")
        return angles


def main():
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Validate calibration on independent grid points")
    parser.add_argument("config", type=Path)
    parser.add_argument("grid", type=Path, help="JSON with image_px and reference_mm arrays")
    parser.add_argument("--image", type=Path, help="Calibration image for ArUco")
    args = parser.parse_args()
    calibration = json.loads(args.config.read_text())["calibration"]
    if "image_px" in calibration:
        mapper = Homography(calibration["image_px"], calibration["world_mm"])
    else:
        image = cv2.imread(str(args.image)) if args.image else None
        if image is None:
            parser.error("Provide a readable --image for ArUco")
        mapper = Homography.from_aruco(image, calibration["markers"],
                                      calibration.get("dictionary", "DICT_4X4_50"))
    grid = json.loads(args.grid.read_text())
    fitted = {tuple(point) for point in calibration.get("image_px", [])}
    if any(tuple(point) in fitted for point in grid["image_px"]):
        parser.error("Grid must exclude fitting points")
    errors = mapper.reprojection_errors_mm(grid["image_px"], grid["reference_mm"])
    print(json.dumps(dict(n=len(errors), mean_mm=float(errors.mean()),
                          sample_sd_mm=float(errors.std(ddof=1)) if len(errors) > 1 else None,
                          rmse_mm=float(np.sqrt(np.mean(errors**2))), max_mm=float(errors.max()),
                          point_errors_mm=errors.tolist()), indent=2))
    return int(errors.max() >= 1.5)


if __name__ == "__main__":
    raise SystemExit(main())
