"""Fabex 'info.py'

'CAM Info & Warnings' properties and panel in Properties > Render
"""

from datetime import timedelta

import bpy
from bpy.props import (
    StringProperty,
    FloatProperty,
)
from bpy.types import (
    Panel,
    PropertyGroup,
)
from .buttons_panel import CAMButtonsPanel
from ...utils import (
    update_operation,
)
from ...constants import (
    PRECISION,
    CHIPLOAD_PRECISION,
    MAX_OPERATION_TIME,
)
from ...simple import strInUnits
from ...version import __version__ as cam_version

# Info panel
# This panel gives general information about the current operation


class CAM_INFO_Properties(PropertyGroup):

    warnings: StringProperty(
        name="Warnings",
        description="Warnings",
        default="",
        update=update_operation,
    )

    chipload: FloatProperty(
        name="Chipload",
        description="Calculated chipload",
        default=0.0,
        unit="LENGTH",
        precision=CHIPLOAD_PRECISION,
    )

    duration: FloatProperty(
        name="Estimated Time",
        default=0.01,
        min=0.0000,
        max=MAX_OPERATION_TIME,
        precision=PRECISION,
        unit="TIME",
    )


class CAM_INFO_Panel(CAMButtonsPanel, Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    # bl_category = "CNC"
    bl_options = {"HIDE_HEADER"}

    bl_label = "Info & Warnings"
    bl_idname = "WORLD_PT_CAM_INFO"
    panel_interface_level = 0
    always_show_panel = True

    # Display the Info Panel
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        main = layout.box()
        # main.label(text="╠ INFO ╣", icon="INFO")
        main.label(text=f'Fabex v{".".join([str(x) for x in cam_version])}', icon="INFO")
        if context.window_manager.progress > 0:
            col = main.column(align=True)
            col.scale_y = 2
            percent = int(context.window_manager.progress * 100)
            col.progress(
                factor=context.window_manager.progress,
                text=f"Processing...{percent}%",
            )
        if self.op is None:
            return
        else:
            if not self.op.info.warnings == "":
                # Operation Warnings
                box = main.box()
                col = box.column(align=True)
                col.alert = True
                col.label(text="!!! Warning !!!", icon="ERROR")
                for line in self.op.info.warnings.rstrip("\n").split("\n"):
                    if len(line) > 0:
                        col.label(text=line, icon="ERROR")

            # Cutter Engagement
            if not self.op.strategy == "CUTOUT" and not self.op.cutter_type in ["LASER", "PLASMA"]:
                box = main.box()
                col = box.column(align=True)
                # Warns if cutter engagement is greater than 50%
                if self.op.cutter_type in ["BALLCONE"]:
                    engagement = round(100 * self.op.dist_between_paths / self.op.ball_radius, 1)
                else:
                    engagement = round(
                        100 * self.op.dist_between_paths / self.op.cutter_diameter, 1
                    )

                if engagement > 50:
                    col.alert = True
                    col.label(text="Warning: High Cutter Engagement", icon="ERROR")

                col.label(text=f"Cutter Engagement: {engagement}%", icon="MOD_SHRINKWRAP")

            # Operation Time Estimate
            duration = self.op.info.duration
            seconds = int(duration * 60)
            if not seconds > 0:
                return

            time_estimate = str(timedelta(seconds=seconds))
            split = time_estimate.split(":")
            split[0] += "h "
            split[1] += "m "
            split[2] += "s"
            time_estimate = split[0] + split[1] + split[2]

            box = main.box()
            col = box.column(align=True)
            col.label(text="Estimates")
            col.label(text=f"Time: {time_estimate}", icon="TIME")

            # Operation Chipload
            if not self.op.info.chipload > 0:
                pass
            else:
                chipload = f"Chipload: {strInUnits(self.op.info.chipload, 4)}/tooth"
                col.label(text=chipload, icon="DRIVER_ROTATIONAL_DIFFERENCE")

            # Operation Money Cost
            if self.level >= 1:
                if not int(self.op.info.duration * 60) > 0:
                    return

                if float(bpy.context.scene.cam_machine.hourly_rate) < 0.01:
                    return

                cost_per_second = bpy.context.scene.cam_machine.hourly_rate / 3600
                total_cost = self.op.info.duration * 60 * cost_per_second
                op_cost = f"Cost: ${total_cost:.2f} (${cost_per_second:.2f}/s)"
                col.label(text=op_cost, icon="TAG")