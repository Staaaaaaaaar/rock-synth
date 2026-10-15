"""Small user-facing configuration; paths are relative to the project root."""

from copy import deepcopy
from math import isclose, isfinite
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = {
    "seed": 42,
    "num_scenes": 1,
    "rocks": {"directory": "assets/rocks", "count": [12, 20], "diameter": [0.2, 0.8], "placement_radius": 3.5},
    "terrain": {"size": 20.0, "relief": 0.15, "texture_size": 4.0, "textures": "assets/surfaces"},
    "camera": {
        "fov": 50.0,
        "poses": [
            {"position": [0, -3, 4], "look_at": [0, 0, 0]},
            {"position": [3, 0, 4], "look_at": [0, 0, 0]},
            {"position": [0, 3, 4], "look_at": [0, 0, 0]},
        ],
    },
    "lighting": {"random": True},
    "output": {
        "directory": "output/dataset",
        "resolution": [640, 480],
        "format": "yolo",
        "save_config": True,
        "yolo": {"split": {"train": 1.0, "val": 0.0, "test": 0.0}},
    },
}


class ConfigError(ValueError):
    """Invalid public configuration."""


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and isfinite(value)


def _range(value, name, integer=False):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = [value, value]
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(_number(v) and v > 0 for v in value)
        or value[0] > value[1]
        or (integer and not all(type(v) is int for v in value))
    ):
        raise ConfigError(f"{name} must be positive {'integer ' if integer else ''}values [min, max]")
    return value


def _merge(config, supplied, prefix=""):
    if not isinstance(supplied, dict):
        raise ConfigError(f"{prefix or 'configuration'} must be a mapping")
    for key, value in supplied.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if key not in config:
            raise ConfigError(f"unknown option: {name}")
        if isinstance(config[key], dict):
            _merge(config[key], value, name)
        else:
            config[key] = value


def load_config(path=ROOT / "configs/default.yaml"):
    with Path(path).open(encoding="utf-8") as handle:
        supplied = yaml.safe_load(handle)
    config = deepcopy(DEFAULTS)
    _merge(config, supplied)
    if type(config["seed"]) is not int or config["seed"] < 0:
        raise ConfigError("seed must be a non-negative integer")
    if type(config["num_scenes"]) is not int or config["num_scenes"] < 1:
        raise ConfigError("num_scenes must be a positive integer")
    rocks = config["rocks"]
    rocks["count"] = _range(rocks["count"], "rocks.count", integer=True)
    rocks["diameter"] = _range(rocks["diameter"], "rocks.diameter")
    terrain = config["terrain"]
    if not _number(terrain["size"]) or terrain["size"] <= 0:
        raise ConfigError("terrain.size must be positive")
    if not _number(terrain["relief"]) or terrain["relief"] < 0:
        raise ConfigError("terrain.relief must be non-negative")
    if not _number(terrain["texture_size"]) or terrain["texture_size"] <= 0:
        raise ConfigError("terrain.texture_size must be positive")
    if not _number(rocks["placement_radius"]) or not 0 < rocks["placement_radius"] <= terrain["size"] / 2:
        raise ConfigError("rocks.placement_radius must be positive and no larger than terrain.size / 2")
    camera = config["camera"]
    if not _number(camera["fov"]) or not 1 < camera["fov"] < 179:
        raise ConfigError("camera.fov must be between 1 and 179 degrees")
    if not isinstance(camera["poses"], list) or not camera["poses"]:
        raise ConfigError("camera.poses must be a non-empty list")
    for pose in camera["poses"]:
        if not isinstance(pose, dict) or set(pose) != {"position", "look_at"}:
            raise ConfigError("each camera pose needs only position and look_at")
        for vector in pose.values():
            if not isinstance(vector, list) or len(vector) != 3 or not all(_number(v) for v in vector):
                raise ConfigError("camera position and look_at must be finite XYZ vectors")
        if pose["position"] == pose["look_at"]:
            raise ConfigError("camera position and look_at must differ")
    resolution = config["output"]["resolution"]
    if not isinstance(resolution, list) or len(resolution) != 2 or any(type(v) is not int or v < 1 for v in resolution):
        raise ConfigError("output.resolution must be positive integers [width, height]")
    if type(config["lighting"]["random"]) is not bool:
        raise ConfigError("lighting.random must be true or false")
    output = config["output"]
    if output["format"] != "yolo":
        raise ConfigError("output.format currently supports only 'yolo'")
    if type(output["save_config"]) is not bool:
        raise ConfigError("output.save_config must be true or false")
    ratios = output["yolo"]["split"].values()
    if not all(_number(value) and 0 <= value <= 1 for value in ratios) or not isclose(sum(ratios), 1, abs_tol=1e-8):
        raise ConfigError("output.yolo.split ratios must be between 0 and 1 and sum to 1")
    for section, field in (("rocks", "directory"), ("terrain", "textures"), ("output", "directory")):
        value = config[section][field]
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{section}.{field} must be a non-empty path")
        config[section][field] = str((ROOT / Path(value).expanduser()).resolve())
    return config
