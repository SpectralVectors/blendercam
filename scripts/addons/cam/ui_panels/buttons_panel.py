"""BlenderCAM 'buttons_panel.py'

Parent (Mixin) class for all panels in 'ui_panels'
Sets up polling and operations to show / hide panels based on Interface Level
"""

import inspect

import bpy


# Panel definitions
class CAMButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    always_show_panel = False
    COMPAT_ENGINES = {'CNCCAM_RENDER'}

    # COMPAT_ENGINES must be defined in each subclass, external engines can add themselves here

    @classmethod
    def poll(cls, context):
        rd = bpy.context.scene.render
        if rd.engine in cls.COMPAT_ENGINES:
            if cls.always_show_panel:
                return True
            op = cls.active_operation()
            if op and op.valid:
                if hasattr(cls, 'panel_interface_level'):
                    return cls.panel_interface_level <= int(context.scene.interface.level)
                else:
                    return True
        return False

    @classmethod
    def active_operation_index(cls):
        return (bpy.context.scene.cam_active_operation)

    @classmethod
    def active_operation(cls):
        active_op = None
        try:
            active_op = bpy.context.scene.cam_operations[cls.active_operation_index()]
        except IndexError:
            pass
        return (active_op)

    def __init__(self):
        self.op = self.active_operation()
        addon_prefs = bpy.context.preferences.addons["bl_ext.user_default.blendercam"].preferences
        self.use_experimental = addon_prefs.experimental

    def operations_count(self):
        return (len(bpy.context.scene.cam_operations))

    def has_operations(self):
        return (self.operations_count() > 0)

    def has_correct_level(self):
        if not hasattr(self, 'prop_level'):
            return True

        caller_function = inspect.stack()[1][3]

        if caller_function not in self.prop_level:
            return True

        return self.prop_level[caller_function] <= int(self.context.scene.interface.level)
