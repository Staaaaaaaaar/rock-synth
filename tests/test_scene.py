from math import hypot
from random import Random

import numpy as np
import pytest

from rocksynth.scene import _place
from rocksynth.terrain import Terrain, sample_terrain


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
