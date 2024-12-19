cam.utilities.addon_utils
=========================

.. py:module:: cam.utilities.addon_utils

.. autoapi-nested-parse::

   Fabex 'addon_utils.py' © 2012 Vilem Novak



Functions
---------

.. autoapisummary::

   cam.utilities.addon_utils.check_operations_on_load
   cam.utilities.addon_utils.fix_units
   cam.utilities.addon_utils.keymap_register
   cam.utilities.addon_utils.keymap_unregister


Module Contents
---------------

.. py:function:: check_operations_on_load(context)

   Checks for any broken computations on load and resets them.

   This function verifies the presence of necessary Blender add-ons and
   installs any that are missing. It also resets any ongoing computations
   in camera operations and sets the interface level to the previously used
   level when loading a new file. If the add-on has been updated, it copies
   the necessary presets from the source to the target directory.
   Additionally, it checks for updates to the camera plugin and updates
   operation presets if required.

   :param context: The context in which the function is executed, typically containing
                   information about
                   the current Blender environment.


.. py:function:: fix_units()

   Set up units for Fabex.

   This function configures the unit settings for the current Blender
   scene. It sets the rotation system to degrees and the scale length to
   1.0, ensuring that the units are appropriately configured for use within
   Fabex.


.. py:function:: keymap_register()

.. py:function:: keymap_unregister()

