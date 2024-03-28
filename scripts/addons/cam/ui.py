# blender CAM ui.py (c) 2012 Vilem Novak
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

import sys
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import (
    StringProperty,
)
from bpy.types import (
    Panel,
    Menu,
    Operator,
    UIList
)

from . import (
    gcodeimportparser,
    simple
)
from .simple import *

from .ui_panels.buttons_panel import CAMButtonsPanel
from .ui_panels.interface import *
from .ui_panels.info import *
from .ui_panels.operations import *
from .ui_panels.cutter import *
from .ui_panels.machine import *
from .ui_panels.material import *
from .ui_panels.chains import *
from .ui_panels.op_properties import *
from .ui_panels.movement import *
from .ui_panels.feedrate import *
from .ui_panels.optimisation import *
from .ui_panels.area import *
from .ui_panels.gcode import *
from .ui_panels.pack import *
from .ui_panels.slice import *


class CAM_UL_orientations(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            layout.label(text=item.name, translate=False, icon_value=icon)
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


# panel containing all tools

class VIEW3D_PT_tools_curvetools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_context = "objectmode"
    bl_label = "Curve CAM Tools"
    bl_options = {'HIDE_HEADER'}
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == 'BLENDERCAM_RENDER'

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.6
        layout.operator("object.curve_boolean", icon='MOD_BOOLEAN')
        layout.operator("object.convex_hull", icon='MOD_SOLIDIFY')
        layout.operator("object.curve_intarsion", icon='OUTLINER_DATA_META')
        column = layout.column(align=True)
        column.operator("object.curve_overcuts", icon='CON_SIZELIKE')
        column.operator("object.curve_overcuts_b", icon='CON_SIZELIKE')
        column = layout.column(align=True)
        column.operator("object.silhouete", icon='USER', text='Object Silhouette')
        column.operator("object.silhouete_offset", icon='COMMUNITY', text='Silhouette Offset')
        layout.operator("object.curve_remove_doubles",
                        icon='FORCE_CHARGE', text='Remove Curve Doubles')
        layout.operator("object.mesh_get_pockets", icon='HOLDOUT_ON', text='Get Pocket Surfaces')

        column = layout.column(align=True)
        column.operator("object.cam_pack_objects", icon='STICKY_UVS_LOC',
                        text='Pack Curves on Sheet')
        column.operator("object.cam_slice_objects", icon='ALIGN_FLUSH', text='Slice Model to Sheet')

        layout.operator("scene.calculate_bas_relief", icon='MOD_OCEAN', text='Bas Relief')


class TOPBAR_MT_import_gcode(bpy.types.Menu):
    bl_idname = 'TOPBAR_MT_import_gcode'
    bl_label = "Import G-Code"

    def draw(self, context):
        layout = self.layout
        layout.operator('wm.gcode_import', text='Import G-Code (.gcode)')


class VIEW3D_MT_tools_add(bpy.types.Menu):
    bl_idname = 'VIEW3D_MT_tools_add'
    bl_label = "Curve CAM Creators"

    def draw(self, context):
        layout = self.layout
        layout.menu("VIEW3D_MT_tools_create", icon='FCURVE')


class VIEW3D_MT_tools_create(bpy.types.Menu):
    bl_idname = 'VIEW3D_MT_tools_create'
    bl_label = "Curve CAM Creators"

    def draw(self, context):
        layout = self.layout
        layout.operator("object.curve_plate")
        layout.operator("object.curve_drawer")
        layout.operator("object.curve_mortise")
        layout.operator("object.curve_interlock")
        layout.operator("object.curve_puzzle")
        layout.operator("object.sine")
        layout.operator("object.lissajous")
        layout.operator("object.hypotrochoid")
        layout.operator("object.customcurve")
        layout.operator("object.curve_hatch")
        layout.operator("object.curve_gear")
        layout.operator("object.curve_flat_cone")


class VIEW3D_PT_tools_create(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_context = "objectmode"
    bl_label = "Curve CAM Creators"
    bl_option = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("object.curve_plate")
        layout.operator("object.curve_drawer")
        layout.operator("object.curve_mortise")
        layout.operator("object.curve_interlock")
        layout.operator("object.curve_puzzle")
        layout.operator("object.sine")
        layout.operator("object.lissajous")
        layout.operator("object.hypotrochoid")
        layout.operator("object.customcurve")
        layout.operator("object.curve_hatch")
        layout.operator("object.curve_gear")
        layout.operator("object.curve_flat_cone")

# Gcode import panel---------------------------------------------------------------
# ------------------------------------------------------------------------
#    Panel in Object Mode
# ------------------------------------------------------------------------


class CustomPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_context = "objectmode"
    bl_label = "Import Gcode"
    bl_idname = "OBJECT_PT_importgcode"

    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT',
                                'EDIT_MESH'}  # with this poll addon is visibly even when no object is selected

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        # isettings = scene.cam_import_gcode
        # layout.prop(isettings, 'output')
        # layout.prop(isettings, "split_layers")
        #
        # layout.prop(isettings, "subdivide")
        # col = layout.column(align=True)
        # col = col.row(align=True)
        # col.split()
        # col.label(text="Segment length")
        #
        # col.prop(isettings, "max_segment_size")
        # col.enabled = isettings.subdivide
        # col.separator()

        col = layout.column()
        col.scale_y = 2.0
        col.operator("wm.gcode_import")


class WM_OT_gcode_import(Operator, ImportHelper):
    """Import Gcode, travel lines don't get drawn"""
    bl_idname = "wm.gcode_import"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Gcode"

    # ImportHelper mixin class uses this
    filename_ext = ".txt"

    filter_glob: StringProperty(
        default="*.*",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    split_layers: BoolProperty(
        name="Split Layers",
        description="Save every layer as single Objects in Collection",
        default=False,
    )
    subdivide: BoolProperty(
        name="Subdivide",
        description="Only Subdivide gcode segments that are "
        "bigger than 'Segment length' ",
        default=False,
    )
    output: EnumProperty(
        name="Output Type",
        items=(
            ('mesh', 'Mesh', 'Make a mesh output'),
            ('curve', 'Curve', 'Make curve output')
        ),
        default='curve',
    )
    max_segment_size: FloatProperty(
        name="Max Segment Size",
        description="Only Segments bigger then this value get subdivided",
        default=0.001,
        min=0.0001,
        max=1.0,
        unit="LENGTH",
    )

    def execute(self, context):
        print(self.filepath)
        return gcodeimportparser.import_gcode(
            context,
            self.filepath,
            self.output,
            self.split_layers,
            self.subdivide,
            self.max_segment_size,
        )
