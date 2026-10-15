"""Normalize raw rock models and a PBR surface using Blender, without a manifest.

blender --background --python scripts/import_assets.py -- --rocks PATH --surface PATH
"""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def import_rock(source, destination):
    import bpy
    from mathutils import Vector

    target = destination / f"{source.parent.name}.blend"
    if target.exists():
        raise FileExistsError(f"Asset already exists: {target}")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if source.suffix.lower() == ".obj":
        # Blender's native OBJ defaults match Blender-exported OBJ coordinates.
        bpy.ops.wm.obj_import(filepath=str(source))
    elif source.suffix.lower() in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(source))
    elif source.suffix.lower() == ".blend":
        with bpy.data.libraries.load(str(source), link=False) as (data_from, data_to):
            data_to.objects = data_from.objects
        for obj in data_to.objects:
            if obj is not None:
                bpy.context.collection.objects.link(obj)
    else:
        raise ValueError(f"Unsupported source model: {source}")
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError(f"No mesh in {source}")
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.object
    obj.parent = None
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    minimum = Vector([min(p[i] for p in corners) for i in range(3)])
    maximum = Vector([max(p[i] for p in corners) for i in range(3)])
    longest = max(maximum - minimum)
    if longest <= 0:
        raise ValueError(f"Degenerate mesh: {source}")
    center = (minimum + maximum) / 2
    matrix = obj.matrix_world.copy()
    for vertex in obj.data.vertices:
        vertex.co = (matrix @ vertex.co - center) / longest
    obj.matrix_world.identity()
    obj.name = "rock"
    obj.data.name = "rock"
    if not obj.data.materials:
        raise ValueError(f"Rock has no material: {source}")
    # Embed dependencies so moving the project cannot break source texture paths.
    for image in bpy.data.images:
        if image.source == "FILE":
            image.filepath = str(Path(bpy.path.abspath(image.filepath)).resolve())
            if not Path(image.filepath).is_file():
                raise FileNotFoundError(f"Missing texture in {source}: {image.filepath}")
            image.pack()
    destination.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target), check_existing=False)
    print(f"Imported rock {source.parent.name}", flush=True)


def import_surface(source, destination):
    import bpy
    import numpy as np

    target = destination / source.name
    if target.exists():
        raise FileExistsError(f"Surface directory already exists: {target}")
    aliases = {
        "basecolor": ("basecolor", "diff", "color"),
        "roughness": ("roughness", "rough"),
        "normal": ("normal", "nor_"),
        "displacement": ("displacement", "disp", "height"),
    }
    files = sorted(p for p in source.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".exr", ".tif"})
    maps = {}
    for channel, names in aliases.items():
        matches = [p for p in files if any(name in p.stem.lower() for name in names)]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous {channel} images in {source}: {matches}")
        if matches:
            maps[channel] = matches[0]
    if "basecolor" not in maps:
        raise ValueError(f"Surface needs a basecolor/diff/color image: {source}")
    target.mkdir(parents=True)
    for channel, path in maps.items():
        if channel == "normal" and ("_dx" in path.stem.lower() or "directx" in path.stem.lower()):
            image = bpy.data.images.load(str(path), check_existing=False)
            image.colorspace_settings.name = "Non-Color"
            pixels = np.empty(len(image.pixels), dtype=np.float32)
            image.pixels.foreach_get(pixels)
            pixels[1::4] = 1 - pixels[1::4]
            image.pixels.foreach_set(pixels)
            image.filepath_raw = str(target / "normal.png")
            image.file_format = "PNG"
            image.save()
            bpy.data.images.remove(image)
        else:
            shutil.copy2(path, target / f"{channel}{path.suffix.lower()}")
    print(f"Imported surface {source.name}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rocks", type=Path, help="Raw directories, one rock per child folder")
    parser.add_argument("--collection", help="Rock collection folder; defaults to the raw directory name")
    parser.add_argument("--surface", type=Path, help="One raw PBR texture directory")
    parser.add_argument("--output", type=Path, default=ROOT / "assets")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    if args.rocks is None and args.surface is None:
        parser.error("provide --rocks and/or --surface")
    if args.rocks:
        collection = args.collection or args.rocks.expanduser().resolve().name
        if not collection or collection in {".", ".."} or "/" in collection or "\\" in collection:
            parser.error("--collection must be a single folder name")
        folders = sorted(p for p in args.rocks.expanduser().resolve().iterdir() if p.is_dir())
        if not folders:
            raise ValueError("No rock directories found")
        for folder in folders:
            # Prefer OBJ here: the supplied scan .blend files may hold stale paths.
            candidates = []
            for suffix in (".obj", ".glb", ".gltf", ".blend"):
                candidates = sorted(folder.glob(f"*{suffix}"))
                if candidates:
                    break
            if len(candidates) != 1:
                raise ValueError(f"Expected one source model in {folder}, got {candidates}")
            import_rock(candidates[0], args.output.resolve() / "rocks" / collection)
    if args.surface:
        import_surface(args.surface.expanduser().resolve(), args.output.resolve() / "surfaces")


if __name__ == "__main__":
    main()
