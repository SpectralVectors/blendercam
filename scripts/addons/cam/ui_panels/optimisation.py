import bpy
from bpy.props import (
    BoolProperty,
    FloatProperty,
    IntProperty,
)

from .buttons_panel import CAMButtonsPanel
from ..utils import (
    update_operation,
    update_exact_mode,
    update_zbuffer_image,
    update_opencamlib,
    opencamlib_version,
)
from ..constants import PRECISION


class CAM_OPTIMISATION_Properties(bpy.types.PropertyGroup):

    optimize: BoolProperty(
        name="Reduce path points",
        description="Reduce path points",
        default=True,
        update=update_operation,
    )

    optimize_threshold: FloatProperty(
        name="Reduction threshold in μm",
        default=.2,
        min=0.000000001,
        max=1000,
        precision=20,
        update=update_operation,
    )

    use_exact: BoolProperty(
        name="Use exact mode",
        description="Exact mode allows greater precision, but is slower "
        "with complex meshes",
        default=True,
        update=update_exact_mode,
    )

    imgres_limit: IntProperty(
        name="Maximum resolution in megapixels",
        default=16,
        min=1,
        max=512,
        description="Limits total memory usage and prevents crashes. "
        "Increase it if you know what are doing",
        update=update_zbuffer_image,
    )

    pixsize: FloatProperty(
        name="sampling raster detail",
        default=0.0001,
        min=0.00001,
        max=0.1,
        precision=PRECISION,
        unit="LENGTH",
        update=update_zbuffer_image,
    )

    use_opencamlib: BoolProperty(
        name="Use OpenCAMLib",
        description="Use OpenCAMLib to sample paths or get waterline shape",
        default=False,
        update=update_opencamlib,
    )

    exact_subdivide_edges: BoolProperty(
        name="Auto subdivide long edges",
        description="This can avoid some collision issues when "
        "importing CAD models",
        default=False,
        update=update_exact_mode,
    )

    circle_detail: IntProperty(
        name="Detail of circles used for curve offsets",
        default=64,
        min=12,
        max=512,
        update=update_operation,
    )

    simulation_detail: FloatProperty(
        name="Simulation sampling raster detail",
        default=0.0002,
        min=0.00001,
        max=0.01,
        precision=PRECISION,
        unit="LENGTH",
        update=update_operation,
    )


class CAM_OPTIMISATION_Panel(CAMButtonsPanel, bpy.types.Panel):
    """CAM optimisation panel"""
    bl_label = "Optimisation"
    bl_idname = "WORLD_PT_CAM_OPTIMISATION"
    panel_interface_level = 2
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'CAM'
    bl_parent_id = "WORLD_PT_CAM_PARENT"

    def draw_optimize(self):
        if not self.has_correct_level():
            return

        box = self.layout.box()
        column = box.column(align=True)
        column.label(text='Reduction')
        column.prop(self.op.optimisation, 'optimize', text='Reduce Path Points')
        if self.op.optimisation.optimize:
            column.prop(self.op.optimisation, 'optimize_threshold', text='Threshold')

    def draw_exact_mode(self):
        if not self.has_correct_level():
            return

        if not self.op.geometry_source == 'OBJECT' or self.op.geometry_source == 'COLLECTION':
            return

        self.exact_possible = self.op.strategy not in [
            'MEDIAL_AXIS', 'POCKET', 'CUTOUT', 'DRILL', 'PENCIL', 'CURVE']

        if self.exact_possible:
            self.layout.prop(self.op.optimisation, 'use_exact')

        if not self.exact_possible or not self.op.optimisation.use_exact:
            box = self.layout.box()
            column = box.column(align=True)
            column.label(text='Sampling Raster')
            column.prop(self.op.optimisation, 'pixsize', text='Detail')
            column.prop(self.op.optimisation, 'imgres_limit', text='Max Res (MP)')

            sx = self.op.max.x - self.op.min.x
            sy = self.op.max.y - self.op.min.y
            resx = int(sx / self.op.optimisation.pixsize)
            resy = int(sy / self.op.optimisation.pixsize)

            if resx > 0 and resy > 0:
                resolution = 'Resolution: ' + str(resx) + ' x ' + str(resy)
                self.layout.label(text=resolution)

    def draw_use_opencamlib(self):
        if not self.has_correct_level():
            return

        if not (self.exact_possible and self.op.optimisation.use_exact):
            return

        ocl_version = opencamlib_version()

        if ocl_version is None:
            self.layout.label(text="Opencamlib is not available ")
            self.layout.prop(self.op.optimisation, 'exact_subdivide_edges')
        else:
            self.layout.prop(self.op.optimisation, 'use_opencamlib')

    def draw_simulation_detail(self):
        if not self.has_correct_level():
            return
        box = self.layout.box()
        column = box.column(align=True)
        column.label(text='Simulation Raster')
        column.prop(self.op.optimisation, 'simulation_detail', text='Detail')
        column.prop(self.op.optimisation, 'circle_detail', text='Offset Circle Detail')

    def draw_simplify_gcode(self):
        if not self.has_correct_level():
            return

        if self.op.strategy not in ['DRILL']:
            self.layout.prop(self.op, 'remove_redundant_points', text='Simplify G-Code')

        if self.op.remove_redundant_points:
            self.layout.prop(self.op, 'simplify_tol')

    def draw_use_modifiers(self):
        if not self.has_correct_level():
            return
        if self.op.geometry_source in ['OBJECT', 'COLLECTION']:
            self.layout.prop(self.op, 'use_modifiers', text='Use Mesh Modifiers')

    def draw_hide_all_others(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.op, 'hide_all_others', text='Hide Other Toolpaths')

    def draw_parent_path_to_object(self):
        if not self.has_correct_level():
            return
        self.layout.prop(self.op, 'parent_path_to_object', text='Parent Path to Object')

    def draw(self, context):
        self.context = context

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        self.draw_optimize()
        # self.layout.separator()
        self.draw_exact_mode()
        self.draw_use_opencamlib()
        # self.layout.separator()
        self.draw_simulation_detail()
        self.draw_simplify_gcode()
        self.draw_use_modifiers()
        self.draw_hide_all_others()
        self.draw_parent_path_to_object()
