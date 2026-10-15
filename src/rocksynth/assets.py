"""Discover local assets by their documented filenames, without a registry."""

from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"}


def scan_rocks(directory):
    paths = sorted(Path(directory).rglob("*.blend"))
    if not paths:
        raise FileNotFoundError(f"No .blend assets in {directory}; run scripts/import_assets.py first")
    return paths


def scan_surfaces(directory):
    surfaces = []
    for folder in sorted(Path(directory).glob("*")):
        if not folder.is_dir():
            continue
        maps = {}
        for channel in ("basecolor", "roughness", "normal", "displacement"):
            matches = sorted(p for p in folder.glob(f"{channel}.*") if p.suffix.lower() in IMAGE_SUFFIXES)
            if len(matches) > 1:
                raise ValueError(f"Multiple {channel} maps in {folder}")
            if matches:
                maps[channel] = matches[0]
        if "basecolor" not in maps:
            raise ValueError(f"Missing basecolor image in surface {folder}")
        surfaces.append(maps)
    if not surfaces:
        raise FileNotFoundError(f"No surface directories in {directory}; run scripts/import_assets.py first")
    return surfaces
