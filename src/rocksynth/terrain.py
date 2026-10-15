"""Heightfield terrain and a single PBR surface material implementation."""

from dataclasses import dataclass
from math import ceil, cos, sin

import numpy as np
from PIL import Image


@dataclass
class Terrain:
    size: float
    heights: np.ndarray
    texture_size: float = 4.0
    texture_angle: float = 0.0
    texture_offset: tuple[float, float] = (0.0, 0.0)

    def texture_uv(self, x, y):
        """One shared mapping for geometry displacement, color and tangent normals."""
        c, s = cos(self.texture_angle), sin(self.texture_angle)
        return (
            (c * x - s * y) / self.texture_size + self.texture_offset[0],
            (s * x + c * y) / self.texture_size + self.texture_offset[1],
        )

    def height_at(self, x, y):
        """Interpolate the same triangles used by the terrain mesh."""
        n = self.heights.shape[0]
        col = np.clip((np.asarray(x) / self.size + 0.5) * (n - 1), 0, n - 1)
        row = np.clip((np.asarray(y) / self.size + 0.5) * (n - 1), 0, n - 1)
        c, r = np.minimum(col.astype(int), n - 2), np.minimum(row.astype(int), n - 2)
        tx, ty = col - c, row - r
        h00, h10 = self.heights[r, c], self.heights[r, c + 1]
        h01, h11 = self.heights[r + 1, c], self.heights[r + 1, c + 1]
        return np.where(
            tx >= ty,
            h00 + tx * (h10 - h00) + ty * (h11 - h10),
            h00 + tx * (h11 - h01) + ty * (h01 - h00),
        )


def _resize(values, resolution):
    source = np.linspace(0, 1, values.shape[0])
    target = np.linspace(0, 1, resolution)
    horizontal = np.array([np.interp(target, source, row) for row in values])
    return np.array([np.interp(target, source, column) for column in horizontal.T]).T


def _texture_height(path, u, v):
    """Read raw height values (not sRGB); periodic bilinear sampling matches UVs."""
    with Image.open(path) as image:
        image = image.convert("F")
        image.thumbnail((1024, 1024), Image.Resampling.BILINEAR)
        values = np.asarray(image, dtype=float)
    low, high = np.percentile(values, (1, 99))
    values = np.clip((values - low) / max(high - low, 1e-12), 0, 1)
    h, w = values.shape
    # Image row zero is the top; UV v=0 is the bottom. Use pixel centers.
    x, y = (u % 1) * w - 0.5, ((1 - v) % 1) * h - 0.5
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    tx, ty = x - x0, y - y0
    return (1 - ty) * ((1 - tx) * values[y0 % h, x0 % w] + tx * values[y0 % h, (x0 + 1) % w]) + ty * (
        (1 - tx) * values[(y0 + 1) % h, x0 % w] + tx * values[(y0 + 1) % h, (x0 + 1) % w]
    )


def sample_terrain(config, seed, maps=None):
    rng = np.random.default_rng(seed)
    resolution = 129
    field = np.zeros((resolution, resolution))
    for octave in range(5):
        n = 2 ** (octave + 1) + 1
        coarse = rng.normal(size=(n, n))
        field += _resize(coarse, resolution) * 0.52**octave
    field -= field.mean()
    field /= max(field.std(), 1e-12)
    ridges = 1 - np.minimum(np.abs(field), 1)
    field = 0.78 * field + 0.22 * (ridges - ridges.mean())
    for _ in range(8):
        padded = np.pad(field, 1, mode="edge")
        average = (
            sum(padded[r : r + resolution, c : c + resolution] for r in range(3) for c in range(3) if (r, c) != (1, 1))
            / 8
        )
        difference = average - field
        field += np.sign(difference) * np.maximum(np.abs(difference) - 0.12, 0) * 0.18
    field -= field.mean()
    field *= config["relief"] / max(np.max(np.abs(field)), 1e-12)
    # About 5 cm between vertices at the default size, capped for large grounds.
    resolution = min(513, max(129, 2 * ceil(config["size"] / 0.1) + 1))
    field = _resize(field, resolution)
    terrain = Terrain(
        config["size"], field, config.get("texture_size", 4.0), rng.uniform(0, 2 * np.pi), tuple(rng.uniform(0, 1, 2))
    )
    if config["relief"] > 0:
        field += rng.uniform(-0.012, 0.012, field.shape)
        if maps and "displacement" in maps:
            coordinates = np.linspace(-terrain.size / 2, terrain.size / 2, resolution)
            x, y = np.meshgrid(coordinates, coordinates)
            u, v = terrain.texture_uv(x, y)
            field += (_texture_height(maps["displacement"], u, v) - 0.5) * 0.02
        field -= field.mean()
        field *= config["relief"] / max(np.max(np.abs(field)), 1e-12)
    return terrain


def create_terrain(bproc, terrain, maps):
    import bpy

    n = terrain.heights.shape[0]
    coordinates = np.linspace(-terrain.size / 2, terrain.size / 2, n)
    vertices = [
        (float(x), float(y), float(terrain.heights[r, c]))
        for r, y in enumerate(coordinates)
        for c, x in enumerate(coordinates)
    ]
    faces = []
    for r in range(n - 1):
        for c in range(n - 1):
            a = r * n + c
            faces.extend([(a, a + 1, a + n + 1), (a, a + n + 1, a + n)])
    mesh = bpy.data.meshes.new("terrain")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            x, y, _ = vertices[vertex_index]
            uv.data[loop_index].uv = terrain.texture_uv(x, y)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bproc.object.create_from_blender_mesh(mesh, "terrain")
    obj.set_cp("rock_id", 0)
    material = obj.new_material("ground")
    material.set_principled_shader_value("Roughness", 0.85)
    material.set_principled_shader_value("Metallic", 0.0)
    nodes = material.blender_obj.node_tree.nodes
    links = material.blender_obj.node_tree.links
    shader = nodes.get("Principled BSDF")
    coordinates_node = nodes.new("ShaderNodeTexCoord")
    textures = {}
    for channel, path in maps.items():
        node = nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(str(path), check_existing=True)
        if channel != "basecolor":
            node.image.colorspace_settings.name = "Non-Color"
        links.new(coordinates_node.outputs["UV"], node.inputs["Vector"])
        textures[channel] = node.outputs["Color"]
    # A charcoal floor keeps nearly black scan pixels responsive to lighting.
    color = nodes.new("ShaderNodeMixRGB")
    color.blend_type = "ADD"
    color.inputs[0].default_value = 1
    color.inputs[2].default_value = (0.018, 0.018, 0.018, 1)
    links.new(textures["basecolor"], color.inputs[1])
    links.new(color.outputs["Color"], shader.inputs["Base Color"])
    grain = nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = terrain.texture_size * 80
    grain.inputs["Detail"].default_value = 2
    links.new(coordinates_node.outputs["UV"], grain.inputs["Vector"])
    if "roughness" in textures:
        links.new(textures["roughness"], shader.inputs["Roughness"])
    else:
        roughness = nodes.new("ShaderNodeMapRange")
        roughness.inputs["To Min"].default_value = 0.72
        roughness.inputs["To Max"].default_value = 0.96
        links.new(grain.outputs["Fac"], roughness.inputs["Value"])
        links.new(roughness.outputs["Result"], shader.inputs["Roughness"])
    normal = None
    if "normal" in textures:
        node = nodes.new("ShaderNodeNormalMap")
        node.inputs["Strength"].default_value = 0.8
        links.new(textures["normal"], node.inputs["Color"])
        normal = node.outputs["Normal"]
    if "displacement" in textures:
        node = nodes.new("ShaderNodeBump")
        node.inputs["Strength"].default_value = 0.6
        node.inputs["Distance"].default_value = 0.05
        links.new(textures["displacement"], node.inputs["Height"])
        if normal is not None:
            links.new(normal, node.inputs["Normal"])
        normal = node.outputs["Normal"]
    fine_bump = nodes.new("ShaderNodeBump")
    fine_bump.inputs["Strength"].default_value = 0.3
    fine_bump.inputs["Distance"].default_value = 0.004
    links.new(grain.outputs["Fac"], fine_bump.inputs["Height"])
    if normal is not None:
        links.new(normal, fine_bump.inputs["Normal"])
    links.new(fine_bump.outputs["Normal"], shader.inputs["Normal"])
    obj.enable_rigidbody(active=False, collision_shape="MESH", collision_margin=0.002, friction=0.85)
    return obj
