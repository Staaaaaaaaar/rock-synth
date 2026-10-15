"""Small user-facing configuration; paths are relative to the project root."""

from copy import deepcopy
from math import isfinite
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = {
    "seed": 42,
    "num_scenes": 1,
    "rocks": {"directory": "assets/rocks", "count": [12, 20], "diameter": [0.2, 0.8]},
    "terrain": {"size": 10.0, "relief": 0.15, "textures": "assets/surfaces"},
    "camera": {
        "fov": 60.0,
        "poses": [
            {"position": [0, -4, 4], "look_at": [0, 0, 0]},
            {"position": [4, 0, 4], "look_at": [0, 0, 0]},
            {"position": [0, 4, 4], "look_at": [0, 0, 0]},
        ],
    },
    "lighting": {"random": True},
    "output": {"directory": "output/dataset", "resolution": [640, 480]},
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


def load_config(path=ROOT / "configs/default.yaml"):
    with Path(path).open(encoding="utf-8") as handle:
        supplied = yaml.safe_load(handle)
    if not isinstance(supplied, dict):
        raise ConfigError("configuration must be a mapping")
    config = deepcopy(DEFAULTS)
    for key, value in supplied.items():
        if key not in config:
            raise ConfigError(f"unknown option: {key}")
        if isinstance(config[key], dict):
            if not isinstance(value, dict) or set(value) - set(config[key]):
                raise ConfigError(f"invalid or unknown options in {key}")
            config[key].update(value)
        else:
            config[key] = value
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
    for section, field in (("rocks", "directory"), ("terrain", "textures"), ("output", "directory")):
        value = config[section][field]
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{section}.{field} must be a non-empty path")
        config[section][field] = str((ROOT / Path(value).expanduser()).resolve())
    return config
