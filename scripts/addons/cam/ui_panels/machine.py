
import bpy
from .buttons_panel import CAMButtonsPanel


class CAM_MACHINE_Panel(CAMButtonsPanel, bpy.types.Panel):
    """CAM machine panel"""
    bl_label = "Machine"
    bl_idname = "WORLD_PT_CAM_MACHINE"
    always_show_panel = True
    panel_interface_level = 0
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    bl_order = 1

    prop_level = {
        # Level 0
        'draw_post_processor': 0,
        'draw_system': 0,
        'draw_splindle_speeds': 0,
        'draw_working_area': 0,
        # Level 1
        'draw_presets': 1,
        'draw_feedrates': 1,
        'draw_hourly_rate': 1,
        # Level 2
        'draw_split_files': 2,
        'draw_position_definitions': 2,
        'draw_tool_options': 2,
        'draw_collet_size': 2,
        'draw_block_numbers': 2,
        # Level 3
        'draw_suplemental_axis': 3,
    }

    def draw_presets(self):
        if not self.has_correct_level():
            return
        row = self.layout.row(align=True)
        row.menu("CAM_MACHINE_MT_presets", text=bpy.types.CAM_MACHINE_MT_presets.bl_label)
        row.operator("render.cam_preset_machine_add", text="", icon='ADD')
        row.operator("render.cam_preset_machine_add", text="", icon='REMOVE').remove_active = True

    def draw_post_processor(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.machine, 'post_processor')

    def draw_split_files(self):
        if not self.has_correct_level():
            return
        # self.layout.prop(self.machine, 'eval_splitting')
        # if self.machine.eval_splitting:
        #     self.layout.prop(self.machine, 'split_limit')

    def draw_system(self):
        if not self.has_correct_level():
            return
        self.layout.prop(bpy.context.scene.unit_settings, 'system')

    def draw_position_definitions(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.machine, 'use_position_definitions')
        if self.machine.use_position_definitions:
            self.layout.prop(self.machine, 'starting_position')
            self.layout.prop(self.machine, 'mtc_position')
            self.layout.prop(self.machine, 'ending_position')

    def draw_working_area(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.machine, 'working_area')

    def draw_feedrates(self):
        if not self.has_correct_level():
            return
        box = self.layout.box()
        column = box.column(align=True)
        column.label(text='Feedrate (/min):')
        column.prop(self.machine, 'feedrate_min', text='Min')
        column.prop(self.machine, 'feedrate_max', text='Max')
        column.prop(self.machine, 'feedrate_default', text='Default')

    def draw_splindle_speeds(self):
        if not self.has_correct_level():
            return
        # TODO: spindle default and feedrate default should become part of the cutter definition...
        box = self.layout.box()
        column = box.column(align=True)
        column.label(text='Spindle Speed (RPM):')
        column.prop(self.machine, 'spindle_min', text='Min')
        column.prop(self.machine, 'spindle_max', text='Max')
        column.prop(self.machine, 'spindle_default', text='Default')
        column = box.column()
        column.prop(self.machine, 'spindle_start_time', text='Start Delay (seconds)')

    def draw_tool_options(self):
        if not self.has_correct_level():
            return
        # self.layout.prop(self.machine, 'output_tool_definitions')
        # self.layout.prop(self.machine, 'output_tool_change')
        # if self.machine.output_tool_change:
        #     self.layout.prop(self.machine, 'output_g43_on_tool_change')

    def draw_suplemental_axis(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.machine, 'axis4')
        self.layout.prop(self.machine, 'axis5')

    def draw_collet_size(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.machine, 'collet_size')

    def draw_block_numbers(self):
        if not self.has_correct_level():
            return
###########
        box = self.layout.box()
        column = box.column(align=True)
        column.label(text='File Output:')
        if self.machine.eval_splitting:
            column.prop(self.machine, 'split_limit')
        column.prop(self.machine, 'eval_splitting', text='Split Files')
        column.prop(self.machine, 'output_tool_definitions')
        column.prop(self.machine, 'output_tool_change')
        if self.machine.output_tool_change:
            column.prop(self.machine, 'output_g43_on_tool_change')
############
        column.prop(self.machine, 'output_block_numbers')
        if self.machine.output_block_numbers:
            column.prop(self.machine, 'start_block_number')
            column.prop(self.machine, 'block_number_increment')

    def draw_hourly_rate(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.machine, 'hourly_rate')

    def draw(self, context):
        self.context = context
        self.machine = bpy.context.scene.cam_machine
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        self.draw_presets()
        self.draw_post_processor()
        self.draw_split_files()
        self.draw_system()
        self.draw_working_area()
        self.draw_collet_size()
        self.draw_position_definitions()
        self.draw_suplemental_axis()
        self.draw_feedrates()
        self.draw_splindle_speeds()
        self.draw_tool_options()
        # self.draw_block_numbers()
        self.draw_hourly_rate()
