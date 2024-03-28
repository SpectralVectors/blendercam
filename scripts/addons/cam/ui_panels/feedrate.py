import bpy
from .buttons_panel import CAMButtonsPanel


class CAM_FEEDRATE_Panel(CAMButtonsPanel, bpy.types.Panel):
    """CAM feedrate panel"""
    bl_label = "Feedrate"
    bl_idname = "WORLD_PT_CAM_FEEDRATE"
    panel_interface_level = 0
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'CAM'
    bl_parent_id = "WORLD_PT_CAM_PARENT"

    prop_level = {
        'draw_feedrate': 0,
        'draw_sim_feedrate': 2,
        'draw_plunge_feedrate': 1,
        'draw_plunge_angle': 1,
        'draw_spindle_rpm': 0
    }

    def draw_feedrate(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.op, 'feedrate')

    def draw_sim_feedrate(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.op, 'do_simulation_feedrate')

    def draw_plunge_feedrate(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.op, 'plunge_feedrate')

    def draw_plunge_angle(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.op, 'plunge_angle')

    def draw_spindle_rpm(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.op, 'spindle_rpm')

    def draw(self, context):
        self.context = context

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        self.draw_feedrate()
        self.draw_sim_feedrate()
        self.draw_plunge_feedrate()
        self.draw_plunge_angle()
        self.draw_spindle_rpm()
