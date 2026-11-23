"""Export segmentation, targeting and skin exposure metrics for captured runs."""

import argparse
import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from software.calibration.homography_ik import Homography
from software.vision.segmenter import nail_from_mask


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_instances(bundle, shape=None):
    masks = bundle["masks"]
    ids = bundle["ids"].tolist()
    if (masks.ndim != 3 or len(ids) != len(masks) or len(set(ids)) != len(ids)
            or any(type(nail_id) is not int or nail_id < 1 for nail_id in ids)
            or (shape is not None and any(nail_id > 5 for nail_id in ids))
            or (shape is not None and masks.shape[1:] != shape)):
        raise ValueError("Invalid nail mask bundle")
    return masks.shape[1:], dict(zip(ids, masks != 0))


def exposure(mapper, bbox, nails, spots, radius, skin_mask=None, step=0.20):
    """Rasterize in millimeters, using the hand bounding box as the baseline ROI."""
    left, top, right, bottom = bbox
    if not (0 <= left < right <= nails.shape[1] and 0 <= top < bottom <= nails.shape[0]):
        raise ValueError("Hand bounding box is outside the image")
    corners = mapper.to_world([(left, top), (right, top), (right, bottom), (left, bottom)])
    lo = corners.min(axis=0)
    hi = corners.max(axis=0)
    if math.prod(np.ceil((hi-lo)/step)) > 5_000_000:
        raise ValueError("Hand grid exceeds raster size limit")
    xs = np.arange(lo[0] + step/2, hi[0], step)
    ys = np.arange(lo[1] + step/2, hi[1], step)
    grid = np.column_stack([axis.ravel() for axis in np.meshgrid(xs, ys)])
    if not len(grid):
        raise ValueError("Hand grid is empty")
    uv = mapper.to_image(grid)
    in_box = ((left <= uv[:, 0]) & (uv[:, 0] < right) &
              (top <= uv[:, 1]) & (uv[:, 1] < bottom))
    uv = np.floor(uv[in_box]).astype(int)
    grid = grid[in_box]
    u, v = uv.T
    skin = ~nails[v, u]
    if skin_mask is not None:
        skin &= skin_mask[v, u]
    lit = np.zeros(len(grid), dtype=bool)
    for center in spots:
        lit |= np.sum((grid - center)**2, axis=1) <= radius**2
    baseline = skin.sum() * step**2
    selective = (skin & lit).sum() * step**2
    serr = 100 * (1 - selective / baseline) if baseline else None
    return float(baseline), float(selective), serr


def evaluate(path, reference_path, fallback_bbox):
    with np.load(path, allow_pickle=False) as bundle:
        shape, predicted = load_instances(bundle)
        mapper = Homography.__new__(Homography)
        mapper.matrix = np.asarray(bundle["matrix"], dtype=float)
        if (mapper.matrix.shape != (3, 3) or not np.isfinite(mapper.matrix).all()
                or np.linalg.matrix_rank(mapper.matrix) != 3):
            raise ValueError("Invalid calibration matrix")
        source = str(bundle["source"].item())
        radius = float(bundle["spot_radius_mm"])
        if not 0 < radius < math.inf:
            raise ValueError("Invalid spot radius")
        confidence = dict(zip(predicted, bundle["confidence"], strict=True))
        bbox = tuple(bundle["hand_bbox_px"]) if "hand_bbox_px" in bundle else fallback_bbox

    truth = {}
    skin = None
    measured = {}
    if reference_path is not None:
        with np.load(reference_path, allow_pickle=False) as reference:
            _, truth = load_instances(reference, shape)
            if "hand_bbox_px" in reference:
                bbox = tuple(reference["hand_bbox_px"])
            if "hand_mask" in reference:
                skin = reference["hand_mask"] != 0
                if skin.shape != shape:
                    raise ValueError("Hand mask size differs from capture")
            if "measured_spots_mm" in reference:
                coords = reference["measured_spots_mm"]
                if coords.shape != (len(truth), 2) or not np.isfinite(coords).all():
                    raise ValueError("Provide a finite measured spot for each reference mask")
                measured = dict(zip(truth, coords))
    rows = []
    spots = {}
    for nail_id in sorted(predicted.keys() | truth.keys()):
        mask = predicted.get(nail_id)
        label = truth.get(nail_id)
        estimated_error = measured_error = iou = score = None
        if mask is not None:
            spots[nail_id] = mapper.to_world([nail_from_mask(nail_id, mask).centroid])[0]
            score = confidence[nail_id]
            score = float(score) if np.isfinite(score) else None
        if label is not None:
            center = mapper.to_world([nail_from_mask(nail_id, label).centroid])[0]
            if mask is not None:
                estimated_error = float(np.linalg.norm(spots[nail_id] - center))
            if nail_id in measured:
                measured_error = float(np.linalg.norm(measured[nail_id] - center))
        if reference_path is not None:
            if label is None or mask is None:
                iou = 0.0
            else:
                iou = float(np.logical_and(mask, label).sum() / np.logical_or(mask, label).sum())
        rows.append(dict(capture=path.stem, source=source, nail_id=nail_id, confidence=score,
                         iou=iou, centroid_error_mm=estimated_error,
                         measured_targeting_error_mm=measured_error))
    area_rows = []
    if bbox is not None and spots.keys() == set(range(1, 6)):
        masks = truth if reference_path is not None else predicted
        nail_union = np.logical_or.reduce(list(masks.values())) if masks else np.zeros(shape, bool)
        for method, centers in (("planned_spots", spots), ("measured_centers", measured)):
            if centers.keys() != spots.keys():
                continue
            baseline, selective, serr = exposure(mapper, bbox, nail_union, list(centers.values()),
                                                  radius, skin)
            area_rows.append(dict(capture=path.stem, source=source, method=method,
                                  region="hand_mask" if skin is not None else "bbox_proxy",
                                  nail_masks="annotated" if reference_path is not None else "predicted",
                                  baseline_mm2=baseline, selective_mm2=selective, serr_pct=serr))
    return rows, area_rows


def summarize(rows, metrics, keys):
    groups = sorted({tuple(row[key] for key in keys) for row in rows})
    for group in groups:
        for metric in metrics:
            values = [row[metric] for row in rows if tuple(row[key] for key in keys) == group
                      and row[metric] is not None]
            if values:
                yield dict(zip(keys, group), metric=metric, n=len(values),
                           mean=float(np.mean(values)),
                           sample_sd=float(np.std(values, ddof=1)) if len(values) > 1 else None)


def plot_exposure(rows, output):
    groups = sorted({(row["source"], row["method"], row["region"], row["nail_masks"]) for row in rows})
    for index, group in enumerate(groups, start=1):
        source, method, region, mask_kind = group
        selected = [row for row in rows
                    if tuple(row[key] for key in ("source", "method", "region", "nail_masks")) == group]
        series = [[row[key] for row in selected] for key in ("baseline_mm2", "selective_mm2")]
        means = [np.mean(values) for values in series]
        errors = [np.std(values, ddof=1) if len(values) > 1 else 0 for values in series]
        fig, ax = plt.subplots(figsize=(3.45, 2.45), layout="constrained")
        ax.bar(["Full-hand", "Selective"], means, yerr=errors, capsize=3,
               color=["#485974", "#27816e"])
        ax.set_ylabel("Exposed area (mm²)")
        ax.set_title(f"{source} · {method.replace('_', ' ')}", fontsize=9)
        ax.text(.98, .96, f"{region.replace('_', ' ')}\n{mask_kind} masks (n={len(selected)})",
                transform=ax.transAxes, ha="right", va="top", fontsize=7)
        ax.spines[["top", "right"]].set_visible(False)
        fig.savefig(output / f"exposure_{index}.png", dpi=300)
        fig.savefig(output / f"exposure_{index}.pdf")
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", nargs="+", type=Path)
    parser.add_argument("--references", type=Path, help="Directory with same-name NPZ annotations")
    parser.add_argument("--hand-bbox", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    parser.add_argument("--log", type=Path, help="Controller CSV for curing duration statistics")
    parser.add_argument("--output", type=Path, default=Path("data/evaluation"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    nails, areas = [], []
    for capture in args.captures:
        annotation = args.references / capture.name if args.references else None
        rows, areas_for_capture = evaluate(capture, annotation, args.hand_bbox)
        nails.extend(rows)
        areas.extend(areas_for_capture)
    nail_metrics = ("confidence", "iou", "centroid_error_mm", "measured_targeting_error_mm")
    area_metrics = ("baseline_mm2", "selective_mm2", "serr_pct")
    write_csv(args.output / "nails.csv", ("capture", "source", "nail_id", *nail_metrics), nails)
    groups = ("source", "method", "region", "nail_masks")
    write_csv(args.output / "exposure.csv", ("capture", *groups, *area_metrics), areas)
    write_csv(args.output / "nail_summary.csv", ("source", "metric", "n", "mean", "sample_sd"),
              summarize(nails, nail_metrics, ("source",)))
    write_csv(args.output / "exposure_summary.csv", (*groups, "metric", "n", "mean", "sample_sd"),
              summarize(areas, area_metrics, groups))
    if args.log:
        with args.log.open(newline="", encoding="utf-8") as handle:
            durations = [dict(source=row["source"], actual_ms=float(row["actual_ms"]),
                              duration_error_ms=float(row["actual_ms"]) - float(row["duration_ms"]))
                         for row in csv.DictReader(handle) if row["status"] == "DONE"]
        write_csv(args.output / "duration_summary.csv", ("source", "metric", "n", "mean", "sample_sd"),
                  summarize(durations, ("actual_ms", "duration_error_ms"), ("source",)))
    plot_exposure(areas, args.output)


if __name__ == "__main__":
    main()
