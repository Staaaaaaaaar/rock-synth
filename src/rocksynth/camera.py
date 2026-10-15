"""Explicit configuration poses; no camera sampling or visibility filtering."""

from math import radians, tan

import numpy as np


def configure_cameras(bproc, config, resolution, terrain_size):
    width, height = resolution
    focal = width / (2 * tan(radians(config["fov"]) / 2))
    intrinsics = np.array([[focal, 0, width / 2], [0, focal, height / 2], [0, 0, 1]])
    bproc.camera.set_intrinsics_from_K_matrix(
        intrinsics,
        width,
        height,
        clip_start=0.01,
        clip_end=max(100.0, terrain_size * 10),
    )
    for pose in config["poses"]:
        location = np.asarray(pose["position"], dtype=float)
        direction = np.asarray(pose["look_at"], dtype=float) - location
        rotation = bproc.camera.rotation_from_forward_vec(direction)
        bproc.camera.add_camera_pose(bproc.math.build_transformation_mat(location, rotation))
