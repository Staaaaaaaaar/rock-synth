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
