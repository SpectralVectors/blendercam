
import bpy
from .buttons_panel import CAMButtonsPanel


class CAM_GCODE_Panel(CAMButtonsPanel, bpy.types.Panel):
    """CAM operation g-code options panel"""
    bl_label = "G-Code Output"
    bl_idname = "WORLD_PT_CAM_GCODE"
    panel_interface_level = 1
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    # bl_options = {'HIDE_HEADER'}
    bl_order = 99

    prop_level = {
        'draw_output_header': 1,
        'draw_output_trailer': 1,
        'draw_enable_dust': 1,
        'draw_enable_hold': 1,
        'draw_enable_mist': 1
    }

    def draw_output_header(self):
        if not self.has_correct_level():
            return
        self.column.prop(self.op, 'output_header', text='G-Code Header')
        if self.op.output_header:
            self.column.prop(self.op, 'gcode_header', text='Header')

    def draw_output_trailer(self):
        if not self.has_correct_level():
            return
        self.column.prop(self.op, 'output_trailer', text='G-Code Trailer')
        if self.op.output_trailer:
            self.column.prop(self.op, 'gcode_trailer', text='Trailer')

    def draw_enable_dust(self):
        if not self.has_correct_level():
            return
        self.column.prop(self.op, 'enable_dust', text='Dust Collector')
        if self.op.enable_dust:
            self.column.prop(self.op, 'gcode_start_dust_cmd')
            self.column.prop(self.op, 'gcode_stop_dust_cmd')

    def draw_enable_hold(self):
        if not self.has_correct_level():
            return
        self.column.prop(self.op, 'enable_hold', text='Hold Down')
        if self.op.enable_hold:
            self.column.prop(self.op, 'gcode_start_hold_cmd')
            self.column.prop(self.op, 'gcode_stop_hold_cmd')

    def draw_enable_mist(self):
        if not self.has_correct_level():
            return
        self.column.prop(self.op, 'enable_mist')
        if self.op.enable_mist:
            self.column.prop(self.op, 'gcode_start_mist_cmd')
            self.column.prop(self.op, 'gcode_stop_mist_cmd')

    def draw_block_numbers(self):
        if not self.has_correct_level():
            return
###########
        self.column.label(text='Options:')  # , icon='EVENT_G')
        machine = bpy.context.scene.cam_machine
        self.column.prop(machine, 'eval_splitting', text='Split Files')
        if machine.eval_splitting:
            self.column.prop(machine, 'split_limit')
        self.column.label(text='Output:')
        self.column.prop(machine, 'output_tool_definitions', text='Tool Definitions')
        self.column.prop(machine, 'output_tool_change', text='Tool Change Commands')
        if machine.output_tool_change:
            self.column.prop(machine, 'output_g43_on_tool_change', text='G43 on Tool Change')
############
        self.column.prop(machine, 'output_block_numbers', text='Block Numbers')
        if machine.output_block_numbers:
            self.column.prop(machine, 'start_block_number')
            self.column.prop(machine, 'block_number_increment')

    def draw(self, context):
        self.context = context

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        self.box = self.layout.box()
        self.column = self.box.column(align=True)

        self.draw_block_numbers()
        self.draw_output_header()
        self.draw_output_trailer()
        self.draw_enable_dust()
        self.draw_enable_hold()
        self.draw_enable_mist()
