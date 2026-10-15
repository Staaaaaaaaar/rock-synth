import blenderproc as bproc

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from rocksynth.assets import scan_rocks, scan_surfaces
from rocksynth.config import load_config
from rocksynth.export import prepare_output, save_frame
from rocksynth.render import render_views
from rocksynth.scene import build_scene


def main():
    parser = argparse.ArgumentParser(description="Generate rock scenes, each with every configured camera view.")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/default.yaml")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.seed is not None:
        if args.seed < 0:
            parser.error("--seed must be non-negative")
        config["seed"] = args.seed
    if args.output is not None:
        config["output"]["directory"] = str((ROOT / args.output.expanduser()).resolve())
    rock_paths = scan_rocks(config["rocks"]["directory"])
    surfaces = scan_surfaces(config["terrain"]["textures"])
    output = Path(config["output"]["directory"])
    splits = prepare_output(config)
    bproc.init()
    for scene_index, split in enumerate(splits):
        if scene_index:
            bproc.clean_up()
        seed = config["seed"] + scene_index
        import bpy

        bpy.context.scene.cycles.seed = seed % (2**31)
        build_scene(bproc, config, rock_paths, surfaces, seed)
        images, masks = render_views(bproc, config)
        if len(images) != len(config["camera"]["poses"]) or len(masks) != len(images):
            raise RuntimeError("Renderer returned an unexpected number of views")
        for view_index, (rgb, mask) in enumerate(zip(images, masks, strict=True)):
            frame_id = f"{scene_index:04d}-{view_index:04d}"
            save_frame(output, frame_id, np.asarray(rgb), np.asarray(mask), split=split)
        print(f"Scene {scene_index + 1}/{config['num_scenes']}: {len(images)} views -> {split} in {output}")


if __name__ == "__main__":
    main()
