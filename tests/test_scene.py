from math import hypot
from random import Random

import numpy as np
import pytest
from PIL import Image

from rocksynth.scene import _place
from rocksynth.terrain import Terrain, _texture_height, sample_terrain


def test_placement_stays_inside_ground_with_clearance():
    radii = [0.2, 0.4, 0.3, 0.1] * 5
    positions = _place(radii, 3.5, Random(42))
    assert positions == _place(radii, 3.5, Random(42))
    for i, ((x, y), radius) in enumerate(zip(positions, radii, strict=True)):
        assert hypot(x, y) + radius <= 3.5
        for j in range(i):
            assert hypot(x - positions[j][0], y - positions[j][1]) >= radius + radii[j] + 0.04


def test_overfull_scene_fails_instead_of_looping():
    with pytest.raises(ValueError, match="Cannot place"):
        _place([10], 1, Random(42))


def test_terrain_matches_rendered_triangle_interpolation():
    terrain = Terrain(2, np.array([[0, 0], [0, 1]], dtype=float))
    assert terrain.height_at(0, 0) == pytest.approx(0.5)
    assert terrain.height_at(-0.5, 0.5) == pytest.approx(0.25)
    assert terrain.height_at(1, 1) == 1


def test_terrain_seed_and_relief():
    first = sample_terrain({"size": 10, "relief": 0.15}, 42)
    second = sample_terrain({"size": 10, "relief": 0.15}, 42)
    assert np.array_equal(first.heights, second.heights)
    assert np.max(np.abs(first.heights)) == pytest.approx(0.15)


def test_microgeometry_resolution_and_flat_ground():
    terrain = sample_terrain({"size": 20, "relief": 0.15}, 42)
    assert terrain.size / (terrain.heights.shape[0] - 1) <= 0.05
    flat = sample_terrain({"size": 20, "relief": 0}, 42)
    assert np.count_nonzero(flat.heights) == 0


def test_texture_height_respects_uv_orientation_and_repeats(tmp_path):
    path = tmp_path / "height.png"
    Image.fromarray(np.array([[255, 255], [0, 0]], dtype=np.uint8)).save(path)
    u = np.array([0.25, 0.25])
    v = np.array([0.25, 0.75])
    heights = _texture_height(path, u, v)
    assert heights[0] == 0
    assert heights[1] == 1
    np.testing.assert_allclose(heights, _texture_height(path, u + 1, v + 1))


def test_displacement_changes_collision_heightfield_reproducibly(tmp_path):
    path = tmp_path / "height.png"
    Image.fromarray(np.array([[0, 255], [255, 0]], dtype=np.uint8)).save(path)
    config = {"size": 10, "relief": 0.15, "texture_size": 4}
    maps = {"displacement": path}
    first, second = sample_terrain(config, 42, maps), sample_terrain(config, 42, maps)
    np.testing.assert_array_equal(first.heights, second.heights)
    assert not np.array_equal(first.heights, sample_terrain(config, 42).heights)
    assert np.max(np.abs(first.heights)) == pytest.approx(0.15)
    # A ground vertex queried by physics must match the rendered mesh height.
    n = first.heights.shape[0]
    row, column = 20, 35
    x, y = (column / (n - 1) - 0.5) * first.size, (row / (n - 1) - 0.5) * first.size
    assert first.height_at(x, y) == pytest.approx(first.heights[row, column])
