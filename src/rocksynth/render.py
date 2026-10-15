"""The sole renderer: RGB and scene-stable rock IDs from BlenderProc."""

from rocksynth.camera import configure_cameras


def render_views(bproc, config):
    import bpy

    configure_cameras(bproc, config["camera"], config["output"]["resolution"], config["terrain"]["size"])
    bpy.context.scene.view_settings.view_transform = "AgX"
    bpy.context.scene.view_settings.look = "AgX - Medium High Contrast"
    bpy.context.scene.view_settings.exposure = -0.15
    bproc.renderer.set_max_amount_of_samples(64)
    bproc.renderer.set_noise_threshold(0.025)
    # clean_up() keeps compositor settings. Remove only this call's temporary
    # segmentation nodes afterwards, so they do not accumulate across scenes.
    bpy.context.scene.use_nodes = True
    nodes = bpy.context.scene.node_tree.nodes
    existing_nodes = {node.name for node in nodes}
    bproc.renderer.enable_segmentation_output(map_by=["rock_id"], default_values={"rock_id": 0})
    try:
        data = bproc.renderer.render()
    finally:
        for node in list(nodes):
            if node.name not in existing_nodes:
                nodes.remove(node)
    return data["colors"], data["rock_id_segmaps"]
