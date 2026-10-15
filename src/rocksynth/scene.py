"""Build one rock field and settle it once, shared by all configured views."""

from math import cos, exp, hypot, log, pi, sin
from random import Random

import numpy as np

from rocksynth.terrain import create_terrain, sample_terrain


def _place(footprints, radius, rng):
    positions = []
    for index, footprint in enumerate(footprints):
        for _ in range(2000):
            angle = rng.uniform(0, 2 * pi)
            distance = radius * rng.random() ** 0.5
            candidate = (distance * cos(angle), distance * sin(angle))
            if hypot(*candidate) + footprint > radius:
                continue
            if all(
                hypot(candidate[0] - x, candidate[1] - y) >= footprint + footprints[j] + 0.04
                for j, (x, y) in enumerate(positions)
            ):
                positions.append(candidate)
                break
        else:
            raise ValueError(f"Cannot place rock {index + 1}; reduce count/diameter or increase terrain.size")
    return positions


def _penetration(obj, terrain):
    import bpy

    evaluated = obj.blender_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", coordinates)
        matrix = np.asarray(evaluated.matrix_world)
        points = coordinates.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
        return float(np.max(terrain.height_at(points[:, 0], points[:, 1]) - points[:, 2], initial=0))
    finally:
        evaluated.to_mesh_clear()


def _validate_clearance(rocks):
    from blenderproc.python.utility.CollisionUtility import CollisionUtility

    cache = {}
    for index, obj in enumerate(rocks):
        for other in rocks[index + 1 :]:
            intersects, cache = CollisionUtility.check_mesh_intersection(
                obj,
                other,
                skip_inside_check=True,
                bvh_cache=cache,
            )
            if intersects:
                raise RuntimeError(f"Rock intersection: {obj.get_name()} / {other.get_name()}")


def build_scene(bproc, config, rock_paths, surfaces, seed):
    import bpy

    rng = Random(seed)
    terrain = sample_terrain(config["terrain"], rng.getrandbits(64))
    ground = create_terrain(bproc, terrain, rng.choice(surfaces))
    count = rng.randint(*config["rocks"]["count"])
    rocks, asset_ids, footprints = [], [], []
    templates = {}
    for index in range(count):
        path = rng.choice(rock_paths)
        if path not in templates:
            loaded = bproc.loader.load_blend(str(path), obj_types="mesh")
            if len(loaded) != 1:
                raise ValueError(f"Expected exactly one mesh in {path}; reimport asset")
            templates[path] = loaded[0]
            obj = loaded[0]
        else:
            # Physics applies transforms into each mesh; instances must own their mesh data.
            obj = templates[path].duplicate()
        obj.set_name(f"rock_{index + 1:03d}")
        obj.set_cp("rock_id", index + 1)
        obj.set_rotation_euler([0, 0, 0])
        bpy.context.view_layer.update()
        diameter = exp(rng.uniform(*map(log, config["rocks"]["diameter"])))
        dimensions = np.asarray(obj.blender_obj.dimensions, dtype=float)
        # Duplicates inherit their template's current scale.
        factor = diameter / max(dimensions[:2])
        obj.set_scale(np.asarray(obj.get_scale()) * factor)
        bpy.context.view_layer.update()
        dimensions = np.asarray(obj.blender_obj.dimensions, dtype=float)
        footprints.append(hypot(*dimensions[:2]) / 2)
        obj.set_rotation_euler([0, 0, rng.uniform(0, 2 * pi)])
        rocks.append(obj)
        asset_ids.append(path.relative_to(config["rocks"]["directory"]).with_suffix("").as_posix())
    positions = _place(footprints, terrain.size * 0.35, rng)
    for obj, (x, y), radius in zip(rocks, positions, footprints, strict=True):
        support = max(
            terrain.height_at(x + dx, y + dy)
            for dx in np.linspace(-radius, radius, 5)
            for dy in np.linspace(-radius, radius, 5)
        )
        obj.set_location([x, y, support + obj.blender_obj.dimensions.z / 2 + 0.08])
        obj.enable_rigidbody(
            active=True,
            collision_shape="CONVEX_HULL",
            collision_margin=0.003,
            mass=max(0.05, float(np.prod(obj.blender_obj.dimensions)) * 1500),
            friction=0.78,
            angular_damping=0.65,
            linear_damping=0.35,
        )
    bpy.context.view_layer.update()
    _validate_clearance(rocks)
    bproc.object.simulate_physics_and_fix_final_poses(
        min_simulation_time=2,
        max_simulation_time=15,
        check_object_interval=1,
        substeps_per_frame=12,
        solver_iters=30,
    )
    ground.disable_rigidbody()
    for obj in rocks:
        obj.disable_rigidbody()
        penetration = _penetration(obj, terrain)
        if penetration > 0.003:
            position = obj.get_location()
            position[2] += penetration - 0.003 + 1e-4
            obj.set_location(position)
    bpy.context.view_layer.update()
    _validate_clearance(rocks)
    for obj in rocks:
        if _penetration(obj, terrain) > 0.0031:
            raise RuntimeError(f"Terrain penetration: {obj.get_name()}")
    _lighting(bproc, config["lighting"]["random"], rng)
    return asset_ids


def _lighting(bproc, randomize, rng):
    import bpy

    elevation = rng.uniform(0.45, 1.2) if randomize else 0.75
    azimuth = rng.uniform(-pi, pi) if randomize else -0.4
    sun = bproc.types.Light(light_type="SUN", name="sun")
    sun.set_rotation_euler([pi / 2 - elevation, 0, azimuth])
    sun.set_energy(rng.uniform(1.8, 3.2) if randomize else 2.4)
    sun.set_color([1.0, 0.94, 0.84])
    sun.blender_obj.data.angle = 0.08
    world = bpy.context.scene.world
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()
    sky = nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation, sky.sun_rotation = elevation, azimuth
    sky.sun_disc = False
    background = nodes.new("ShaderNodeBackground")
    background.inputs["Strength"].default_value = 0.35
    output = nodes.new("ShaderNodeOutputWorld")
    links.new(sky.outputs["Color"], background.inputs["Color"])
    links.new(background.outputs["Background"], output.inputs["Surface"])
