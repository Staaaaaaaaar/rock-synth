import pytest
import yaml

from rocksynth.config import ROOT, ConfigError, load_config


def test_defaults_and_project_relative_paths():
    config = load_config()
    assert config["rocks"]["directory"] == str(ROOT / "assets/rocks")
    assert len(config["camera"]["poses"]) == 3


@pytest.mark.parametrize(
    "override",
    [
        {"rocks": {"diameter": [0, 1]}},
        {"rocks": {"count": [1, 2.5]}},
        {"camera": {"poses": [{"position": [0, 0, 0], "look_at": [0, 0, 0]}]}},
        {"camera": {"poses": []}},
        {"num_scenes": 0},
        {"seed": True},
        {"camera": {"poses": [{"position": [0, 0, float("nan")], "look_at": [0, 1, 0]}]}},
        {"render": {"samples": 100}},
        {"rocks": {"asset_manifest": "unused"}},
        {"rocks": {"placement_radius": 0}},
        {"rocks": {"placement_radius": 11}},
        {"terrain": {"texture_size": 0}},
        {"output": {"format": "coco"}},
        {"output": {"save_config": "false"}},
        {"output": {"yolo": {"split": {"train": 0.7, "val": 0.2}}}},
        {"output": {"yolo": {"split": {"train": 1.1, "val": -0.1}}}},
        {"output": {"yolo": {"split": {"train": float("nan")}}}},
        {"output": {"yolo": {"split": {"train": True}}}},
        {"output": {"yolo": {"split": {"validation": 0.2}}}},
        {"output": {"yolo": []}},
    ],
)
def test_invalid_configuration_fails_early(tmp_path, override):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(override))
    with pytest.raises(ConfigError):
        load_config(path)


def test_fixed_count_and_size_are_accepted(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("rocks:\n  count: 4\n  diameter: 0.5\n")
    config = load_config(path)
    assert config["rocks"]["count"] == [4, 4]
    assert config["rocks"]["diameter"] == [0.5, 0.5]


def test_ground_size_does_not_change_rock_field_radius(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("terrain:\n  size: 30\n")
    config = load_config(path)
    assert config["rocks"]["placement_radius"] == 3.5


def test_nested_output_defaults_are_merged_without_changing_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("output:\n  save_config: false\n  yolo:\n    split:\n      train: 0.8\n      val: 0.2\n")
    config = load_config(path)
    assert config["output"]["format"] == "yolo"
    assert config["output"]["save_config"] is False
    assert config["output"]["yolo"]["split"] == {"train": 0.8, "val": 0.2, "test": 0.0}
    defaults_path = tmp_path / "defaults.yaml"
    defaults_path.write_text("{}")
    assert load_config(defaults_path)["output"]["yolo"]["split"]["train"] == 1.0
