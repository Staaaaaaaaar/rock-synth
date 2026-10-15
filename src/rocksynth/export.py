"""Direct YOLO segmentation export from one integer instance image."""

from pathlib import Path
from random import Random

import cv2
import numpy as np
import yaml
from PIL import Image

from rocksynth.config import ConfigError

SPLITS = ("train", "val", "test")


def scene_splits(num_scenes, ratios, seed):
    """Allocate whole scenes by largest remainder, then shuffle independently."""
    total = sum(ratios.values())
    targets = [num_scenes * ratios[name] / total for name in SPLITS]
    counts = [int(value) for value in targets]
    order = sorted(range(len(SPLITS)), key=lambda index: targets[index] - counts[index], reverse=True)
    for index in order[: num_scenes - sum(counts)]:
        counts[index] += 1
    empty = [name for name, count in zip(SPLITS, counts, strict=True) if ratios[name] > 0 and count == 0]
    if empty:
        raise ConfigError(
            f"No scenes allocated to {', '.join(empty)}; increase num_scenes, adjust ratios, or set them to 0"
        )
    assignments = [name for name, count in zip(SPLITS, counts, strict=True) for _ in range(count)]
    Random(seed).shuffle(assignments)
    return assignments


def prepare_output(config):
    options = config["output"]
    assignments = scene_splits(config["num_scenes"], options["yolo"]["split"], config["seed"])
    directory = Path(options["directory"])
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(f"Output directory is not empty; choose another --output: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    dataset = {"path": str(directory.resolve()), "names": {0: "rock"}}
    for split in SPLITS:
        if split not in assignments:
            continue
        for kind in ("images", "labels"):
            (directory / kind / split).mkdir(parents=True, exist_ok=True)
        dataset[split] = f"images/{split}"
    (directory / "data.yaml").write_text(yaml.safe_dump(dataset, sort_keys=False), encoding="utf-8")
    if options["save_config"]:
        (directory / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return assignments


def _join_contours(contours):
    """Connect disconnected visible regions with a doubled, zero-area bridge."""
    polygon = contours[0]
    for contour in contours[1:]:
        best = None
        for index, point in enumerate(polygon):
            distances = np.sum((contour.astype(float) - point) ** 2, axis=1)
            other = int(np.argmin(distances))
            candidate = (float(distances[other]), index, other)
            if best is None or candidate < best:
                best = candidate
        _, index, other = best
        cycle = np.concatenate([contour[other:], contour[: other + 1]])
        polygon = np.concatenate([polygon[: index + 1], cycle, polygon[index:]])
    return polygon


def yolo_labels(instance_ids):
    if instance_ids.ndim != 2 or not np.issubdtype(instance_ids.dtype, np.integer) or np.any(instance_ids < 0):
        raise ValueError("instance_ids must be a non-negative integer HxW array")
    height, width = instance_ids.shape
    labels = []
    for rock_id in np.unique(instance_ids):
        if rock_id == 0:
            continue
        mask = (instance_ids == rock_id).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [
            cv2.approxPolyDP(c, min(1.0, 0.001 * cv2.arcLength(c, True)), True).reshape(-1, 2)
            for c in contours
            if cv2.contourArea(c) > 0
        ]
        contours = [c for c in contours if len(c) >= 3]
        if not contours:
            continue
        contours.sort(key=lambda c: (-abs(cv2.contourArea(c)), int(c[:, 0].min()), int(c[:, 1].min())))
        polygon = _join_contours(contours).astype(float) / [width, height]
        labels.append("0 " + " ".join(f"{v:.6f}" for v in polygon.flat))
    return labels


def save_frame(output_dir, frame_id, rgb, instance_ids, split="train"):
    if split not in SPLITS:
        raise ValueError(f"Unknown dataset split: {split}")
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] not in (3, 4):
        raise ValueError("rgb must be a uint8 HxWx3/4 array")
    if rgb.shape[:2] != instance_ids.shape:
        raise ValueError("RGB and instance image shapes differ")
    labels = yolo_labels(instance_ids)
    directory = Path(output_dir)
    image_path = directory / "images" / split / f"{frame_id}.png"
    label_path = directory / "labels" / split / f"{frame_id}.txt"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    if image_path.exists() or label_path.exists():
        raise FileExistsError(f"Frame already exists: {frame_id}")
    Image.fromarray(rgb[:, :, :3]).save(image_path)
    label_path.write_text("\n".join(labels) + ("\n" if labels else ""), encoding="utf-8")
    return len(labels)
