from types import SimpleNamespace

import numpy as np

from rocksynth.camera import configure_cameras


def test_explicit_world_coordinates_are_used_without_sampling_or_filtering():
    poses, intrinsics = [], []

    def transform(location, rotation):
        return np.array(location), np.array(rotation)

    bproc = SimpleNamespace(
        camera=SimpleNamespace(
            set_intrinsics_from_K_matrix=lambda *args, **kwargs: intrinsics.append((args, kwargs)),
            rotation_from_forward_vec=lambda direction: direction,
            add_camera_pose=poses.append,
        ),
        math=SimpleNamespace(build_transformation_mat=transform),
    )
    config = {
        "fov": 90,
        "poses": [
            {"position": [0, -4, 4], "look_at": [0, 0, 0]},
            # An upward-looking camera is allowed too: no visibility filtering.
            {"position": [1, 2, 3], "look_at": [1, 2, 10]},
        ],
    }
    configure_cameras(bproc, config, [640, 480], 10)
    assert len(poses) == 2
    np.testing.assert_allclose(poses[0][0], [0, -4, 4])
    np.testing.assert_allclose(poses[0][1], [0, 4, -4])
    np.testing.assert_allclose(poses[1][1], [0, 0, 7])
    np.testing.assert_allclose(intrinsics[0][0][0], [[320, 0, 320], [0, 320, 240], [0, 0, 1]])
