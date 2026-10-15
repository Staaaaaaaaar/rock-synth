"""Heightfield terrain and a single PBR surface material implementation."""

from dataclasses import dataclass

import numpy as np


@dataclass
class Terrain:
    size: float
    heights: np.ndarray

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


def sample_terrain(config, seed):
    rng = np.random.default_rng(seed)
    resolution = 129
    field = np.zeros((resolution, resolution))
    target = np.linspace(0, 1, resolution)
    for octave in range(5):
        n = 2 ** (octave + 1) + 1
        coarse = rng.normal(size=(n, n))
        source = np.linspace(0, 1, n)
        horizontal = np.array([np.interp(target, source, row) for row in coarse])
        resized = np.array([np.interp(target, source, column) for column in horizontal.T]).T
        field += resized * 0.52**octave
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
    return Terrain(config["size"], field)


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
            r, c = divmod(vertex_index, n)
            uv.data[loop_index].uv = (c / (n - 1), r / (n - 1))
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
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (terrain.size / 2, terrain.size / 2, 1)
    links.new(coordinates_node.outputs["UV"], mapping.inputs["Vector"])
    textures = {}
    for channel, path in maps.items():
        node = nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(str(path), check_existing=True)
        if channel != "basecolor":
            node.image.colorspace_settings.name = "Non-Color"
        links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        textures[channel] = node.outputs["Color"]
    links.new(textures["basecolor"], shader.inputs["Base Color"])
    if "roughness" in textures:
        links.new(textures["roughness"], shader.inputs["Roughness"])
    normal = None
    if "normal" in textures:
        node = nodes.new("ShaderNodeNormalMap")
        links.new(textures["normal"], node.inputs["Color"])
        normal = node.outputs["Normal"]
    if "displacement" in textures:
        node = nodes.new("ShaderNodeBump")
        node.inputs["Strength"].default_value = 0.22
        node.inputs["Distance"].default_value = 0.035
        links.new(textures["displacement"], node.inputs["Height"])
        if normal is not None:
            links.new(normal, node.inputs["Normal"])
        normal = node.outputs["Normal"]
    if normal is not None:
        links.new(normal, shader.inputs["Normal"])
    obj.enable_rigidbody(active=False, collision_shape="MESH", collision_margin=0.002, friction=0.85)
    return obj
