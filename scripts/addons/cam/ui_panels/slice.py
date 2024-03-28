
import bpy
from .buttons_panel import CAMButtonsPanel


class CAM_SLICE_Panel(CAMButtonsPanel, bpy.types.Panel):
    """CAM slicer panel"""
    bl_label = "Slice model to plywood sheets"
    bl_idname = "WORLD_PT_CAM_SLICE"
    panel_interface_level = 2
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}

    COMPAT_ENGINES = {'BLENDERCAM_RENDER'}

    def draw(self, context):
        layout = self.layout
        scene = bpy.context.scene
        settings = scene.cam_slice

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout.operator("object.cam_slice_objects")
        layout.prop(settings, 'slice_distance')
        layout.prop(settings, 'slice_above0')
        layout.prop(settings, 'slice_3d')
        layout.prop(settings, 'indexes')
