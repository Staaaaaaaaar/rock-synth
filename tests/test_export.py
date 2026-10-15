import cv2
import numpy as np
import pytest
from PIL import Image

from rocksynth.export import save_frame, yolo_labels


def test_disconnected_regions_are_one_instance_with_both_regions_preserved():
    mask = np.zeros((100, 120), dtype=np.int32)
    mask[10:40, 10:40] = 7
    mask[50:80, 70:100] = 7
    lines = yolo_labels(mask)
    assert len(lines) == 1
    values = lines[0].split()
    assert values[0] == "0"
    coordinates = np.array(values[1:], dtype=float).reshape(-1, 2)
    assert np.all((coordinates >= 0) & (coordinates <= 1))
    polygon = np.rint(coordinates * [120, 100]).astype(np.int32)
    restored = np.zeros_like(mask, dtype=np.uint8)
    cv2.fillPoly(restored, [polygon], 1)
    overlap = np.count_nonzero(restored & (mask > 0)) / np.count_nonzero(restored | (mask > 0))
    assert overlap > 0.95


def test_empty_and_tiny_instances():
    mask = np.zeros((20, 20), dtype=np.int32)
    assert yolo_labels(mask) == []
    mask[3, 3] = 1
    assert yolo_labels(mask) == []


def test_multiple_ids_remain_distinct_and_file_pair_is_saved(tmp_path):
    mask = np.zeros((40, 40), dtype=np.int32)
    mask[3:15, 3:15] = 10
    mask[20:35, 20:35] = 42
    rgb = np.zeros((40, 40, 3), dtype=np.uint8)
    assert save_frame(tmp_path, "0000-0000", rgb, mask) == 2
    assert Image.open(tmp_path / "images/train/0000-0000.png").size == (40, 40)
    assert len((tmp_path / "labels/train/0000-0000.txt").read_text().splitlines()) == 2
    with pytest.raises(FileExistsError):
        save_frame(tmp_path, "0000-0000", rgb, mask)


def test_bad_array_contract_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="shapes differ"):
        save_frame(tmp_path, "bad", np.zeros((3, 4, 3), dtype=np.uint8), np.zeros((3, 3), dtype=int))
    with pytest.raises(ValueError, match="integer"):
        yolo_labels(np.zeros((4, 4), dtype=float))
