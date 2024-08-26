"""BlenderCAM 'puzzle_joinery.py' © 2021 Alain Pelletier

Functions to add various puzzle joints as curves.
"""

from math import (
    cos,
    degrees,
    pi,
    sin,
    sqrt,
    tan,
)

import bpy

from . import (
    joinery,
    simple,
    utils,
)

DT = 1.025


def finger(diameter, stem=2):
    """Create a joint tool shape based on the specified diameter and stem.

    This function generates a 3D joint tool shape using Blender's
    operations. It calculates the dimensions of the tool based on the
    provided diameter and stem parameters. The function creates a
    rectangular base and circular features, duplicates and mirrors them, and
    performs union and difference operations to form the final shape. The
    resulting object is named and cleaned up to ensure a proper mesh.

    Args:
        diameter (float): The diameter of the tool for joint creation.
        stem (float?): The amount of radius the stem or neck
            of the joint will have. Defaults to 2.

    Returns:
        None: This function does not return a value but modifies
        the Blender scene by creating and manipulating objects.
    """

    # diameter = diameter of the tool for joint creation
    # DT = Bit diameter tolerance
    # stem = amount of radius the stem or neck of the joint will have
    global DT
    RESOLUTION = 12  # Data resolution
    cube_sx = diameter * DT * (2 + stem - 1)
    cube_ty = diameter * DT
    cube_sy = 2 * diameter * DT
    circle_radius = diameter * DT / 2
    c1x = cube_sx / 2
    c2x = cube_sx / 2
    c2y = 3 * circle_radius
    c1y = circle_radius

    bpy.ops.curve.simple(align='WORLD', location=(0, cube_ty, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=cube_sx, Simple_length=cube_sy, use_cyclic_u=True, edit_mode=False)
    bpy.context.active_object.name = "ftmprect"

    bpy.ops.curve.simple(align='WORLD', location=(c2x, c2y, 0), rotation=(0, 0, 0), Simple_Type='Ellipse',
                         Simple_a=circle_radius,
                         Simple_b=circle_radius, Simple_sides=4, use_cyclic_u=True, edit_mode=False, shape='3D')

    bpy.context.active_object.name = "ftmpcirc_add"
    bpy.context.object.data.resolution_u = RESOLUTION

    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

    simple.duplicate()
    simple.mirrorx()

    simple.union('ftmp')
    simple.rename('ftmp', '_sum')

    rc1 = circle_radius

    bpy.ops.curve.simple(align='WORLD', location=(c1x, c1y, 0), rotation=(0, 0, 0), Simple_Type='Ellipse',
                         Simple_a=circle_radius, Simple_b=rc1, Simple_sides=4, use_cyclic_u=True, edit_mode=False,
                         shape='3D')

    bpy.context.active_object.name = "_circ_delete"
    bpy.context.object.data.resolution_u = RESOLUTION
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

    simple.duplicate()
    simple.mirrorx()
    simple.union('_circ')

    simple.difference('_', '_sum')
    bpy.ops.object.curve_remove_doubles()
    simple.rename('_sum', "_puzzle")


def fingers(diameter, inside, amount=1, stem=1):
    """Create a specified number of fingers for a joint tool.

    This function generates a set of fingers based on the provided diameter
    and tolerance values. It calculates the necessary translations and
    duplicates the fingers if more than one is required. Additionally, it
    creates a receptacle using the silhouette offset from the fingers, if
    specified.

    Args:
        diameter (float): The diameter of the tool for joint creation.
        inside (float): The tolerance in the joint receptacle.
        amount (int?): The number of fingers to create. Defaults to 1.
        stem (int?): The amount of radius the stem or neck of the joint will have. Defaults
            to 1.
    """

    # diameter = diameter of the tool for joint creation
    # inside = Tolerance in the joint receptacle
    global DT  # Bit diameter tolerance
    # stem = amount of radius the stem or neck of the joint will have
    # amount = the amount of fingers

    xtranslate = -(4 + 2 * (stem - 1)) * (amount - 1) * diameter * DT / 2
    finger(diameter, stem=stem)  # generate male finger
    simple.active_name("puzzlem")
    simple.move(x=xtranslate, y=-0.00002)

    if amount > 1:
        # duplicate translate the amount needed (faster than generating new)
        for i in range(amount - 1):
            bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked": False, "mode": 'TRANSLATION'},
                                          TRANSFORM_OT_translate={
                                              "value": ((4 + 2 * (stem - 1)) * diameter * DT, 0, 0.0)})
        simple.union('puzzle')

    simple.active_name("fingers")
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

    # Receptacle is made using the silhouette offset from the fingers
    if inside > 0:
        bpy.ops.object.silhouete_offset(offset=inside, style='1')
        simple.active_name('receptacle')
        simple.move(y=-inside)


def twistf(name, length, diameter, tolerance, twist, tneck, tthick, twist_keep=False):
    """Add a twist lock to a receptacle.

    This function modifies the receptacle by adding a twist lock feature if
    the 'twist' parameter is set to True. It performs a series of operations
    including interlocking, rotating, and moving the components based on the
    provided parameters. If 'twist_keep' is True, it duplicates the twist
    lock feature for further use. The function ensures that the active name
    is set correctly throughout the process.

    Args:
        name (str): The name to assign to the active component.
        length (float): The length of the receptacle.
        diameter (float): The diameter of the receptacle.
        tolerance (float): The tolerance value for the dimensions.
        twist (bool): A flag indicating whether to add a twist lock.
        tneck (float): The neck thickness for the twist lock.
        tthick (float): The thickness of the twist lock.
        twist_keep (bool?): A flag indicating whether to keep the twist lock duplicate. Defaults to
            False.

    Returns:
        None: This function does not return a value but modifies the active component
            in place.
    """

    # add twist lock to receptacle
    if twist:
        joinery.interlock_twist(length, tthick, tolerance, cx=0, cy=0, rotation=0, percentage=tneck)
        simple.rotate(pi / 2)
        simple.move(y=-tthick / 2 + 2 * diameter + 2 * tolerance)
        simple.active_name('xtemptwist')
        if twist_keep:
            simple.duplicate()
            simple.active_name('twist_keep_f')
        simple.make_active(name)
        simple.active_name('xtemp')
        simple.union('xtemp')
        simple.active_name(name)


def twistm(name, length, diameter, tolerance, twist, tneck, tthick, angle, twist_keep=False, x=0, y=0):
    """Add a twist lock to a male connector.

    This function creates a twist lock feature on a male connector based on
    the provided parameters. It utilizes global variables and functions from
    the `joinery` and `simple` modules to perform operations such as
    interlocking, rotating, and moving components. The function also allows
    for duplication of the twist feature if specified.

    Args:
        name (str): The name to assign to the active component.
        length (float): The length of the connector.
        diameter (float): The diameter of the connector.
        tolerance (float): The tolerance for the connector dimensions.
        twist (bool): A flag indicating whether to add a twist feature.
        tneck (float): The neck thickness for the twist feature.
        tthick (float): The thickness of the twist feature.
        angle (float): The angle to rotate the twist feature.
        twist_keep (bool?): A flag indicating whether to keep the twist feature. Defaults to False.
        x (float?): The x-coordinate for movement. Defaults to 0.
        y (float?): The y-coordinate for movement. Defaults to 0.

    Returns:
        None: This function does not return a value but modifies the active component
            in place.
    """

    # add twist lock to male connector
    global DT
    if twist:
        joinery.interlock_twist(length, tthick, tolerance, cx=0, cy=0, rotation=0, percentage=tneck)
        simple.rotate(pi / 2)
        simple.move(y=-tthick / 2 + 2 * diameter * DT)
        simple.rotate(angle)
        simple.move(x=x, y=y)
        simple.active_name('_twist')
        if twist_keep:
            simple.duplicate()
            simple.active_name('twist_keep_m')
        simple.make_active(name)
        simple.active_name('_tmp')
        simple.difference('_', '_tmp')
        simple.active_name(name)


def bar(width, thick, diameter, tolerance, amount=0, stem=1, twist=False, tneck=0.5, tthick=0.01, twist_keep=False,
        twist_line=False, twist_line_amount=2, which='MF'):
    """Create a puzzle bar with specified dimensions and features.

    This function generates a puzzle bar based on the provided parameters,
    including width, thickness, and joint characteristics. It allows for
    customization of the number of fingers in the joint, the presence of a
    twist lock, and other attributes. The function utilizes Blender's
    operations to create and manipulate 3D objects, including rectangles and
    joints, and performs various transformations such as rotation and
    movement to achieve the desired shape.

    Args:
        width (float): The length of the bar.
        thick (float): The thickness of the bar.
        diameter (float): The diameter of the tool used for joint creation.
        tolerance (float): The tolerance in the joint.
        amount (int?): The number of fingers in the joint; 0 means auto-generate. Defaults to
            0.
        stem (float?): The amount of radius the stem or neck of the joint will have. Defaults
            to 1.
        twist (bool?): Indicates whether to add a twist lock. Defaults to False.
        tneck (float?): The percentage the twist neck will have compared to thickness. Defaults
            to 0.5.
        tthick (float?): The thickness of the twist material. Defaults to 0.01.
        twist_keep (bool?): Indicates whether to keep the twist feature. Defaults to False.
        twist_line (bool?): Indicates whether to add a twist line feature. Defaults to False.
        twist_line_amount (int?): The amount of twist line to create. Defaults to 2.
        which (str?): Specifies the type of joint; options are 'M', 'F', 'MF', 'MM', 'FF'.
            Defaults to 'MF'.
    """


    # width = length of the bar
    # thick = thickness of the bar
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # Which M,F, MF, MM, FF

    global DT
    if amount == 0:
        amount = round(thick / ((4 + 2 * (stem - 1)) * diameter * DT)) - 1
    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=width, Simple_length=thick, use_cyclic_u=True, edit_mode=False)
    simple.active_name('tmprect')

    fingers(diameter, tolerance, amount, stem=stem)

    if which == 'MM' or which == 'M' or which == 'MF':
        simple.rename('fingers', '_tmpfingers')
        simple.rotate(-pi / 2)
        simple.move(x=width / 2)
        simple.rename('tmprect', '_tmprect')
        simple.union('_tmp')
        simple.active_name("tmprect")
        twistm('tmprect', thick, diameter, tolerance, twist, tneck, tthick, -pi / 2,
               x=width / 2, twist_keep=twist_keep)

    twistf('receptacle', thick, diameter, tolerance, twist, tneck, tthick, twist_keep=twist_keep)
    simple.rename('receptacle', '_tmpreceptacle')
    if which == 'FF' or which == 'F' or which == 'MF':
        simple.rotate(-pi / 2)
        simple.move(x=-width / 2)
        simple.rename('tmprect', '_tmprect')
        simple.difference('_tmp', '_tmprect')
        simple.active_name("tmprect")
        if twist_keep:
            simple.make_active('twist_keep_f')
            simple.rotate(-pi / 2)
            simple.move(x=-width / 2)

    simple.remove_multiple("_")  # Remove temporary base and holes
    simple.remove_multiple("fingers")  # Remove temporary base and holes

    if twist_line:
        joinery.twist_line(thick, tthick, tolerance, tneck, twist_line_amount, width)
        if twist_keep:
            simple.duplicate()
        simple.active_name('tmptwist')
        simple.difference('tmp', 'tmprect')
    simple.rename('tmprect', 'Puzzle_bar')
    simple.remove_multiple("tmp")  # Remove temporary base and holes
    simple.make_active('Puzzle_bar')


def arc(radius, thick, angle, diameter, tolerance, amount=0, stem=1, twist=False, tneck=0.5, tthick=0.01,
        twist_keep=False, which='MF'):
    """Generate an arc with specified parameters.

    This function creates a 3D arc based on the provided radius, thickness,
    angle, and other parameters. It calculates the necessary components for
    the arc and generates it using Blender's operations. The function also
    handles the creation of fingers and twist locks if specified. The
    generated arc can be either male, female, or a combination of both based
    on the 'which' parameter.

    Args:
        radius (float): The radius of the curve.
        thick (float): The thickness of the bar.
        angle (float): The angle of the arc. Must be greater than 0.
        diameter (float): The diameter of the tool for joint creation.
        tolerance (float): Tolerance in the joint.
        amount (int?): The number of fingers in the joint. Defaults to 0 for auto generation.
        stem (float?): The amount of radius the stem or neck of the joint will have. Defaults
            to 1.
        twist (bool?): Whether to add a twist lock. Defaults to False.
        tneck (float?): Percentage the twist neck will have compared to thickness. Defaults to
            0.5.
        tthick (float?): Thickness of the twist material. Defaults to 0.01.
        twist_keep (bool?): Whether to keep the twist. Defaults to False.
        which (str?): Specifies which joint to generate ('M', 'F', 'MF'). Defaults to 'MF'.

    Returns:
        None: This function does not return a value but modifies the Blender scene
            directly.
    """

    # radius = radius of the curve
    # thick = thickness of the bar
    # angle = angle of the arc
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # which = which joint to generate, Male Female MaleFemale M, F, MF

    global DT  # diameter tolerance for diameter of finger creation

    if angle == 0:  # angle cannot be 0
        angle = 0.01

    negative = False
    if angle < 0:  # if angle < 0 then negative is true
        angle = -angle
        negative = True

    if amount == 0:
        amount = round(thick / ((4 + 2 * (stem - 1)) * diameter * DT)) - 1

    fingers(diameter, tolerance, amount, stem=stem)
    twistf('receptacle', thick, diameter, tolerance, twist, tneck, tthick, twist_keep=twist_keep)
    twistf('testing', thick, diameter, tolerance, twist, tneck, tthick, twist_keep=twist_keep)
    print("generating arc")
    # generate arc
    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Segment',
                         Simple_a=radius - thick / 2,
                         Simple_b=radius + thick / 2, Simple_startangle=-0.0001, Simple_endangle=degrees(angle),
                         Simple_radius=radius, use_cyclic_u=False, edit_mode=False)
    bpy.context.active_object.name = "tmparc"

    simple.rename('fingers', '_tmpfingers')

    simple.rotate(pi)
    simple.move(x=radius)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

    simple.rename('tmparc', '_tmparc')
    if which == 'MF' or which == 'M':
        simple.union('_tmp')
        simple.active_name("base")
        twistm('base', thick, diameter, tolerance, twist, tneck, tthick, pi, x=radius)
        simple.rename('base', '_tmparc')

    simple.rename('receptacle', '_tmpreceptacle')
    simple.mirrory()
    simple.move(x=radius)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    simple.rotate(angle)
    simple.make_active('_tmparc')

    if which == 'MF' or which == 'F':
        simple.difference('_tmp', '_tmparc')
    bpy.context.active_object.name = "PUZZLE_arc"
    bpy.ops.object.curve_remove_doubles()
    simple.remove_multiple("_")  # Remove temporary base and holes
    simple.make_active('PUZZLE_arc')
    if which == 'M':
        simple.rotate(-angle)
        simple.mirrory()
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=False)
        simple.rotate(-pi / 2)
        simple.move(y=radius)
        simple.rename('PUZZLE_arc', 'PUZZLE_arc_male')
    elif which == 'F':
        simple.mirrorx()
        simple.move(x=radius)
        simple.rotate(pi / 2)
        simple.rename('PUZZLE_arc', 'PUZZLE_arc_receptacle')
    else:
        simple.move(x=-radius)
    # bpy.ops.object.transform_apply(location=True, rotation=False, scale=False, properties=False)
    #
    if negative:  # mirror if angle is negative
        simple.mirrory()
    #
    # bpy.ops.object.curve_remove_doubles()


def arcbararc(length, radius, thick, angle, angleb, diameter, tolerance, amount=0, stem=1, twist=False,
              tneck=0.5, tthick=0.01, which='MF', twist_keep=False, twist_line=False, twist_line_amount=2):
    """Generate an arc bar joint with specified parameters.

    This function creates a 3D arc bar joint in Blender using the provided
    dimensions and characteristics. It generates a base rectangle and then
    adds male and/or female sections based on the specified joint type. The
    function also supports optional twisting features for the joint.

    Args:
        length (float): The total width of the segments including 2 * radius and thickness.
        radius (float): The radius of the curve.
        thick (float): The thickness of the bar.
        angle (float): The angle of the female part.
        angleb (float): The angle of the male part.
        diameter (float): The diameter of the tool for joint creation.
        tolerance (float): The tolerance in the joint.
        amount (int?): The number of fingers in the joint; 0 means auto-generate. Defaults to
            0.
        stem (float?): The amount of radius the stem or neck of the joint will have. Defaults
            to 1.
        twist (bool?): Whether to add a twist lock. Defaults to False.
        tneck (float?): The percentage the twist neck will have compared to thickness. Defaults
            to 0.5.
        tthick (float?): The thickness of the twist material. Defaults to 0.01.
        which (str?): Specifies which joint to generate ('M', 'F', 'MF'). Defaults to 'MF'.
        twist_keep (bool?): Whether to keep the twist after creation. Defaults to False.
        twist_line (bool?): Whether to add a twist line. Defaults to False.
        twist_line_amount (int?): The amount for the twist line. Defaults to 2.

    Returns:
        None: This function does not return any value but modifies the Blender scene
            directly.

    Note:
        This function relies on Blender's bpy module and assumes that the
        necessary context is set up for
        executing operations within Blender's environment.
    """

    # length is the total width of the segments including 2 * radius and thick
    # radius = radius of the curve
    # thick = thickness of the bar
    # angle = angle of the female part
    # angleb = angle of the male part
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # which = which joint to generate, Male Female MaleFemale M, F, MF

    # adjust length to include 2x radius + thick
    length -= (radius * 2 + thick)

    # generate base rectangle
    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=length * 1.005, Simple_length=thick, use_cyclic_u=True, edit_mode=False)
    simple.active_name("tmprect")

    #  Generate male section and join to the base
    if which == 'M' or which == 'MF':
        arc(radius, thick, angleb, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck,
            tthick=tthick, which='M')
        simple.move(x=length / 2)
        simple.active_name('tmp_male')
        simple.select_multiple('tmp')
        bpy.ops.object.curve_boolean(boolean_type='UNION')
        simple.active_name('male')
        simple.remove_multiple('tmp')
        simple.rename('male', 'tmprect')

    # Generate female section and join to base
    if which == 'F' or which == 'MF':
        arc(radius, thick, angle, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck,
            tthick=tthick, which='F')
        simple.move(x=-length / 2)
        simple.active_name('tmp_receptacle')
        simple.union('tmp')
        simple.active_name('tmprect')

    if twist_line:
        joinery.twist_line(thick, tthick, tolerance, tneck, twist_line_amount, length)
        if twist_keep:
            simple.duplicate()
        simple.active_name('tmptwist')
        simple.difference('tmp', 'tmprect')

    simple.active_name('arcBarArc')
    simple.make_active('arcBarArc')


def arcbar(length, radius, thick, angle, diameter, tolerance, amount=0, stem=1, twist=False,
           tneck=0.5, tthick=0.01, twist_keep=False, which='MF', twist_line=False, twist_line_amount=2):
    """Generate an arc bar joint based on specified parameters.

    This function creates an arc bar joint by generating male and female
    sections based on the provided dimensions and characteristics. The
    function takes into account various parameters such as length, radius,
    thickness, angle, and tolerance to accurately model the joint. The joint
    can be customized with options for twisting and the number of fingers in
    the joint. The generated components are then combined to form the final
    arc bar.

    Args:
        length (float): The total width of the segments including 2 * radius and thickness.
        radius (float): The radius of the curve.
        thick (float): The thickness of the bar.
        angle (float): The angle of the female part.
        diameter (float): The diameter of the tool for joint creation.
        tolerance (float): Tolerance in the joint.
        amount (int?): The number of fingers in the joint; 0 means auto-generate. Defaults to
            0.
        stem (float?): The amount of radius the stem or neck of the joint will have. Defaults
            to 1.
        twist (bool?): Indicates if a twist lock addition is required. Defaults to False.
        tneck (float?): Percentage the twist neck will have compared to thickness. Defaults to
            0.5.
        tthick (float?): Thickness of the twist material. Defaults to 0.01.
        twist_keep (bool?): Indicates if the twist should be retained. Defaults to False.
        which (str?): Specifies which joint to generate ('M', 'F', 'MF'). Defaults to 'MF'.
        twist_line (bool?): Indicates if a twist line should be included. Defaults to False.
        twist_line_amount (int?): Amount of twist line to generate. Defaults to 2.

    Returns:
        None: This function does not return a value but modifies the active scene in
            Blender.
    """

    # length is the total width of the segments including 2 * radius and thick
    # radius = radius of the curve
    # thick = thickness of the bar
    # angle = angle of the female part
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # which = which joint to generate, Male Female MaleFemale M, F, MF
    if which == 'M':
        which = 'MM'
    elif which == 'F':
        which = 'FF'
    # adjust length to include 2x radius + thick
    length -= (radius * 2 + thick)

    # generate base rectangle
    #  Generate male section and join to the base
    if which == 'MM' or which == 'MF':
        bar(length, thick, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick,
            which='M', twist_keep=twist_keep, twist_line=twist_line, twist_line_amount=twist_line_amount)
        simple.active_name('tmprect')

    if which == 'FF' or which == 'FM':
        bar(length, thick, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick,
            which='F', twist_keep=twist_keep, twist_line=twist_line, twist_line_amount=twist_line_amount)
        simple.rotate(pi)
        simple.active_name('tmprect')

    # Generate female section and join to base
    if which == 'FF' or which == 'MF':
        arc(radius, thick, angle, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck,
            tthick=tthick, which='F')
        simple.move(x=-length / 2 * 0.998)
        simple.active_name('tmp_receptacle')
        simple.union('tmp')
        simple.active_name('arcBar')
        simple.remove_multiple('tmp')

    if which == 'MM':
        arc(radius, thick, angle, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck,
            tthick=tthick, which='M')
        bpy.ops.transform.mirror(orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                 orient_matrix_type='GLOBAL', constraint_axis=(True, False, False))
        simple.move(x=-length / 2 * 0.998)
        simple.active_name('tmp_receptacle')
        simple.union('tmp')
        simple.active_name('arcBar')
        simple.remove_multiple('tmp')

    simple.make_active('arcBar')


def multiangle(radius, thick, angle, diameter, tolerance, amount=0, stem=1, twist=False,
               tneck=0.5, tthick=0.01, combination='MFF'):
    """Generate a multi-angle joint based on specified parameters.

    This function creates a multi-angle joint by generating curves and arcs
    using the provided parameters such as radius, thickness, angle,
    diameter, tolerance, and other optional settings. It utilizes the
    Blender Python API to create and manipulate 3D shapes, allowing for the
    customization of the joint's geometry. The function supports different
    combinations of male and female parts, and can automatically generate
    the number of fingers in the joint if specified.

    Args:
        radius (float): The radius of the curve.
        thick (float): The thickness of the bar.
        angle (float): The angle of the female part.
        diameter (float): The diameter of the tool for joint creation.
        tolerance (float): The tolerance in the joint.
        amount (int?): The amount of fingers in the joint; 0 means auto-generate. Defaults to
            0.
        stem (float?): The amount of radius the stem or neck of the joint will have. Defaults
            to 1.
        twist (bool?): Whether to add a twist lock. Defaults to False.
        tneck (float?): The percentage the twist neck will have compared to thickness. Defaults
            to 0.5.
        tthick (float?): The thickness of the twist material. Defaults to 0.01.
        combination (str?): Which joint to generate ('M', 'F', 'MF', 'MFF', 'MMF'). Defaults to
            'MFF'.

    Returns:
        None: This function does not return a value but modifies the Blender scene.
    """

    # length is the total width of the segments including 2 * radius and thick
    # radius = radius of the curve
    # thick = thickness of the bar
    # angle = angle of the female part
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # which = which joint to generate, Male Female MaleFemale M, F, MF

    r_exterior = radius + thick / 2
    r_interior = radius - thick / 2

    height = sqrt(r_exterior * r_exterior - radius * radius) + r_interior / 4

    bpy.ops.curve.simple(align='WORLD', location=(0, height, 0),
                         rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=r_interior, Simple_length=r_interior / 2, use_cyclic_u=True,
                         edit_mode=False, shape='3D')
    simple.active_name('tmp_rect')

    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Circle', Simple_sides=4,
                         Simple_radius=r_interior, shape='3D', use_cyclic_u=True, edit_mode=False)
    simple.move(y=radius * tan(angle))
    simple.active_name('tmpCircle')

    arc(radius, thick, angle, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick,
        which='MF')
    simple.active_name('tmp_arc')
    if combination == 'MFF':
        simple.duplicate()
        simple.mirrorx()
    elif combination == 'MMF':
        arc(radius, thick, angle, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck,
            tthick=tthick,
            which='M')
        simple.active_name('tmp_arc')
        simple.mirrory()
        simple.rotate(pi / 2)
    simple.union("tmp_")
    simple.difference('tmp', 'tmp_')
    simple.active_name('multiAngle60')


def t(length, thick, diameter, tolerance, amount=0, stem=1, twist=False, tneck=0.5, tthick=0.01, combination='MF',
      base_gender='M', corner=False):
    """Generate a 3D model based on specified parameters.

    This function creates a 3D model by manipulating geometric shapes based
    on the provided parameters. It considers various combinations of shapes
    and orientations to produce the final model. The function handles
    different configurations based on the `combination` and `corner`
    arguments, allowing for flexibility in the design process. The resulting
    model is constructed using a series of operations such as moving,
    duplicating, and uniting shapes.

    Args:
        length (float): The length of the main shape.
        thick (float): The thickness of the shape.
        diameter (float): The diameter of the shape.
        tolerance (float): The tolerance level for the dimensions.
        amount (int?): The amount of material to use. Defaults to 0.
        stem (int?): The stem configuration. Defaults to 1.
        twist (bool?): Whether to apply a twist to the shape. Defaults to False.
        tneck (float?): The neck thickness. Defaults to 0.5.
        tthick (float?): The thickness for the neck. Defaults to 0.01.
        combination (str?): The combination type ('MF', 'F', 'M'). Defaults to 'MF'.
        base_gender (str?): The base gender for the model ('M' or 'F'). Defaults to 'M'.
        corner (bool?): Whether to apply corner adjustments. Defaults to False.

    Returns:
        None: This function does not return a value but modifies the 3D model
            directly.
    """

    if corner:
        if combination == 'MF':
            base_gender = 'M'
            combination = 'f'
        elif combination == 'F':
            base_gender = 'F'
            combination = 'f'
        elif combination == 'M':
            base_gender = 'M'
            combination = 'm'

    bar(length, thick, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck,
        tthick=tthick, which=base_gender)
    simple.active_name('tmp')
    fingers(diameter, tolerance, amount=amount, stem=stem)
    if combination == 'MF' or combination == 'M' or combination == 'm':
        simple.make_active('fingers')
        simple.move(y=thick / 2)
        simple.duplicate()
        simple.active_name('tmp')
        simple.union('tmp')

    if combination == 'M':
        simple.make_active('fingers')
        simple.mirrory()
        simple.active_name('tmp')
        simple.union('tmp')

    if combination == 'MF' or combination == 'F' or combination == 'f':
        simple.make_active('receptacle')
        simple.move(y=-thick / 2)
        simple.duplicate()
        simple.active_name('tmp')
        simple.difference('tmp', 'tmp')

    if combination == 'F':
        simple.make_active('receptacle')
        simple.mirrory()
        simple.active_name('tmp')
        simple.difference('tmp', 'tmp')

    simple.remove_multiple('receptacle')
    simple.remove_multiple('fingers')

    simple.rename('tmp', 't')
    simple.make_active('t')


def curved_t(length, thick, radius, diameter, tolerance, amount=0, stem=1, twist=False, tneck=0.5, tthick=0.01,
             combination='MF', base_gender='M'):
    """Create a curved shape based on specified parameters.

    This function generates a 3D curved shape using the provided dimensions
    and characteristics. It utilizes various helper functions to create bars
    and arcs, applying transformations such as mirroring and union
    operations to achieve the desired geometry. The function supports
    different configurations based on the `base_gender` parameter, allowing
    for the creation of male, female, or combined shapes.

    Args:
        length (float): The length of the bar.
        thick (float): The thickness of the bar.
        radius (float): The radius of the arcs.
        diameter (float): The diameter used in arc creation.
        tolerance (float): The tolerance level for the operations.
        amount (int?): The amount parameter for the bar creation. Defaults to 0.
        stem (int?): The stem parameter for the bar creation. Defaults to 1.
        twist (bool?): Indicates whether to apply a twist to the shape. Defaults to False.
        tneck (float?): The neck thickness parameter. Defaults to 0.5.
        tthick (float?): The thickness parameter for the arcs. Defaults to 0.01.
        combination (str?): Specifies the combination type for the arcs. Defaults to 'MF'.
        base_gender (str?): Specifies the base gender for the shape ('M', 'F', or 'MF'). Defaults to
            'M'.

    Returns:
        None: This function does not return a value but modifies the 3D scene
            directly.
    """

    bar(length, thick, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck,
        tthick=tthick, which=combination)
    simple.active_name('tmpbar')

    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=3 * radius, Simple_length=thick, use_cyclic_u=True, edit_mode=False)
    simple.active_name("tmp_rect")

    if base_gender == 'MF':
        arc(radius, thick, pi / 2, diameter, tolerance,
            amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick, which='M')
        simple.move(-radius)
        simple.active_name('tmp_arc')
        arc(radius, thick, pi / 2, diameter, tolerance,
            amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick, which='F')
        simple.move(radius)
        simple.mirrory()
        simple.active_name('tmp_arc')
        simple.union('tmp_arc')
        simple.duplicate()
        simple.mirrorx()
        simple.union('tmp_arc')
        simple.difference('tmp_', 'tmp_arc')
    else:
        arc(radius, thick, pi / 2, diameter, tolerance,
            amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick, which=base_gender)
        simple.active_name('tmp_arc')
        simple.difference('tmp_', 'tmp_arc')
        if base_gender == 'M':
            simple.move(-radius)
        else:
            simple.move(radius)
        simple.duplicate()
        simple.mirrorx()

    simple.union('tmp')
    simple.active_name('curved_t')


def mitre(length, thick, angle, angleb, diameter, tolerance, amount=0, stem=1, twist=False,
          tneck=0.5, tthick=0.01, which='MF'):
    """Generate a mitre joint with specified parameters.

    This function creates a 3D mitre joint based on the provided dimensions
    and characteristics. It generates a base rectangle and cutout shapes for
    the joint, then constructs either a male, female, or both sections
    depending on the specified type. The function utilizes Blender's
    operations to create and manipulate the geometry of the joint.

    Args:
        length (float): The total width of the segments including 2 * radius and thickness.
        thick (float): The thickness of the bar.
        angle (float): The angle of the female part.
        angleb (float): The angle of the male part.
        diameter (float): The diameter of the tool for joint creation.
        tolerance (float): The tolerance in the joint.
        amount (int?): The number of fingers in the joint; 0 means auto-generate. Defaults to
            0.
        stem (float?): The amount of radius the stem or neck of the joint will have. Defaults
            to 1.
        twist (bool?): Indicates whether to add a twist lock. Defaults to False.
        tneck (float?): The percentage the twist neck will have compared to thickness. Defaults
            to 0.5.
        tthick (float?): The thickness of the twist material. Defaults to 0.01.
        which (str?): Specifies which joint to generate ('M', 'F', 'MF'). Defaults to 'MF'.
    """

    # length is the total width of the segments including 2 * radius and thick
    # radius = radius of the curve
    # thick = thickness of the bar
    # angle = angle of the female part
    # angleb = angle of the male part
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # which = which joint to generate, Male Female MaleFemale M, F, MF

    # generate base rectangle
    bpy.ops.curve.simple(align='WORLD', location=(0, -thick / 2, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=length * 1.005 + 4 * thick, Simple_length=thick, use_cyclic_u=True,
                         edit_mode=False,
                         shape='3D')
    simple.active_name("tmprect")

    # generate cutout shapes
    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=4 * thick, Simple_length=6 * thick, use_cyclic_u=True, edit_mode=False,
                         shape='3D')
    simple.move(x=2 * thick)
    simple.rotate(angle)
    simple.move(x=length / 2)
    simple.active_name('tmpmitreright')

    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=4 * thick, Simple_length=6 * thick, use_cyclic_u=True, edit_mode=False,
                         shape='3D')
    simple.move(x=2 * thick)
    simple.rotate(angleb)
    simple.move(x=length / 2)
    simple.mirrorx()
    simple.active_name('tmpmitreleft')
    simple.difference('tmp', 'tmprect')
    simple.make_active('tmprect')

    fingers(diameter, tolerance, amount, stem=stem)

    #  Generate male section and join to the base
    if which == 'M' or which == 'MF':
        simple.make_active('fingers')
        simple.duplicate()
        simple.active_name('tmpfingers')
        simple.rotate(angle - pi / 2)
        h = thick / cos(angle)
        h /= 2
        simple.move(x=length / 2 + h * sin(angle), y=-thick / 2)
        if which == 'M':
            simple.rename('fingers', 'tmpfingers')
            simple.rotate(angleb - pi / 2)
            h = thick / cos(angleb)
            h /= 2
            simple.move(x=length / 2 + h * sin(angleb), y=-thick / 2)
            simple.mirrorx()

        simple.union('tmp')
        simple.active_name('tmprect')

    # Generate female section and join to base
    if which == 'MF' or which == 'F':
        simple.make_active('receptacle')
        simple.mirrory()
        simple.duplicate()
        simple.active_name('tmpreceptacle')
        simple.rotate(angleb - pi / 2)
        h = thick / cos(angleb)
        h /= 2
        simple.move(x=length / 2 + h * sin(angleb), y=-thick / 2)
        simple.mirrorx()
        if which == 'F':
            simple.rename('receptacle', 'tmpreceptacle2')
            simple.rotate(angle - pi / 2)
            h = thick / cos(angle)
            h /= 2
            simple.move(x=length / 2 + h * sin(angle), y=-thick / 2)
        simple.difference('tmp', 'tmprect')

    simple.remove_multiple('receptacle')
    simple.remove_multiple('fingers')
    simple.rename('tmprect', 'mitre')


def open_curve(line, thick, diameter, tolerance, amount=0, stem=1, twist=False, t_neck=0.5, t_thick=0.01,
               twist_amount=1, which='MF', twist_keep=False):
    """Open a curve with optional puzzle connectors and twist locks.

    This function generates an open curve based on the provided parameters.
    It creates a shape using the specified thickness and diameter, applies
    tolerances, and optionally adds puzzle connectors at the ends of the
    curve. Additionally, it can incorporate twist lock connectors either at
    the puzzle connection or distributed along the curve. The function
    utilizes various geometric transformations to position and modify the
    shapes as needed.

    Args:
        line (shapely.geometry.LineString): The shapely LineString object representing the curve.
        thick (float): The thickness of the bar used in the construction.
        diameter (float): The diameter of the tool for joint creation.
        tolerance (float): The tolerance applied in the joint.
        amount (int?): The number of fingers in the joint; 0 means auto-generate. Defaults to
            0.
        stem (float?): The radius of the stem or neck of the joint. Defaults to 1.
        twist (bool?): Whether to add twist lock connectors. Defaults to False.
        t_neck (float?): The percentage of thickness for the twist neck compared to thick.
            Defaults to 0.5.
        t_thick (float?): The thickness of the twist material. Defaults to 0.01.
        twist_amount (int?): The amount of twist distributed along the curve, not counting joint
            twists. Defaults to 1.
        which (str?): Specifies the type of joint; options include 'M', 'F', 'MF', 'MM', 'FF'.
            Defaults to 'MF'.
        twist_keep (bool?): Whether to keep the twist locks after creation. Defaults to False.

    Returns:
        None: This function does not return a value but modifies the 3D scene
            directly.
    """

    # puts puzzle connectors at the end of an open curve
    # optionally puts twist lock connectors at the puzzle connection
    # optionally puts twist lock connectors along the open curve
    # line = shapely linestring
    # thick = thickness of the bar
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # twist_amount = twist amount distributed on the curve not counting the joint twist locks
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # Which M,F, MF, MM, FF

    coords = list(line.coords)

    start_angle = joinery.angle(coords[0], coords[1]) + pi/2
    end_angle = joinery.angle(coords[-1], coords[-2]) + pi/2
    p_start = coords[0]
    p_end = coords[-1]

    print('start angle', start_angle)
    print('end angle', end_angle)

    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=thick*2, Simple_length=thick * 2, use_cyclic_u=True, edit_mode=False, shape='3D')
    simple.active_name('tmprect')
    simple.move(y=thick)
    simple.duplicate()
    simple.rotate(start_angle)
    simple.move(x=p_start[0], y=p_start[1])
    simple.make_active('tmprect')
    simple.rotate(end_angle)
    simple.move(x=p_end[0], y=p_end[1])
    simple.union('tmprect')
    dilated = line.buffer(thick/2)  # expand shapely object to thickness
    utils.shapelyToCurve('tmp_curve', dilated, 0.0)
    # truncate curve at both ends with the rectangles
    simple.difference('tmp', 'tmp_curve')

    fingers(diameter, tolerance, amount, stem=stem)
    simple.make_active('fingers')
    simple.rotate(end_angle)
    simple.move(x=p_end[0], y=p_end[1])
    simple.active_name('tmp_fingers')
    simple.union('tmp_')
    simple.active_name('tmp_curve')
    twistm('tmp_curve', thick, diameter, tolerance, twist, t_neck, t_thick, end_angle, x=p_end[0], y=p_end[1],
           twist_keep=twist_keep)

    twistf('receptacle', thick, diameter, tolerance, twist, t_neck, t_thick, twist_keep=twist_keep)
    simple.rename('receptacle', 'tmp')
    simple.rotate(start_angle+pi)
    simple.move(x=p_start[0], y=p_start[1])
    simple.difference('tmp', 'tmp_curve')
    if twist_keep:
        simple.make_active('twist_keep_f')
        simple.rotate(start_angle + pi)
        simple.move(x=p_start[0], y=p_start[1])

    if twist_amount > 0 and twist:
        twist_start = line.length / (twist_amount+1)
        joinery.distributed_interlock(line, line.length, thick, t_thick, tolerance, twist_amount,
                                      tangent=pi/2, fixed_angle=0, start=twist_start, end=twist_start,
                                      closed=False, type='TWIST', twist_percentage=t_neck)
        if twist_keep:
            simple.duplicate()
            simple.active_name('twist_keep')
            simple.join_multiple('twist_keep')
            simple.make_active('interlock')

        simple.active_name('tmp_twist')
        simple.difference('tmp', 'tmp_curve')
        simple.active_name('puzzle_curve')


def tile(diameter, tolerance, tile_x_amount, tile_y_amount, stem=1):
    """Create a tile shape based on specified dimensions and parameters.

    This function calculates the dimensions of a tile based on the provided
    diameter, tolerance, and the number of tiles in the x and y directions.
    It uses these dimensions to create a rectangular shape and performs
    various geometric operations to generate the final tile design. The
    function also interacts with a global drawing context to manage the
    shapes created during the process.

    Args:
        diameter (float): The base diameter of the tile.
        tolerance (float): The tolerance value for the tile design.
        tile_x_amount (int): The number of tiles along the x-axis.
        tile_y_amount (int): The number of tiles along the y-axis.
        stem (int?): A parameter that affects the tile dimensions. Defaults to 1.
    """

    global DT
    diameter = diameter * DT
    width = ((tile_x_amount) * (4 + 2 * (stem-1)) + 1) * diameter
    height = ((tile_y_amount) * (4 + 2 * (stem - 1)) + 1) * diameter

    print('size:', width, height)
    fingers(diameter, tolerance, amount=tile_x_amount, stem=stem)
    simple.add_rectangle(width, height)
    simple.active_name('_base')

    simple.make_active('fingers')
    simple.active_name('_fingers')
    simple.intersect('_')
    simple.remove_multiple('_fingers')
    simple.rename('intersection', '_fingers')
    simple.move(y=height/2)
    simple.union('_')
    simple.active_name('_base')
    simple.remove_doubles()
    simple.rename('receptacle', '_receptacle')
    simple.move(y=-height/2)
    simple.difference('_', '_base')
    simple.active_name('base')
    fingers(diameter, tolerance, amount=tile_y_amount, stem=stem)
    simple.rename('base', '_base')
    simple.remove_doubles()
    simple.rename('fingers', '_fingers')
    simple.rotate(pi/2)
    simple.move(x=-width/2)
    simple.union('_')
    simple.active_name('_base')
    simple.rename('receptacle', '_receptacle')
    simple.rotate(pi/2)
    simple.move(x=width/2)
    simple.difference('_', '_base')
    simple.active_name('tile_ ' + str(tile_x_amount) + '_' + str(tile_y_amount))
