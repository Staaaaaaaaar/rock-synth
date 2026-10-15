import cv2
import numpy as np
import pytest
import yaml
from PIL import Image

from rocksynth.config import ConfigError, load_config
from rocksynth.export import prepare_output, save_frame, scene_splits, yolo_labels


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


def test_split_rounding_is_deterministic_and_uses_all_scenes():
    ratios = {"train": 0.7, "val": 0.2, "test": 0.1}
    splits = scene_splits(11, ratios, 42)
    assert splits == scene_splits(11, ratios, 42)
    assert {name: splits.count(name) for name in ratios} == {"train": 8, "val": 2, "test": 1}
    assert splits != scene_splits(11, ratios, 43)


def test_unrepresentable_split_fails_before_creating_output(tmp_path):
    config = load_config()
    config["output"]["directory"] = str(tmp_path / "dataset")
    config["output"]["yolo"]["split"] = {"train": 0.8, "val": 0.2, "test": 0}
    with pytest.raises(ConfigError, match="increase num_scenes"):
        prepare_output(config)
    assert not (tmp_path / "dataset").exists()


@pytest.mark.parametrize("save_config", [True, False])
def test_complete_dataset_keeps_scene_views_together_and_optional_config(tmp_path, save_config):
    config = load_config()
    config["num_scenes"] = 5
    config["output"].update({"directory": str(tmp_path / "dataset"), "save_config": save_config})
    config["output"]["yolo"]["split"] = {"train": 0.6, "val": 0.2, "test": 0.2}
    splits = prepare_output(config)
    directory = tmp_path / "dataset"
    rgb = np.zeros((20, 30, 3), dtype=np.uint8)
    mask = np.zeros((20, 30), dtype=np.int32)
    mask[2:15, 3:20] = 1
    for scene_index, split in enumerate(splits):
        for view_index in range(2):
            save_frame(directory, f"{scene_index:04d}-{view_index:04d}", rgb, mask, split=split)
    dataset = yaml.safe_load((directory / "data.yaml").read_text())
    scene_sets = {}
    for name, expected_count in (("train", 3), ("val", 1), ("test", 1)):
        images = sorted((directory / dataset[name]).glob("*.png"))
        labels = sorted((directory / "labels" / name).glob("*.txt"))
        assert len(images) == len(labels) == expected_count * 2
        assert [p.stem for p in images] == [p.stem for p in labels]
        scene_sets[name] = {p.stem.split("-")[0] for p in images}
    assert scene_sets["train"].isdisjoint(scene_sets["val"] | scene_sets["test"])
    assert scene_sets["val"].isdisjoint(scene_sets["test"])
    assert (directory / "config.yaml").exists() == save_config
    assert not (directory / "samples.jsonl").exists()
    assert dataset["names"] == {0: "rock"}
    with pytest.raises(FileExistsError):
        prepare_output(config)


def test_disabled_splits_are_not_exported(tmp_path):
    config = load_config()
    config["num_scenes"] = 1
    config["output"]["yolo"]["split"] = {"train": 1.0, "val": 0.0, "test": 0.0}
    config["output"]["directory"] = str(tmp_path)
    assert prepare_output(config) == ["train"]
    dataset = yaml.safe_load((tmp_path / "data.yaml").read_text())
    assert "val" not in dataset and "test" not in dataset
    assert not (tmp_path / "images/val").exists()
