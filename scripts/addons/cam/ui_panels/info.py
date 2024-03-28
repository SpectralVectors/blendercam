import bpy
from bpy.props import (
    StringProperty,
    FloatProperty
)

from .buttons_panel import CAMButtonsPanel
from ..utils import (
    update_operation,
    opencamlib_version
)
from ..constants import (
    PRECISION,
    CHIPLOAD_PRECISION,
    MAX_OPERATION_TIME,
)
from ..version import __version__ as cam_version
from ..simple import strInUnits

# Info panel
# This panel gives general information about the current operation


class CAM_INFO_Properties(bpy.types.PropertyGroup):

    warnings: StringProperty(
        name='warnings',
        description='warnings',
        default='',
        update=update_operation,
    )

    chipload: FloatProperty(
        name="chipload", description="Calculated chipload",
        default=0.0, unit='LENGTH',
        precision=CHIPLOAD_PRECISION,
    )

    duration: FloatProperty(
        name="Estimated time", default=0.01, min=0.0000,
        max=MAX_OPERATION_TIME,
        precision=PRECISION,
        unit="TIME",
    )


class CAM_INFO_Panel(CAMButtonsPanel, bpy.types.Panel):
    bl_label = "CAM info & warnings"
    bl_idname = "WORLD_PT_CAM_INFO"
    panel_interface_level = 0
    always_show_panel = True
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    # bl_context = "render"
    bl_order = 2
    bl_options = {'HIDE_HEADER'}

    prop_level = {
        'draw_blendercam_version': 0,
        'draw_opencamlib_version': 1,
        'draw_op_warnings': 0,
        'draw_op_time': 0,
        'draw_op_chipload': 0,
        'draw_op_money_cost': 1,
    }

    # Draw blendercam version (and whether there are updates available)
    def draw_blendercam_version(self):
        if not self.has_correct_level():
            return
        self.column.label(
            text=f'BlenderCAM v{".".join([str(x) for x in cam_version])}')
        if len(bpy.context.preferences.addons['cam'].preferences.new_version_available) > 0:
            # self.box.label(text=f"New version available:")
            self.column.label(
                text=f"New version available:  {bpy.context.preferences.addons['cam'].preferences.new_version_available}")
            self.column.operator("render.cam_update_now")

    # Display the OpenCamLib version
    def draw_opencamlib_version(self):
        if not self.has_correct_level():
            return
        ocl_version = opencamlib_version()
        if ocl_version is None:
            self.column.label(text="OpenCAMLib is not installed")
        else:
            self.column.label(
                text=f"OpenCAMLib v{ocl_version}")

    # Display warnings related to the current operation
    def draw_op_warnings(self):
        if not self.has_correct_level():
            return
        for line in self.op.info.warnings.rstrip("\n").split("\n"):
            if len(line) > 0:
                box = self.column.box()
                box.alert = True
                box.label(text=line, icon='ERROR')
                box.alert = False

    # Display the time estimation for the current operation
    def draw_op_time(self):
        if not self.has_correct_level():
            return
        if not int(self.op.info.duration * 60) > 0:
            return

        time_estimate = f"Operation duration: {int(self.op.info.duration*60)}s "
        if self.op.info.duration > 60:
            time_estimate += f" ({int(self.op.info.duration / 60)}h"
            time_estimate += f" {round(self.op.info.duration % 60)}min)"
        elif self.op.info.duration > 1:
            time_estimate += f" ({round(self.op.info.duration % 60)}min)"

        self.column.label(text=time_estimate)

    # Display the chipload (does this work ?)
    def draw_op_chipload(self):
        if not self.has_correct_level():
            return
        if not self.op.info.chipload > 0:
            return

        chipload = f"Chipload: {strInUnits(self.op.info.chipload, 4)}/tooth"
        self.column.label(text=chipload)

    # Display the current operation money cost
    def draw_op_money_cost(self):
        if not self.has_correct_level():
            return
        if not int(self.op.info.duration * 60) > 0:
            return

        # row = self.layout.row()
        # row.label(text='Hourly Rate')
        self.column.prop(bpy.context.scene.cam_machine, 'hourly_rate', text='Hourly Rate')

        if float(bpy.context.scene.cam_machine.hourly_rate) < 0.01:
            return

        cost_per_second = bpy.context.scene.cam_machine.hourly_rate / 3600
        total_cost = self.op.info.duration * 60 * cost_per_second
        op_cost = f"Operation cost: ${total_cost:.2f} (${cost_per_second:.2f}/s)"
        self.column.label(text=op_cost)

    # Display the Info Panel
    def draw(self, context):
        # context.area.tag_redraw()
        self.context = context

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        self.box = self.layout.box()
        self.column = self.box.column(align=True)
        self.column.label(text='Info & Warnings', icon='INFO')
        self.draw_blendercam_version()
        self.draw_opencamlib_version()
        if context.window_manager.progress > 0:
            self.column.progress(factor=context.window_manager.progress,
                                 text='Processing... (ESC to Cancel)')
        if self.op:
            self.layout.separator()
            self.draw_op_warnings()
            self.draw_op_time()
            self.draw_op_money_cost()
