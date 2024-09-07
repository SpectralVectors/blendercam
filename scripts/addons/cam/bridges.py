"""BlenderCAM 'bridges.py' © 2012 Vilem Novak

Functions to add Bridges / Tabs to meshes or curves.
Called with Operators defined in 'ops.py'
"""

from math import (
    hypot,
    pi,
)

from shapely import ops as sops
from shapely import geometry as sgeometry
from shapely import prepared

import bpy
from bpy_extras.object_utils import object_data_add
from mathutils import Vector

from . import utils
from . import simple


def addBridge(x, y, rot, sizex, sizey):
    """Add a bridge mesh object to the Blender scene.

    This function creates a bridge by adding a primitive plane, adjusting
    its dimensions, and converting it into a curve. The bridge is positioned
    and rotated based on the provided parameters. The function also applies
    transformations to ensure the mesh is correctly sized and oriented in
    the 3D space.

    Args:
        x (float): The x-coordinate for the bridge's location.
        y (float): The y-coordinate for the bridge's location.
        rot (float): The rotation angle around the z-axis in radians.
        sizex (float): The width of the bridge.
        sizey (float): The height of the bridge.

    Returns:
        bpy.types.Object: The created bridge object in Blender.
    """

    bpy.ops.mesh.primitive_plane_add(size=sizey*2, calc_uvs=True, enter_editmode=False, align='WORLD',
                                     location=(0, 0, 0), rotation=(0, 0, 0))
    b = bpy.context.active_object
    b.name = 'bridge'
    # b.show_name=True
    b.dimensions.x = sizex
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    bpy.ops.object.editmode_toggle()
    bpy.ops.transform.translate(value=(0, sizey / 2, 0), constraint_axis=(False, True, False),
                                orient_type='GLOBAL', mirror=False, use_proportional_edit=False,
                                proportional_edit_falloff='SMOOTH', proportional_size=1)
    bpy.ops.object.editmode_toggle()
    bpy.ops.object.convert(target='CURVE')

    b.location = x, y, 0
    b.rotation_euler.z = rot
    return b


def addAutoBridges(o):
    """Attempt to add auto bridges as a set of curves.

    This function checks if a collection for bridges exists in the Blender
    data. If not, it creates a new collection and links it to the current
    context. The function then iterates through the objects in the provided
    input, converting curves and meshes into geometries. For each geometry,
    it calculates the bounds and projects points to create bridges at
    specified locations around the geometry. The bridges are then linked to
    the collection and unlinked from the current context.

    Args:
        o: An object containing properties such as `bridges_collection_name`,
            `objects`, `bridges_width`, and `cutter_diameter`.

    Returns:
        None: This function does not return a value but modifies the Blender
        data directly by adding bridge objects to the specified collection.
    """
    utils.getOperationSources(o)
    bridgecollectionname = o.bridges_collection_name
    if bridgecollectionname == '' or bpy.data.collections.get(bridgecollectionname) is None:
        bridgecollectionname = 'bridges_' + o.name
        bpy.data.collections.new(bridgecollectionname)
        bpy.context.collection.children.link(bpy.data.collections[bridgecollectionname])
    g = bpy.data.collections[bridgecollectionname]
    o.bridges_collection_name = bridgecollectionname
    for ob in o.objects:

        if ob.type == 'CURVE' or ob.type == 'TEXT':
            curve = utils.curveToShapely(ob)
        if ob.type == 'MESH':
            curve = utils.getObjectSilhouete('OBJECTS', [ob])
        for c in curve.geoms:
            c = c.exterior
            minx, miny, maxx, maxy = c.bounds
            d1 = c.project(sgeometry.Point(maxx + 1000, (maxy + miny) / 2.0))
            p = c.interpolate(d1)
            bo = addBridge(p.x, p.y, -pi / 2, o.bridges_width, o.cutter_diameter * 1)
            g.objects.link(bo)
            bpy.context.collection.objects.unlink(bo)
            d1 = c.project(sgeometry.Point(minx - 1000, (maxy + miny) / 2.0))
            p = c.interpolate(d1)
            bo = addBridge(p.x, p.y, pi / 2, o.bridges_width, o.cutter_diameter * 1)
            g.objects.link(bo)
            bpy.context.collection.objects.unlink(bo)
            d1 = c.project(sgeometry.Point((minx + maxx) / 2.0, maxy + 1000))
            p = c.interpolate(d1)
            bo = addBridge(p.x, p.y, 0, o.bridges_width, o.cutter_diameter * 1)
            g.objects.link(bo)
            bpy.context.collection.objects.unlink(bo)
            d1 = c.project(sgeometry.Point((minx + maxx) / 2.0, miny - 1000))
            p = c.interpolate(d1)
            bo = addBridge(p.x, p.y, pi, o.bridges_width, o.cutter_diameter * 1)
            g.objects.link(bo)
            bpy.context.collection.objects.unlink(bo)


def getBridgesPoly(o):
    """Generate and prepare bridge polygons from a Blender object.

    This function checks if the provided object has a 'bridgespolyorig'
    attribute. If not, it retrieves the bridge collection associated with
    the object, selects all curve objects within that collection, duplicates
    and joins them into a single object. The resulting shape is then
    converted to a Shapely object. After processing, the function creates a
    buffered polygon to represent the bridges, ensuring that they are not
    milled. The buffered polygon and its boundary are stored in the object's
    attributes for further use.

    Args:
        o (object): The object containing bridge collection information and
            attributes for storing the generated polygons.
    """

    if not hasattr(o, 'bridgespolyorig'):
        bridgecollectionname = o.bridges_collection_name
        bridgecollection = bpy.data.collections[bridgecollectionname]
        bpy.ops.object.select_all(action='DESELECT')

        for ob in bridgecollection.objects:
            if ob.type == 'CURVE':
                ob.select_set(state=True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.duplicate()
        bpy.ops.object.join()
        ob = bpy.context.active_object
        shapes = utils.curveToShapely(ob, o.use_bridge_modifiers)
        ob.select_set(state=True)
        bpy.ops.object.delete(use_global=False)
        bridgespoly = sops.unary_union(shapes)

        # buffer the poly, so the bridges are not actually milled...
        o.bridgespolyorig = bridgespoly.buffer(distance=o.cutter_diameter / 2.0)
        o.bridgespoly_boundary = o.bridgespolyorig.boundary
        o.bridgespoly_boundary_prep = prepared.prep(o.bridgespolyorig.boundary)
        o.bridgespoly = prepared.prep(o.bridgespolyorig)


def useBridges(ch, o):
    """Add bridges to chunks using a collection of bridge objects.

    This function takes a collection of bridge objects and utilizes the
    curves within it to create bridges over specified chunks. It calculates
    the necessary heights and intersections with the chunk geometry,
    adjusting the points accordingly. The resulting points are then used to
    generate a new mesh that represents the bridges, which is subsequently
    converted into a curve object in Blender.

    Args:
        ch (Chunk): The chunk object to which bridges will be added.
        o (Options): An object containing options such as bridge height,
            collection name, and other parameters.

    Returns:
        None: This function modifies the chunk object in place and does not return a
            value.
    """
    bridgecollectionname = o.bridges_collection_name
    bridgecollection = bpy.data.collections[bridgecollectionname]
    if len(bridgecollection.objects) > 0:

        # get bridgepoly
        getBridgesPoly(o)

        ####

        bridgeheight = min(o.max.z, o.min.z + abs(o.bridges_height))

        vi = 0
        newpoints = []
        ch_points = ch.get_points_np()
        p1 = sgeometry.Point(ch_points[0])
        startinside = o.bridgespoly.contains(p1)
        interrupted = False
        verts = []
        edges = []
        faces = []
        while vi < len(ch_points):
            i1 = vi
            i2 = vi
            chp1 = ch_points[i1]
            # Vector(v1)#this is for case of last point and not closed chunk..
            chp2 = ch_points[i1]
            if vi + 1 < len(ch_points):
                i2 = vi + 1
                chp2 = ch_points[vi + 1]  # Vector(ch_points[vi+1])
            v1 = Vector(chp1)
            v2 = Vector(chp2)
            if v1.z < bridgeheight or v2.z < bridgeheight:
                v = v2 - v1
                p2 = sgeometry.Point(chp2)

                if interrupted:
                    p1 = sgeometry.Point(chp1)
                    startinside = o.bridgespoly.contains(p1)
                    interrupted = False

                endinside = o.bridgespoly.contains(p2)
                l = sgeometry.LineString([chp1, chp2])
                if o.bridgespoly_boundary_prep.intersects(l):
                    intersections = o.bridgespoly_boundary.intersection(l)

                else:
                    intersections = sgeometry.GeometryCollection()

                itpoint = intersections.geom_type == 'Point'
                itmpoint = intersections.geom_type == 'MultiPoint'

                if not startinside:
                    newpoints.append(chp1)
                elif startinside:
                    newpoints.append((chp1[0], chp1[1], max(chp1[2], bridgeheight)))
                cpoints = []
                if itpoint:
                    pt = Vector((intersections.x, intersections.y, intersections.z))
                    cpoints = [pt]

                elif itmpoint:
                    cpoints = []
                    for p in intersections.geoms:
                        pt = Vector((p.x, p.y, p.z))
                        cpoints.append(pt)
                # ####sort collisions here :(
                ncpoints = []
                while len(cpoints) > 0:
                    mind = 10000000
                    mini = -1
                    for i, p in enumerate(cpoints):
                        if min(mind, (p - v1).length) < mind:
                            mini = i
                            mind = (p - v1).length
                    ncpoints.append(cpoints.pop(mini))
                cpoints = ncpoints
                # endsorting

                if startinside:
                    isinside = True
                else:
                    isinside = False
                for cp in cpoints:
                    v3 = cp
                    # print(v3)
                    if v.length == 0:
                        ratio = 1
                    else:
                        fractvect = v3 - v1
                        ratio = fractvect.length / v.length

                    collisionz = v1.z + v.z * ratio
                    np1 = (v3.x, v3.y, collisionz)
                    np2 = (v3.x, v3.y, max(collisionz, bridgeheight))
                    if not isinside:
                        newpoints.extend((np1, np2))
                    else:
                        newpoints.extend((np2, np1))
                    isinside = not isinside

                startinside = endinside
                vi += 1
            else:
                newpoints.append(chp1)
                vi += 1
                interrupted = True
        ch.set_points(newpoints)

    # create bridge cut curve here
    count = 0
    isedge = 0
    x2, y2 = 0, 0
    for pt in newpoints:
        x = pt[0]
        y = pt[1]
        z = pt[2]
        if z == bridgeheight:   # find all points with z = bridge height
            count += 1
            if isedge == 1:     # This is to subdivide  edges which are longer than the width of the bridge
                edgelength = hypot(x - x2, y - y2)
                if edgelength > o.bridges_width:
                    # make new vertex
                    verts.append(((x + x2)/2, (y + y2)/2, o.minz))

                    isedge += 1
                    edge = [count - 2, count - 1]
                    edges.append(edge)
                    count += 1
            else:
                x2 = x
                y2 = y
            verts.append((x, y, o.minz))    # make new vertex
            isedge += 1
            if isedge > 1:  # Two points make an edge
                edge = [count - 2, count - 1]
                edges.append(edge)

        else:
            isedge = 0

    #  verify if vertices have been generated and generate a mesh
    if verts:
        mesh = bpy.data.meshes.new(name=o.name + "_cut_bridges")  # generate new mesh
        # integrate coordinates and edges
        mesh.from_pydata(verts, edges, faces)
        object_data_add(bpy.context, mesh)      # create object
        bpy.ops.object.convert(target='CURVE')  # convert mesh to curve
        # join all the new cut bridges curves
        simple.join_multiple(o.name + '_cut_bridges')
        simple.remove_doubles()     # remove overlapping vertices


def auto_cut_bridge(o):
    """Automatically cuts the bridge objects in a specified collection.

    This function retrieves a collection of bridge objects from the Blender
    data using the provided object `o`. If the collection contains any
    objects, it prints "bridges". This function is intended for use within a
    Blender environment where collections and objects are managed through
    the Blender Python API (bpy).

    Args:
        o (object): An object that contains the name of the bridges collection.

    Returns:
        None: This function does not return any value.
    """

    bridgecollectionname = o.bridges_collection_name
    bridgecollection = bpy.data.collections[bridgecollectionname]
    if len(bridgecollection.objects) > 0:
        print("bridges")
