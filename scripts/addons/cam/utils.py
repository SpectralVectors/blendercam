"""BlenderCAM 'utils.py' © 2012 Vilem Novak

Main functionality of BlenderCAM.
The functions here are called with operators defined in 'ops.py'
"""

from math import (
    ceil,
    pi
)
from pathlib import Path
import pickle
import shutil
import sys
import time

import numpy
import shapely
from shapely import ops as sops
from shapely import geometry as sgeometry
from shapely.geometry import polygon as spolygon
from shapely.geometry import MultiPolygon

import bpy
from bpy.app.handlers import persistent
from bpy_extras import object_utils
from mathutils import Euler, Vector

from .async_op import progress_async
from .cam_chunk import (
    curveToChunks,
    parentChild,
    camPathChunk,
    camPathChunkBuilder,
    parentChildDist,
    chunksToShapely
)
from .collision import (
    getSampleBullet,
    getSampleBulletNAxis,
    prepareBulletCollision
)
from .exception import CamException
from .image_utils import (
    imageToChunks,
    getSampleImage,
    renderSampleImage,
    prepareArea,
)
from .opencamlib.opencamlib import (
    oclSample,
    oclResampleChunks,
)
from .polygon_utils_cam import shapelyToCurve, shapelyToMultipolygon
from .simple import (
    activate,
    progress,
    select_multiple,
    delob,
    timingadd,
    timinginit,
    timingstart,
    tuple_add,
    tuple_mul,
    tuple_sub,
    isVerticalLimit,
    getCachePath
)

# from shapely.geometry import * not possible until Polygon libs gets out finally..
SHAPELY = True


# Import OpencamLib
# Return available OpenCamLib version on success, None otherwise
def opencamlib_version():
    """Return the version of the OpenCamLib library.

    This function attempts to import the OpenCamLib library and returns its
    version. If the library is not available, it will return None. The
    function first tries to import the library as 'ocl' and if that fails,
    it attempts to import it as 'opencamlib'. If both imports fail, the
    function will return None.

    Returns:
        str or None: The version of OpenCamLib if available, None otherwise.
    """

    try:
        import ocl
    except ImportError:
        try:
            import opencamlib as ocl
        except ImportError as e:
            return
    return ocl.version()


def positionObject(operation):
    """Position an object based on specified operation parameters.

    This function adjusts the location of a Blender object according to the
    provided operation settings. It calculates the bounding box of the
    object and repositions it based on the specified material properties,
    such as centering and vertical positioning (above, below, or centered).
    The function also applies the transformation to the object if it is not
    of type 'CURVE'.

    Args:
        operation (OperationType): An object containing the necessary parameters
            for positioning, including object name, material settings, and
            whether to use modifiers.

    Returns:
        None: This function does not return a value; it modifies the object's
            location in place.
    """

    ob = bpy.data.objects[operation.object_name]
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

    minx, miny, minz, maxx, maxy, maxz = getBoundsWorldspace([ob], operation.use_modifiers)
    totx = maxx - minx
    toty = maxy - miny
    totz = maxz - minz
    if operation.material.center_x:
        ob.location.x -= minx + totx / 2
    else:
        ob.location.x -= minx

    if operation.material.center_y:
        ob.location.y -= miny + toty / 2
    else:
        ob.location.y -= miny

    if operation.material.z_position == 'BELOW':
        ob.location.z -= maxz
    elif operation.material.z_position == 'ABOVE':
        ob.location.z -= minz
    elif operation.material.z_position == 'CENTERED':
        ob.location.z -= minz + totz / 2

    if ob.type != 'CURVE':
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    # addMaterialAreaObject()


def getBoundsWorldspace(obs, use_modifiers=False):
    """Get the bounding box of a collection of objects in world space.

    This function calculates the minimum and maximum coordinates of the
    bounding box that encompasses all the specified objects in world space.
    It iterates through each object, taking into account their type (MESH,
    FONT, or other) and whether to apply modifiers. For MESH objects, it
    retrieves the vertices' world coordinates, while for FONT objects, it
    duplicates and converts them to MESH before processing. The function
    raises an exception if an unsupported object type is encountered.

    Args:
        obs (list): A list of Blender objects to calculate bounds for.
        use_modifiers (bool): Whether to apply modifiers to the objects
            before calculating bounds. Defaults to False.

    Returns:
        tuple: A tuple containing the minimum and maximum coordinates
            (minx, miny, minz, maxx, maxy, maxz) of the bounding box.

    Raises:
        CamException: If an unsupported object type is encountered that
            cannot be processed for CAM operations.
    """

    # progress('getting bounds of object(s)')
    t = time.time()

    maxx = maxy = maxz = -10000000
    minx = miny = minz = 10000000
    for ob in obs:
        # bb=ob.bound_box
        mw = ob.matrix_world
        if ob.type == 'MESH':
            if use_modifiers:
                depsgraph = bpy.context.evaluated_depsgraph_get()
                mesh_owner = ob.evaluated_get(depsgraph)
                mesh = mesh_owner.to_mesh()
            else:
                mesh = ob.data

            for c in mesh.vertices:
                coord = c.co
                worldCoord = mw @ Vector((coord[0], coord[1], coord[2]))
                minx = min(minx, worldCoord.x)
                miny = min(miny, worldCoord.y)
                minz = min(minz, worldCoord.z)
                maxx = max(maxx, worldCoord.x)
                maxy = max(maxy, worldCoord.y)
                maxz = max(maxz, worldCoord.z)

            if use_modifiers:
                mesh_owner.to_mesh_clear()

        elif ob.type == "FONT":
            activate(ob)
            bpy.ops.object.duplicate()
            co = bpy.context.active_object
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            bpy.ops.object.convert(target='MESH', keep_original=False)
            mesh = co.data
            for c in mesh.vertices:
                coord = c.co
                worldCoord = mw @ Vector((coord[0], coord[1], coord[2]))
                minx = min(minx, worldCoord.x)
                miny = min(miny, worldCoord.y)
                minz = min(minz, worldCoord.z)
                maxx = max(maxx, worldCoord.x)
                maxy = max(maxy, worldCoord.y)
                maxz = max(maxz, worldCoord.z)
            bpy.ops.object.delete()
            bpy.ops.outliner.orphans_purge()
        else:
            if not hasattr(ob.data, "splines"):
                raise CamException("Can't do CAM operation on the selected object type")
            # for coord in bb:
            for c in ob.data.splines:
                for p in c.bezier_points:
                    coord = p.co
                    # this can work badly with some imported curves, don't know why...
                    # worldCoord = mw * Vector((coord[0]/ob.scale.x, coord[1]/ob.scale.y, coord[2]/ob.scale.z))
                    worldCoord = mw @ Vector((coord[0], coord[1], coord[2]))
                    minx = min(minx, worldCoord.x)
                    miny = min(miny, worldCoord.y)
                    minz = min(minz, worldCoord.z)
                    maxx = max(maxx, worldCoord.x)
                    maxy = max(maxy, worldCoord.y)
                    maxz = max(maxz, worldCoord.z)
                for p in c.points:
                    coord = p.co
                    # this can work badly with some imported curves, don't know why...
                    # worldCoord = mw * Vector((coord[0]/ob.scale.x, coord[1]/ob.scale.y, coord[2]/ob.scale.z))
                    worldCoord = mw @ Vector((coord[0], coord[1], coord[2]))
                    minx = min(minx, worldCoord.x)
                    miny = min(miny, worldCoord.y)
                    minz = min(minz, worldCoord.z)
                    maxx = max(maxx, worldCoord.x)
                    maxy = max(maxy, worldCoord.y)
                    maxz = max(maxz, worldCoord.z)
    # progress(time.time()-t)
    return minx, miny, minz, maxx, maxy, maxz


def getSplineBounds(ob, curve):
    """Get the bounding box of a given object and its associated curve.

    This function calculates the minimum and maximum coordinates (x, y, z)
    of an object based on its world matrix and the coordinates of its
    associated curve's bezier points and regular points. It iterates through
    the points of the curve to determine the bounding box in 3D space.

    Args:
        ob (Object): The object whose bounds are to be calculated.
        curve (Curve): The curve associated with the object.

    Returns:
        tuple: A tuple containing the minimum and maximum coordinates
            (minx, miny, minz, maxx, maxy, maxz) of the bounding box.
    """

    # progress('getting bounds of object(s)')
    maxx = maxy = maxz = -10000000
    minx = miny = minz = 10000000
    mw = ob.matrix_world

    for p in curve.bezier_points:
        coord = p.co
        # this can work badly with some imported curves, don't know why...
        # worldCoord = mw * Vector((coord[0]/ob.scale.x, coord[1]/ob.scale.y, coord[2]/ob.scale.z))
        worldCoord = mw @ Vector((coord[0], coord[1], coord[2]))
        minx = min(minx, worldCoord.x)
        miny = min(miny, worldCoord.y)
        minz = min(minz, worldCoord.z)
        maxx = max(maxx, worldCoord.x)
        maxy = max(maxy, worldCoord.y)
        maxz = max(maxz, worldCoord.z)
    for p in curve.points:
        coord = p.co
        # this can work badly with some imported curves, don't know why...
        # worldCoord = mw * Vector((coord[0]/ob.scale.x, coord[1]/ob.scale.y, coord[2]/ob.scale.z))
        worldCoord = mw @ Vector((coord[0], coord[1], coord[2]))
        minx = min(minx, worldCoord.x)
        miny = min(miny, worldCoord.y)
        minz = min(minz, worldCoord.z)
        maxx = max(maxx, worldCoord.x)
        maxy = max(maxy, worldCoord.y)
        maxz = max(maxz, worldCoord.z)
    # progress(time.time()-t)
    return minx, miny, minz, maxx, maxy, maxz


def getOperationSources(o):
    """Get the operation sources based on the geometry source type.

    This function determines the operation sources for a given object based
    on its geometry source type. It handles three types of geometry sources:
    'OBJECT', 'COLLECTION', and 'IMAGE'. For 'OBJECT', it selects the
    specified object and sets its rotation based on the provided parameters.
    For 'COLLECTION', it retrieves all objects in the specified collection.
    For 'IMAGE', it sets a specific optimization flag. The function also
    checks if the objects are curves or meshes based on the geometry source
    type.

    Args:
        o (object): An object containing properties such as geometry_source,

    Returns:
        None: This function modifies the input object in place and does not
        return a value.
    """

    if o.geometry_source == 'OBJECT':
        # bpy.ops.object.select_all(action='DESELECT')
        ob = bpy.data.objects[o.object_name]
        o.objects = [ob]
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        if o.enable_B or o.enable_A:
            if o.old_rotation_A != o.rotation_A or o.old_rotation_B != o.rotation_B:
                o.old_rotation_A = o.rotation_A
                o.old_rotation_B = o.rotation_B
                ob = bpy.data.objects[o.object_name]
                ob.select_set(True)
                bpy.context.view_layer.objects.active = ob
                if o.A_along_x:  # A parallel with X
                    if o.enable_A:
                        bpy.context.active_object.rotation_euler.x = o.rotation_A
                    if o.enable_B:
                        bpy.context.active_object.rotation_euler.y = o.rotation_B
                else:  # A parallel with Y
                    if o.enable_A:
                        bpy.context.active_object.rotation_euler.y = o.rotation_A
                    if o.enable_B:
                        bpy.context.active_object.rotation_euler.x = o.rotation_B

    elif o.geometry_source == 'COLLECTION':
        collection = bpy.data.collections[o.collection_name]
        o.objects = collection.objects
    elif o.geometry_source == 'IMAGE':
        o.optimisation.use_exact = False

    if o.geometry_source == 'OBJECT' or o.geometry_source == 'COLLECTION':
        o.onlycurves = True
        for ob in o.objects:
            if ob.type == 'MESH':
                o.onlycurves = False
    else:
        o.onlycurves = False


def getBounds(o):
    """Calculate the bounding box for a given object.

    This function determines the minimum and maximum coordinates of an
    object's bounding box based on its geometry source. It handles different
    geometry types, including OBJECT, COLLECTION, and CURVE, and adjusts the
    bounding box dimensions based on material properties and image cropping
    settings if applicable. The function also checks if the calculated
    dimensions exceed the machine's working area and updates the warnings
    accordingly.

    Args:
        o (Object): An object containing properties such as geometry_source, material, and
            source_image_name.
    """

    # print('kolikrat sem rpijde')
    if o.geometry_source == 'OBJECT' or o.geometry_source == 'COLLECTION' or o.geometry_source == 'CURVE':
        print("Valid Geometry")
        minx, miny, minz, maxx, maxy, maxz = getBoundsWorldspace(o.objects, o.use_modifiers)

        if o.minz_from == 'OBJECT':
            if minz == 10000000:
                minz = 0
            print("Minz from Object:" + str(minz))
            o.min.z = minz
            o.minz = o.min.z
        else:
            o.min.z = o.minz  # max(bb[0][2]+l.z,o.minz)#
            print("Not Minz from Object")

        if o.material.estimate_from_model:
            print("Estimate Material from Model")

            o.min.x = minx - o.material.radius_around_model
            o.min.y = miny - o.material.radius_around_model
            o.max.z = max(o.maxz, maxz)

            o.max.x = maxx + o.material.radius_around_model
            o.max.y = maxy + o.material.radius_around_model
        else:
            print("Not Material from Model")
            o.min.x = o.material.origin.x
            o.min.y = o.material.origin.y
            o.min.z = o.material.origin.z - o.material.size.z
            o.max.x = o.min.x + o.material.size.x
            o.max.y = o.min.y + o.material.size.y
            o.max.z = o.material.origin.z

    else:
        i = bpy.data.images[o.source_image_name]
        if o.source_image_crop:
            sx = int(i.size[0] * o.source_image_crop_start_x / 100)
            ex = int(i.size[0] * o.source_image_crop_end_x / 100)
            sy = int(i.size[1] * o.source_image_crop_start_y / 100)
            ey = int(i.size[1] * o.source_image_crop_end_y / 100)
        else:
            sx = 0
            ex = i.size[0]
            sy = 0
            ey = i.size[1]

        o.optimisation.pixsize = o.source_image_size_x / i.size[0]

        o.min.x = o.source_image_offset.x + sx * o.optimisation.pixsize
        o.max.x = o.source_image_offset.x + ex * o.optimisation.pixsize
        o.min.y = o.source_image_offset.y + sy * o.optimisation.pixsize
        o.max.y = o.source_image_offset.y + ey * o.optimisation.pixsize
        o.min.z = o.source_image_offset.z + o.minz
        o.max.z = o.source_image_offset.z
    s = bpy.context.scene
    m = s.cam_machine
    # make sure this message only shows once and goes away once fixed
    o.info.warnings.replace('Operation Exceeds Your Machine Limits\n', '')
    if o.max.x - o.min.x > m.working_area.x or o.max.y - o.min.y > m.working_area.y \
            or o.max.z - o.min.z > m.working_area.z:
        o.info.warnings += 'Operation Exceeds Your Machine Limits\n'


def getBoundsMultiple(operations):
    """Gets bounds of multiple operations for simulations or rest milling.

    This function iterates through a list of operations to determine the
    minimum and maximum bounds in three-dimensional space (x, y, z). It
    initializes extreme values for the bounds and updates them based on the
    bounds of each operation. The function is designed for use in
    simulations or milling processes, although it is noted to be highly
    suboptimal.

    Args:
        operations (list): A list of operation objects, each having
            'min' and 'max' attributes with 'x', 'y', and 'z' properties.

    Returns:
        tuple: A tuple containing the minimum and maximum bounds in the
            order (minx, miny, minz, maxx, maxy, maxz).
    """
    maxx = maxy = maxz = -10000000
    minx = miny = minz = 10000000
    for o in operations:
        getBounds(o)
        maxx = max(maxx, o.max.x)
        maxy = max(maxy, o.max.y)
        maxz = max(maxz, o.max.z)
        minx = min(minx, o.min.x)
        miny = min(miny, o.min.y)
        minz = min(minz, o.min.z)

    return minx, miny, minz, maxx, maxy, maxz


def samplePathLow(o, ch1, ch2, dosample):
    """Generate a sample path between two channels.

    This function calculates a series of points along a path defined by two
    channel objects. It computes the vector between the two channels and
    generates points along this vector based on the specified distance. If
    sampling is enabled, it retrieves height information from either a
    bullet collision detection method or an image sampling method to adjust
    the z-coordinates of the generated points.

    Args:
        o (object): An object containing optimization parameters and properties.
        ch1 (object): The first channel object used to define the starting point of the path.
        ch2 (object): The second channel object used to define the endpoint of the path.
        dosample (bool): A flag indicating whether to perform sampling on the generated points.

    Returns:
        camPathChunk: A collection of points representing the sampled path.
    """

    v1 = Vector(ch1.get_point(-1))
    v2 = Vector(ch2.get_point(0))

    v = v2 - v1
    d = v.length
    v.normalize()

    vref = Vector((0, 0, 0))
    bpath_points = []
    i = 0
    while vref.length < d:
        i += 1
        vref = v * o.dist_along_paths * i
        if vref.length < d:
            p = v1 + vref
            bpath_points.append([p.x, p.y, p.z])
    # print('between path')
    # print(len(bpath))
    pixsize = o.optimisation.pixsize
    if dosample:
        if not (o.optimisation.use_opencamlib and o.optimisation.use_exact):
            if o.optimisation.use_exact:
                if o.update_bullet_collision_tag:
                    prepareBulletCollision(o)
                    o.update_bullet_collision_tag = False

                cutterdepth = o.cutter_shape.dimensions.z / 2
                for p in bpath_points:
                    z = getSampleBullet(o.cutter_shape, p[0], p[1], cutterdepth, 1, o.minz)
                    if z > p[2]:
                        p[2] = z
            else:
                for p in bpath_points:
                    xs = (p[0] - o.min.x) / pixsize + o.borderwidth + pixsize / 2  # -m
                    ys = (p[1] - o.min.y) / pixsize + o.borderwidth + pixsize / 2  # -m
                    z = getSampleImage((xs, ys), o.offset_image, o.minz) + o.skin
                    if z > p[2]:
                        p[2] = z
    return camPathChunk(bpath_points)


# def threadedSampling():#not really possible at all without running more blenders for same operation :( python!
# samples in both modes now - image and bullet collision too.
async def sampleChunks(o, pathSamples, layers):
    """Sample chunks of paths based on provided parameters.

    This function processes a set of path samples and layers to generate
    chunks of sampled points. It takes into account various optimization
    strategies and conditions, including collision detection and ambient
    checks. The function iterates through the provided path samples,
    determining the appropriate z-coordinate for each sample based on the
    specified layers and strategies. It also manages the relationships
    between chunks to ensure proper connectivity.

    Args:
        o (object): An object containing various parameters and settings
            related to the sampling process.
        pathSamples (list): A list of path samples to be processed.
        layers (list): A list of layers defining the z-coordinate ranges
            for sampling.

    Returns:
        list: A list of sampled chunks generated from the provided path
            samples and layers.
    """

    #
    minx, miny, minz, maxx, maxy, maxz = o.min.x, o.min.y, o.min.z, o.max.x, o.max.y, o.max.z
    getAmbient(o)

    if o.optimisation.use_exact:  # prepare collision world
        if o.optimisation.use_opencamlib:
            await oclSample(o, pathSamples)
            cutterdepth = 0
        else:
            if o.update_bullet_collision_tag:
                prepareBulletCollision(o)

                o.update_bullet_collision_tag = False
            # print (o.ambient)
            cutter = o.cutter_shape
            cutterdepth = cutter.dimensions.z / 2
    else:
        # or prepare offset image, but not in some strategies.
        if o.strategy != 'WATERLINE':
            await prepareArea(o)

        pixsize = o.optimisation.pixsize

        coordoffset = o.borderwidth + pixsize / 2  # -m

        res = ceil(o.cutter_diameter / o.optimisation.pixsize)
        m = res / 2

    t = time.time()
    # print('sampling paths')

    totlen = 0  # total length of all chunks, to estimate sampling time.
    for ch in pathSamples:
        totlen += ch.count()
    layerchunks = []
    minz = o.minz - 0.000001  # correction for image method problems
    layeractivechunks = []
    lastrunchunks = []

    for l in layers:
        layerchunks.append([])
        layeractivechunks.append(camPathChunkBuilder([]))
        lastrunchunks.append([])

    zinvert = 0
    if o.inverse:
        ob = bpy.data.objects[o.object_name]
        zinvert = ob.location.z + maxz  # ob.bound_box[6][2]

    print(f"Total Sample Points {totlen}")

    n = 0
    last_percent = -1
    # timing for optimisation
    samplingtime = timinginit()
    sortingtime = timinginit()
    totaltime = timinginit()
    timingstart(totaltime)
    lastz = minz
    for patternchunk in pathSamples:
        thisrunchunks = []
        for l in layers:
            thisrunchunks.append([])
        lastlayer = None
        currentlayer = None
        lastsample = None
        # threads_count=4

        # for t in range(0,threads):
        our_points = patternchunk.get_points_np()
        ambient_contains = shapely.contains(o.ambient, shapely.points(our_points[:, 0:2]))
        for s, in_ambient in zip(our_points, ambient_contains):
            if o.strategy != 'WATERLINE' and int(100 * n / totlen) != last_percent:
                last_percent = int(100 * n / totlen)
                await progress_async('sampling paths ', last_percent)
            n += 1
            x = s[0]
            y = s[1]
            if not in_ambient:
                newsample = (x, y, 1)
            else:
                if o.optimisation.use_opencamlib and o.optimisation.use_exact:
                    z = s[2]
                    if minz > z:
                        z = minz
                    newsample = (x, y, z)
                # ampling
                elif o.optimisation.use_exact and not o.optimisation.use_opencamlib:

                    if lastsample is not None:  # this is an optimalization,
                        # search only for near depths to the last sample. Saves about 30% of sampling time.
                        z = getSampleBullet(cutter, x, y, cutterdepth, 1,
                                            lastsample[2] - o.dist_along_paths)  # first try to the last sample
                        if z < minz - 1:
                            z = getSampleBullet(cutter, x, y, cutterdepth,
                                                lastsample[2] - o.dist_along_paths, minz)
                    else:
                        z = getSampleBullet(cutter, x, y, cutterdepth, 1, minz)

                # print(z)
                else:
                    timingstart(samplingtime)
                    xs = (x - minx) / pixsize + coordoffset
                    ys = (y - miny) / pixsize + coordoffset
                    timingadd(samplingtime)
                    z = getSampleImage((xs, ys), o.offset_image, minz) + o.skin

                ################################
                # handling samples
                ############################################

                if minz > z:
                    z = minz
                newsample = (x, y, z)

            for i, l in enumerate(layers):
                terminatechunk = False

                ch = layeractivechunks[i]

                if l[1] <= newsample[2] <= l[0]:
                    lastlayer = None  # rather the last sample here ? has to be set to None,
                    # since sometimes lastsample vs lastlayer didn't fit and did ugly ugly stuff....
                    if lastsample is not None:
                        for i2, l2 in enumerate(layers):
                            if l2[1] <= lastsample[2] <= l2[0]:
                                lastlayer = i2

                    currentlayer = i
                    # and lastsample[2]!=newsample[2]:
                    if lastlayer is not None and lastlayer != currentlayer:
                        # #sampling for sorted paths in layers- to go to the border of the sampled layer at least...
                        # there was a bug here, but should be fixed.
                        if currentlayer < lastlayer:
                            growing = True
                            r = range(currentlayer, lastlayer)
                            spliti = 1
                        else:
                            r = range(lastlayer, currentlayer)
                            growing = False
                            spliti = 0
                        # print(r)
                        li = 0
                        for ls in r:
                            splitz = layers[ls][1]
                            # print(ls)

                            v1 = lastsample
                            v2 = newsample
                            if o.movement.protect_vertical:
                                v1, v2 = isVerticalLimit(v1, v2, o.movement.protect_vertical_limit)
                            v1 = Vector(v1)
                            v2 = Vector(v2)
                            # print(v1,v2)
                            ratio = (splitz - v1.z) / (v2.z - v1.z)
                            # print(ratio)
                            betweensample = v1 + (v2 - v1) * ratio

                            # ch.points.append(betweensample.to_tuple())

                            if growing:
                                if li > 0:
                                    layeractivechunks[ls].points.insert(-1,
                                                                        betweensample.to_tuple())
                                else:
                                    layeractivechunks[ls].points.append(betweensample.to_tuple())
                                layeractivechunks[ls + 1].points.append(betweensample.to_tuple())
                            else:
                                # print(v1,v2,betweensample,lastlayer,currentlayer)
                                layeractivechunks[ls].points.insert(-1, betweensample.to_tuple())
                                layeractivechunks[ls + 1].points.insert(0, betweensample.to_tuple())

                            li += 1
                    # this chunk is terminated, and allready in layerchunks /

                    # ch.points.append(betweensample.to_tuple())#
                    ch.points.append(newsample)
                elif l[1] > newsample[2]:
                    ch.points.append((newsample[0], newsample[1], l[1]))
                elif l[0] < newsample[2]:  # terminate chunk
                    terminatechunk = True

                if terminatechunk:
                    if len(ch.points) > 0:
                        as_chunk = ch.to_chunk()
                        layerchunks[i].append(as_chunk)
                        thisrunchunks[i].append(as_chunk)
                        layeractivechunks[i] = camPathChunkBuilder([])
            lastsample = newsample

        for i, l in enumerate(layers):
            ch = layeractivechunks[i]
            if len(ch.points) > 0:
                as_chunk = ch.to_chunk()
                layerchunks[i].append(as_chunk)
                thisrunchunks[i].append(as_chunk)
                layeractivechunks[i] = camPathChunkBuilder([])

            # PARENTING
            if o.strategy == 'PARALLEL' or o.strategy == 'CROSS' or o.strategy == 'OUTLINEFILL':
                timingstart(sortingtime)
                parentChildDist(thisrunchunks[i], lastrunchunks[i], o)
                timingadd(sortingtime)

        lastrunchunks = thisrunchunks

    # print(len(layerchunks[i]))
    progress('Checking Relations Between Paths')
    timingstart(sortingtime)

    if o.strategy == 'PARALLEL' or o.strategy == 'CROSS' or o.strategy == 'OUTLINEFILL':
        if len(layers) > 1:  # sorting help so that upper layers go first always
            for i in range(0, len(layers) - 1):
                parents = []
                children = []
                # only pick chunks that should have connectivity assigned - 'last' and 'first' ones of the layer.
                for ch in layerchunks[i + 1]:
                    if not ch.children:
                        parents.append(ch)
                for ch1 in layerchunks[i]:
                    if not ch1.parents:
                        children.append(ch1)

                # parent only last and first chunk, before it did this for all.
                parentChild(parents, children, o)
    timingadd(sortingtime)
    chunks = []

    for i, l in enumerate(layers):
        if o.movement.ramp:
            for ch in layerchunks[i]:
                ch.zstart = layers[i][0]
                ch.zend = layers[i][1]
        chunks.extend(layerchunks[i])
    timingadd(totaltime)
    print(samplingtime)
    print(sortingtime)
    print(totaltime)
    return chunks


async def sampleChunksNAxis(o, pathSamples, layers):
    """Sample chunks along a specified axis based on provided paths and layers.

    This function processes a set of path samples and organizes them into
    chunks according to specified layers. It prepares the collision world if
    necessary and samples paths while considering the cutter's rotation and
    position. The function also handles the relationships between the
    sampled paths and organizes them into layers for further processing.

    Args:
        o (Object): An object containing properties such as min/max coordinates,
            cutter shape, and collision tags.
        pathSamples (list): A list of path samples, each containing start points,
            end points, and rotations.
        layers (list): A list of tuples defining the layers with their respective
            distance ranges.

    Returns:
        list: A list of chunks sampled from the path samples organized by layers.
    """

    #
    minx, miny, minz, maxx, maxy, maxz = o.min.x, o.min.y, o.min.z, o.max.x, o.max.y, o.max.z

    # prepare collision world
    if o.update_bullet_collision_tag:
        prepareBulletCollision(o)
        # print('getting ambient')
        getAmbient(o)
        o.update_bullet_collision_tag = False
    # print (o.ambient)
    cutter = o.cutter_shape
    cutterdepth = cutter.dimensions.z / 2

    t = time.time()
    print('Sampling Paths')

    totlen = 0  # total length of all chunks, to estimate sampling time.
    for chs in pathSamples:
        totlen += len(chs.startpoints)
    layerchunks = []
    minz = o.minz
    layeractivechunks = []
    lastrunchunks = []

    for l in layers:
        layerchunks.append([])
        layeractivechunks.append(camPathChunkBuilder([]))
        lastrunchunks.append([])
    n = 0

    last_percent = -1
    lastz = minz
    for patternchunk in pathSamples:
        # print (patternchunk.endpoints)
        thisrunchunks = []
        for l in layers:
            thisrunchunks.append([])
        lastlayer = None
        currentlayer = None
        lastsample = None
        # threads_count=4
        lastrotation = (0, 0, 0)
        # for t in range(0,threads):
        # print(len(patternchunk.startpoints),len( patternchunk.endpoints))
        spl = len(patternchunk.startpoints)
        # ,startp in enumerate(patternchunk.startpoints):
        for si in range(0, spl):
            # #TODO: seems we are writing into the source chunk ,
            #  and that is why we need to write endpoints everywhere too?

            percent = int(100 * n / totlen)
            if percent != last_percent:
                await progress_async('sampling paths', percent)
                last_percent = percent
            n += 1
            sampled = False
            # print(si)

            # get the vector to sample
            startp = Vector(patternchunk.startpoints[si])
            endp = Vector(patternchunk.endpoints[si])
            rotation = patternchunk.rotations[si]
            sweepvect = endp - startp
            sweepvect.normalize()
            # sampling
            if rotation != lastrotation:

                cutter.rotation_euler = rotation
                # cutter.rotation_euler.x=-cutter.rotation_euler.x
                # print(rotation)

                if o.cutter_type == 'VCARVE':  # Bullet cone is always pointing Up Z in the object
                    cutter.rotation_euler.x += pi
                cutter.update_tag()
                # this has to be :( it resets the rigidbody world.
                bpy.context.scene.frame_set(1)
                # No other way to update it probably now :(
                # actually 2 frame jumps are needed.
                bpy.context.scene.frame_set(2)
                bpy.context.scene.frame_set(0)

            newsample = getSampleBulletNAxis(cutter, startp, endp, rotation, cutterdepth)

            # print('totok',startp,endp,rotation,newsample)
            ################################
            # handling samples
            ############################################
            # this is weird, but will leave it this way now.. just prototyping here.
            if newsample is not None:
                sampled = True
            else:  # TODO: why was this here?
                newsample = startp
                sampled = True
            # print(newsample)

            # elif o.ambient_behaviour=='ALL' and not o.inverse:#handle ambient here
            # newsample=(x,y,minz)
            if sampled:
                for i, l in enumerate(layers):
                    terminatechunk = False
                    ch = layeractivechunks[i]

                    # print(i,l)
                    # print(l[1],l[0])
                    v = startp - newsample
                    distance = -v.length

                    if l[1] <= distance <= l[0]:
                        lastlayer = currentlayer
                        currentlayer = i

                        if lastsample is not None and lastlayer is not None and currentlayer is not None \
                                and lastlayer != currentlayer:  # sampling for sorted paths in layers-
                            # to go to the border of the sampled layer at least...
                            # there was a bug here, but should be fixed.
                            if currentlayer < lastlayer:
                                growing = True
                                r = range(currentlayer, lastlayer)
                                spliti = 1
                            else:
                                r = range(lastlayer, currentlayer)
                                growing = False
                                spliti = 0
                            # print(r)
                            li = 0

                            for ls in r:
                                splitdistance = layers[ls][1]

                                ratio = (splitdistance - lastdistance) / (distance - lastdistance)
                                # print(ratio)
                                betweensample = lastsample + (newsample - lastsample) * ratio
                                # this probably doesn't work at all!!!! check this algoritm>
                                betweenrotation = tuple_add(lastrotation,
                                                            tuple_mul(tuple_sub(rotation, lastrotation), ratio))
                                # startpoint = retract point, it has to be always available...
                                betweenstartpoint = laststartpoint + \
                                    (startp - laststartpoint) * ratio
                                # here, we need to have also possible endpoints always..
                                betweenendpoint = lastendpoint + (endp - lastendpoint) * ratio
                                if growing:
                                    if li > 0:
                                        layeractivechunks[ls].points.insert(-1, betweensample)
                                        layeractivechunks[ls].rotations.insert(-1, betweenrotation)
                                        layeractivechunks[ls].startpoints.insert(
                                            -1, betweenstartpoint)
                                        layeractivechunks[ls].endpoints.insert(-1, betweenendpoint)
                                    else:
                                        layeractivechunks[ls].points.append(betweensample)
                                        layeractivechunks[ls].rotations.append(betweenrotation)
                                        layeractivechunks[ls].startpoints.append(betweenstartpoint)
                                        layeractivechunks[ls].endpoints.append(betweenendpoint)
                                    layeractivechunks[ls + 1].points.append(betweensample)
                                    layeractivechunks[ls + 1].rotations.append(betweenrotation)
                                    layeractivechunks[ls + 1].startpoints.append(betweenstartpoint)
                                    layeractivechunks[ls + 1].endpoints.append(betweenendpoint)
                                else:

                                    layeractivechunks[ls].points.insert(-1, betweensample)
                                    layeractivechunks[ls].rotations.insert(-1, betweenrotation)
                                    layeractivechunks[ls].startpoints.insert(-1, betweenstartpoint)
                                    layeractivechunks[ls].endpoints.insert(-1, betweenendpoint)

                                    layeractivechunks[ls + 1].points.append(betweensample)
                                    layeractivechunks[ls + 1].rotations.append(betweenrotation)
                                    layeractivechunks[ls + 1].startpoints.append(betweenstartpoint)
                                    layeractivechunks[ls + 1].endpoints.append(betweenendpoint)

                                # layeractivechunks[ls+1].points.insert(0,betweensample)
                                li += 1
                        # this chunk is terminated, and allready in layerchunks /

                        # ch.points.append(betweensample)#
                        ch.points.append(newsample)
                        ch.rotations.append(rotation)
                        ch.startpoints.append(startp)
                        ch.endpoints.append(endp)
                        lastdistance = distance

                    elif l[1] > distance:
                        v = sweepvect * l[1]
                        p = startp - v
                        ch.points.append(p)
                        ch.rotations.append(rotation)
                        ch.startpoints.append(startp)
                        ch.endpoints.append(endp)
                    elif l[0] < distance:  # retract to original track
                        ch.points.append(startp)
                        ch.rotations.append(rotation)
                        ch.startpoints.append(startp)
                        ch.endpoints.append(endp)

            lastsample = newsample
            lastrotation = rotation
            laststartpoint = startp
            lastendpoint = endp

        # convert everything to actual chunks
        # rather than chunkBuilders
        for i, l in enumerate(layers):
            layeractivechunks[i] = layeractivechunks[i].to_chunk(
            ) if layeractivechunks[i] is not None else None

        for i, l in enumerate(layers):
            ch = layeractivechunks[i]
            if ch.count() > 0:
                layerchunks[i].append(ch)
                thisrunchunks[i].append(ch)
                layeractivechunks[i] = camPathChunkBuilder([])

            if o.strategy == 'PARALLEL' or o.strategy == 'CROSS' or o.strategy == 'OUTLINEFILL':
                parentChildDist(thisrunchunks[i], lastrunchunks[i], o)

        lastrunchunks = thisrunchunks

    # print(len(layerchunks[i]))

    progress('Checking Relations Between Paths')
    """#this algorithm should also work for n-axis, but now is "sleeping"
    if (o.strategy=='PARALLEL' or o.strategy=='CROSS'):
        if len(layers)>1:# sorting help so that upper layers go first always
            for i in range(0,len(layers)-1):
                #print('layerstuff parenting')
                parentChild(layerchunks[i+1],layerchunks[i],o)
    """
    chunks = []
    for i, l in enumerate(layers):
        chunks.extend(layerchunks[i])

    return chunks


def extendChunks5axis(chunks, o):
    """Extend chunks with start and end points based on object orientation.

    This function modifies a list of chunks by calculating start and end
    points for each chunk based on the provided object's orientation and
    position. It retrieves the necessary parameters from the Blender context
    and the object, determining the starting and ending positions for the
    cutter based on the object's movement properties. The calculated points
    are then appended to the respective chunk's startpoints and endpoints
    lists. Additionally, it captures rotation information, although the
    current implementation may not yield meaningful results.

    Args:
        chunks (list): A list of chunk objects to be modified.
        o (object): An object containing movement properties and orientation
            information.
    """

    s = bpy.context.scene
    m = s.cam_machine
    s = bpy.context.scene
    free_height = o.movement.free_height  # o.max.z +
    if m.use_position_definitions:  # dhull
        cutterstart = Vector((m.starting_position.x, m.starting_position.y,
                              max(o.max.z, m.starting_position.z)))  # start point for casting
    else:
        # start point for casting
        cutterstart = Vector((0, 0, max(o.max.z, free_height)))
    cutterend = Vector((0, 0, o.min.z))
    oriname = o.name + ' orientation'
    ori = s.objects[oriname]
    # rotationaxes = rotTo2axes(ori.rotation_euler,'CA')#warning-here it allready is reset to 0!!
    print('rot', o.rotationaxes)
    a, b = o.rotationaxes  # this is all nonsense by now.
    for chunk in chunks:
        for v in chunk.points:
            cutterstart.x = v[0]
            cutterstart.y = v[1]
            cutterend.x = v[0]
            cutterend.y = v[1]
            chunk.startpoints.append(cutterstart.to_tuple())
            chunk.endpoints.append(cutterend.to_tuple())
            chunk.rotations.append(
                (a, b, 0))  # TODO: this is a placeholder. It does 99.9% probably write total nonsense.


def curveToShapely(cob, use_modifiers=False):
    """Convert a curve object to Shapely polygons.

    This function takes a curve object and converts it into a list of
    Shapely polygons. It first breaks the curve into chunks and then
    transforms those chunks into Shapely-compatible polygon representations.
    The optional `use_modifiers` parameter allows for additional processing
    of the curve before conversion.

    Args:
        cob: The curve object to be converted.
        use_modifiers (bool): A flag indicating whether to apply modifiers
            during the conversion process. Defaults to False.

    Returns:
        list: A list of Shapely polygons derived from the input curve.
    """

    chunks = curveToChunks(cob, use_modifiers)
    polys = chunksToShapely(chunks)
    return polys


# separate function in blender, so you can offset any curve.
# FIXME: same algorithms as the cutout strategy, because that is hierarchy-respecting.

def silhoueteOffset(context, offset, style=1, mitrelimit=1.0):
    """Offset the silhouette of a curve or font object in Blender.

    This function takes an active curve or font object and generates an
    offset silhouette based on the specified parameters. It first converts
    the object to a shapely representation and then applies a buffer
    operation to create the offset. The resulting geometry is then converted
    back to a curve in Blender with a new name that reflects the offset
    value.

    Args:
        context (Context): The Blender context in which the operation is performed.
        offset (float): The distance by which to offset the silhouette.
        style (int?): The style of the join for the offset. Defaults to 1.
        mitrelimit (float?): The limit for the miter join. Defaults to 1.0.

    Returns:
        dict: A dictionary indicating the operation has finished with the key
            'FINISHED'.
    """

    bpy.context.scene.cursor.location = (0, 0, 0)
    ob = bpy.context.active_object
    if ob.type == 'CURVE' or ob.type == 'FONT':
        silhs = curveToShapely(ob)
    else:
        silhs = getObjectSilhouete('OBJECTS', [ob])

    polys = []
    mp = shapely.ops.unary_union(silhs)
    print("offset attributes:")
    print(offset, style)
    mp = mp.buffer(offset, cap_style=1, join_style=style, resolution=16, mitre_limit=mitrelimit)
    shapelyToCurve(ob.name + '_offset_' + str(round(offset, 5)), mp, ob.location.z)

    return {'FINISHED'}


def polygonBoolean(context, boolean_type):
    """Perform a boolean operation on selected polygons.

    This function takes the active object and performs a specified boolean
    operation (union, difference, or intersection) with all other selected
    objects in the Blender context. It converts the curves of the objects to
    Shapely geometries, applies the boolean operation, and then converts the
    result back to a curve in Blender.

    Args:
        context: The Blender context in which the operation is performed.
        boolean_type (str): The type of boolean operation to perform.
            Must be one of 'UNION', 'DIFFERENCE', or 'INTERSECT'.

    Returns:
        dict: A dictionary indicating the operation result, typically
            {'FINISHED'}.
    """

    bpy.context.scene.cursor.location = (0, 0, 0)
    ob = bpy.context.active_object
    obs = []
    for ob1 in bpy.context.selected_objects:
        if ob1 != ob:
            obs.append(ob1)
    plist = curveToShapely(ob)
    p1 = MultiPolygon(plist)
    polys = []
    for o in obs:
        plist = curveToShapely(o)
        p2 = MultiPolygon(plist)
        polys.append(p2)
    # print(polys)
    if boolean_type == 'UNION':
        for p2 in polys:
            p1 = p1.union(p2)
    elif boolean_type == 'DIFFERENCE':
        for p2 in polys:
            p1 = p1.difference(p2)
    elif boolean_type == 'INTERSECT':
        for p2 in polys:
            p1 = p1.intersection(p2)

    shapelyToCurve('boolean', p1, ob.location.z)
    # bpy.ops.object.convert(target='CURVE')
    # bpy.context.scene.cursor_location=ob.location
    # bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    return {'FINISHED'}


def polygonConvexHull(context):
    """Generate the convex hull of a set of vertices in a 3D space.

    This function duplicates the current object, joins its components, and
    converts it to a mesh. It then extracts the X and Y coordinates from the
    vertices of the mesh and uses these coordinates to create a convex hull
    using the Shapely library. The resulting convex hull is then converted
    back into a curve object in Blender.

    Args:
        context: The Blender context in which the operation is performed.

    Returns:
        dict: A dictionary indicating that the operation has been completed
        successfully with the key 'FINISHED'.
    """

    coords = []

    bpy.ops.object.duplicate()
    bpy.ops.object.join()
    bpy.context.object.data.dimensions = '3D'  # force curve to be a 3D curve
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.active_object.name = "_tmp"

    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.view_layer.objects.active

    for v in obj.data.vertices:  # extract X,Y coordinates from the vertices data
        c = (v.co.x, v.co.y)
        coords.append(c)

    select_multiple('_tmp')  # delete temporary mesh
    select_multiple('ConvexHull')  # delete old hull

    # convert coordinates to shapely MultiPoint datastructure
    points = sgeometry.MultiPoint(coords)

    hull = points.convex_hull
    shapelyToCurve('ConvexHull', hull, 0.0)

    return {'FINISHED'}


def Helix(r, np, zstart, pend, rev):
    """Generate a helix path in 3D space.

    This function calculates a series of points that form a helix based on
    the given parameters. It starts from a specified point and spirals
    downwards in the z-direction, while rotating around the z-axis. The
    function utilizes a vector and an Euler rotation to compute the
    coordinates of each point in the helix.

    Args:
        r (float): The radius of the helix.
        np (int): The number of points per revolution.
        zstart (float): The starting z-coordinate of the helix.
        pend (tuple): A tuple containing the x, y, and z coordinates of the endpoint.
        rev (int): The number of revolutions the helix makes.

    Returns:
        list: A list of tuples representing the coordinates of the points along the
            helix.
    """

    c = []
    v = Vector((r, 0, zstart))
    e = Euler((0, 0, 2.0 * pi / np))
    zstep = (zstart - pend[2]) / (np * rev)
    for a in range(0, int(np * rev)):
        c.append((v.x + pend[0], v.y + pend[1], zstart - (a * zstep)))
        v.rotate(e)
    c.append((v.x + pend[0], v.y + pend[1], pend[2]))

    return c


def comparezlevel(x):
    return x[5]


def overlaps(bb1, bb2):
    """Determine if one bounding box is a child of another.

    This function checks if the first bounding box (bb1) is completely
    enclosed within the second bounding box (bb2). It does this by comparing
    the coordinates of both bounding boxes to see if the boundaries of bb1
    fall within the boundaries of bb2.

    Args:
        bb1 (tuple): A tuple representing the coordinates of the first
            bounding box in the format (x_min, y_min, x_max, y_max).
        bb2 (tuple): A tuple representing the coordinates of the second
            bounding box in the same format.

    Returns:
        bool: True if bb1 is a child of bb2, otherwise False.
    """
  # true if bb1 is child of bb2
    ch1 = bb1
    ch2 = bb2
    if (ch2[1] > ch1[1] > ch1[0] > ch2[0] and ch2[3] > ch1[3] > ch1[2] > ch2[2]):
        return True


async def connectChunksLow(chunks, o):
    """Connects chunks that are close to each other without lifting, sampling
    them 'low'.

    This function processes a list of chunks and connects them based on
    their proximity, allowing for efficient path generation in various
    strategies. It considers several parameters such as movement settings
    and strategy types to determine the distance threshold for merging
    chunks. The function also handles resampling of paths when necessary,
    ensuring that the resulting connected chunks are optimized for the given
    operation.

    Args:
        chunks (list): A list of chunk objects to be connected.
        o (object): An object containing movement and strategy parameters.

    Returns:
        list: A list of connected chunk objects.
    """
    if not o.movement.stay_low or (o.strategy == 'CARVE' and o.carve_depth > 0):
        return chunks

    connectedchunks = []
    chunks_to_resample = []  # for OpenCAMLib sampling
    mergedist = 3 * o.dist_between_paths
    if o.strategy == 'PENCIL':  # this is bigger for pencil path since it goes on the surface to clean up the rests,
        # and can go to close points on the surface without fear of going deep into material.
        mergedist = 10 * o.dist_between_paths

    if o.strategy == 'MEDIAL_AXIS':
        mergedist = 1 * o.medial_axis_subdivision

    if o.movement.parallel_step_back:
        mergedist *= 2

    if o.movement.merge_dist > 0:
        mergedist = o.movement.merge_dist
    # mergedist=10
    lastch = None
    i = len(chunks)
    pos = (0, 0, 0)

    for ch in chunks:
        if ch.count() > 0:
            if lastch is not None and (ch.distStart(pos, o) < mergedist):
                # CARVE should lift allways, when it goes below surface...
                # print(mergedist,ch.dist(pos,o))
                if o.strategy == 'PARALLEL' or o.strategy == 'CROSS' or o.strategy == 'PENCIL':
                    # for these paths sorting happens after sampling, thats why they need resample the connection
                    between = samplePathLow(o, lastch, ch, True)
                else:
                    # print('addbetwee')
                    between = samplePathLow(o, lastch, ch,
                                            False)  # other paths either dont use sampling or are sorted before it.
                if o.optimisation.use_opencamlib and o.optimisation.use_exact and (
                        o.strategy == 'PARALLEL' or o.strategy == 'CROSS' or o.strategy == 'PENCIL'):
                    chunks_to_resample.append(
                        (connectedchunks[-1], connectedchunks[-1].count(), between.count()))

                connectedchunks[-1].extend(between.get_points_np())
                connectedchunks[-1].extend(ch.get_points_np())
            else:
                connectedchunks.append(ch)
            lastch = ch
            pos = lastch.get_point(-1)

    if o.optimisation.use_opencamlib and o.optimisation.use_exact and o.strategy != 'CUTOUT' and o.strategy != 'POCKET' and o.strategy != 'WATERLINE':
        await oclResampleChunks(o, chunks_to_resample, use_cached_mesh=True)

    return connectedchunks


def getClosest(o, pos, chunks):
    """Find the closest chunk to a given position.

    This function iterates through a list of chunks and determines which
    chunk is closest to a specified position. It checks if each chunk's
    children are sorted before calculating the distance. The chunk with the
    minimum distance to the position is returned.

    Args:
        o: An object representing a reference point.
        pos: A position to which the closest chunk is determined.
        chunks (list): A list of chunk objects to evaluate.

    Returns:
        Chunk: The closest chunk object to the specified position, or None if no valid
            chunk is found.
    """

    # ch=-1
    mind = 2000
    d = 100000000000
    ch = None
    for chtest in chunks:
        cango = True
        # here was chtest.getNext==chtest, was doing recursion error and slowing down.
        for child in chtest.children:
            if not child.sorted:
                cango = False
                break
        if cango:
            d = chtest.dist(pos, o)
            if d < mind:
                ch = chtest
                mind = d
    return ch


async def sortChunks(chunks, o, last_pos=None):
    """Sort a list of chunks based on a specified strategy.

    This function sorts a list of chunks according to the provided options
    and the current state of the chunks. It utilizes a recursive approach to
    find the closest chunk to the current position and adapts its distance
    based on the specified options. The function also handles progress
    updates asynchronously if the strategy is not 'WATERLINE'. The recursion
    limit is temporarily increased to accommodate deep recursive calls that
    may occur during sorting.

    Args:
        chunks (list): A list of chunk objects to be sorted.
        o (object): An options object containing sorting strategy and other parameters.
        last_pos (tuple?): The last known position as a tuple of coordinates.
            Defaults to None.

    Returns:
        list: A sorted list of chunk objects.
    """

    if o.strategy != 'WATERLINE':
        await progress_async('sorting paths')
    # the getNext() function of CamPathChunk was running out of recursion limits.
    sys.setrecursionlimit(100000)
    sortedchunks = []
    chunks_to_resample = []

    lastch = None
    last_progress_time = time.time()
    total = len(chunks)
    i = len(chunks)
    pos = (0, 0, 0) if last_pos is None else last_pos
    while len(chunks) > 0:
        if o.strategy != 'WATERLINE' and time.time()-last_progress_time > 0.1:
            await progress_async("Sorting paths", 100.0*(total-len(chunks))/total)
            last_progress_time = time.time()
        ch = None
        if len(sortedchunks) == 0 or len(
                lastch.parents) == 0:  # first chunk or when there are no parents -> parents come after children here...
            ch = getClosest(o, pos, chunks)
        elif len(lastch.parents) > 0:  # looks in parents for next candidate, recursively
            for parent in lastch.parents:
                ch = parent.getNextClosest(o, pos)
                if ch is not None:
                    break
            if ch is None:
                ch = getClosest(o, pos, chunks)

        if ch is not None:  # found next chunk, append it to list
            # only adaptdist the chunk if it has not been sorted before
            if not ch.sorted:
                ch.adaptdist(pos, o)
                ch.sorted = True
            # print(len(ch.parents),'children')
            chunks.remove(ch)
            sortedchunks.append(ch)
            lastch = ch
            pos = lastch.get_point(-1)
        # print(i, len(chunks))
        # experimental fix for infinite loop problem
        # else:
        # THIS PROBLEM WASN'T HERE AT ALL. but keeping it here, it might fix the problems somwhere else:)
        # can't find chunks close enough and still some chunks left
        # to be sorted. For now just move the remaining chunks over to
        # the sorted list.
        # This fixes an infinite loop condition that occurs sometimes.
        # This is a bandaid fix: need to find the root cause of this problem
        # suspect it has to do with the sorted flag?
        # print("no chunks found closest. Chunks not sorted: ", len(chunks))
        # sortedchunks.extend(chunks)
        # chunks[:] = []

        i -= 1
    if o.strategy == 'POCKET' and o.pocket_option == 'OUTSIDE':
        sortedchunks.reverse()

    sys.setrecursionlimit(1000)
    if o.strategy != 'DRILL' and o.strategy != 'OUTLINEFILL':
        # THIS SHOULD AVOID ACTUALLY MOST STRATEGIES, THIS SHOULD BE DONE MANUALLY,
        # BECAUSE SOME STRATEGIES GET SORTED TWICE.
        sortedchunks = await connectChunksLow(sortedchunks, o)
    return sortedchunks


# most right vector from a set regarding angle..
def getVectorRight(lastv, verts):
    """Get the index of the vector that is most to the right based on angle.

    This function calculates the angle between a specified vector (defined
    by the last two points in `lastv`) and each vector in the `verts` list.
    It identifies the vector that has the smallest angle with respect to the
    specified direction, which is considered to be the "most right" vector.
    The function returns the index of this vector in the `verts` list.

    Args:
        lastv (list): A list containing two vectors, where each vector is
            represented as a tuple or list of coordinates.
        verts (list): A list of vectors, where each vector is represented as
            a tuple or list of coordinates.

    Returns:
        int: The index of the vector in `verts` that is most to the right
            with respect to the angle calculated.
    """

    defa = 100
    v1 = Vector(lastv[0])
    v2 = Vector(lastv[1])
    va = v2 - v1
    for i, v in enumerate(verts):
        if v != lastv[0]:
            vb = Vector(v) - v2
            a = va.angle_signed(Vector(vb))

            if a < defa:
                defa = a
                returnvec = i
    return returnvec


def cleanUpDict(ndict):
    """Remove lonely points from a dictionary.

    This function iterates over the keys of the provided dictionary and
    removes entries that are considered "lonely," meaning they have one or
    fewer associated values. It continues to check for and remove any
    entries that become lonely as a result of other removals.

    Args:
        ndict (dict): A dictionary where keys are associated with lists of values.

    Returns:
        None: This function modifies the input dictionary in place and does not return
            a value.
    """

    # now it should delete all junk first, iterate over lonely verts.
    print('Removing Lonely Points')
    # found_solitaires=True
    # while found_solitaires:
    found_solitaires = False
    keys = []
    keys.extend(ndict.keys())
    removed = 0
    for k in keys:
        print(k)
        print(ndict[k])
        if len(ndict[k]) <= 1:
            newcheck = [k]
            while (len(newcheck) > 0):
                v = newcheck.pop()
                if len(ndict[v]) <= 1:
                    for v1 in ndict[v]:
                        newcheck.append(v)
                    dictRemove(ndict, v)
            removed += 1
            found_solitaires = True
    print(removed)


def dictRemove(dict, val):
    """Remove a key and its associated values from a dictionary.

    This function takes a dictionary and a key (val) as input. It removes
    the specified key from the dictionary and also removes the key from the
    lists of all other keys that reference it. This is useful for
    maintaining referential integrity in a dictionary of lists.

    Args:
        dict (dict): A dictionary where each key maps to a list of values.
        val: The key to be removed from the dictionary and from the lists of other
            keys.
    """

    for v in dict[val]:
        dict[v].remove(val)
    dict.pop(val)


def addLoop(parentloop, start, end):
    """Add a loop to a parent loop structure.

    This function iterates through the child loops of a given parent loop to
    determine if the new loop defined by the start and end parameters can be
    added. If the new loop's range is completely within an existing child
    loop's range, it recursively calls itself to check that child loop. If
    no such child loop exists, it appends the new loop to the parent loop's
    list of child loops.

    Args:
        parentloop (list): A list representing the parent loop, where the third element
            contains child loops.
        start (int): The starting point of the new loop.
        end (int): The ending point of the new loop.
    """

    added = False
    for l in parentloop[2]:
        if l[0] < start and l[1] > end:
            addLoop(l, start, end)
            return
    parentloop[2].append([start, end, []])


def cutloops(csource, parentloop, loops):
    """Cut loops from a source code segment.

    This function takes a source code segment and a parent loop defined by
    its start and end indices, along with a list of nested loops. It
    extracts the code within the parent loop, removes the code segments
    defined by the nested loops, and appends the modified code to the
    provided list of loops. The function also recursively processes any
    nested loops found within the parent loop.

    Args:
        csource (str): The source code from which loops will be cut.
        parentloop (tuple): A tuple containing the start index, end index, and a list of nested
            loops.
            The nested loops are represented as tuples of their own start and end
            indices.
        loops (list): A list that will be populated with the modified code segments after
            cutting loops.

    Returns:
        None: This function modifies the `loops` list in place and does not return a
            value.
    """

    copy = csource[parentloop[0]:parentloop[1]]

    for li in range(len(parentloop[2]) - 1, -1, -1):
        l = parentloop[2][li]
        # print(l)
        copy = copy[:l[0] - parentloop[0]] + copy[l[1] - parentloop[0]:]
    loops.append(copy)
    for l in parentloop[2]:
        cutloops(csource, l, loops)


def getOperationSilhouete(operation):
    """Gets the silhouette for the operation.

    This function computes the silhouette of a given operation using image
    thresholding techniques. It distinguishes between different geometry
    sources such as 'OBJECT', 'COLLECTION', and 'IMAGE'. For operations
    involving objects, it counts the total number of faces and decides
    whether to use an image-based method or an object-based method for
    silhouette extraction. If the total number of faces exceeds a certain
    threshold, it opts for the image method; otherwise, it retrieves the
    silhouette directly from the objects.

    Args:
        operation (Operation): An object containing details about the operation, including
            geometry source, objects, and parameters for silhouette
            computation.

    Returns:
        Silhouette: The computed silhouette of the operation.
    """
    if operation.update_silhouete_tag:
        image = None
        objects = None
        if operation.geometry_source == 'OBJECT' or operation.geometry_source == 'COLLECTION':
            if not operation.onlycurves:
                stype = 'OBJECTS'
            else:
                stype = 'CURVES'
        else:
            stype = 'IMAGE'

        totfaces = 0
        if stype == 'OBJECTS':
            for ob in operation.objects:
                if ob.type == 'MESH':
                    totfaces += len(ob.data.polygons)

        if (stype == 'OBJECTS' and totfaces > 200000) or stype == 'IMAGE':
            print('Image Method')
            samples = renderSampleImage(operation)
            if stype == 'OBJECTS':
                i = samples > operation.minz - 0.0000001
                # numpy.min(operation.zbuffer_image)-0.0000001#
                # #the small number solves issue with totally flat meshes, which people tend to mill instead of
                # proper pockets. then the minimum was also maximum, and it didn't detect contour.
            else:
                # this fixes another numeric imprecision.
                i = samples > numpy.min(operation.zbuffer_image)

            chunks = imageToChunks(operation, i)
            operation.silhouete = chunksToShapely(chunks)
        # print(operation.silhouete)
        # this conversion happens because we need the silh to be oriented, for milling directions.
        else:
            print('object method for retrieving silhouette')  #
            operation.silhouete = getObjectSilhouete(stype, objects=operation.objects,
                                                     use_modifiers=operation.use_modifiers)

        operation.update_silhouete_tag = False
    return operation.silhouete


def getObjectSilhouete(stype, objects=None, use_modifiers=False):
    """Get the silhouette of objects based on the specified type.

    This function computes the silhouette of a given set of objects in
    either 'CURVES' or 'OBJECTS' format. For 'CURVES', it converts curves to
    polygon format and aggregates them. For 'OBJECTS', it calculates the
    silhouette based on the polygons of the objects, taking into account the
    number of faces and whether to use modifiers. The function handles large
    numbers of polygons efficiently by processing them in parts if
    necessary.

    Args:
        stype (str): The type of silhouette to compute ('CURVES' or 'OBJECTS').
        objects (list?): A list of objects to process. Defaults to None.
        use_modifiers (bool?): Whether to apply modifiers to the objects.
            Defaults to False.

    Returns:
        shapely.geometry.MultiPolygon: The computed silhouette as a MultiPolygon.
    """

    # o=operation
    if stype == 'CURVES':  # curve conversion to polygon format
        allchunks = []
        for ob in objects:
            chunks = curveToChunks(ob)
            allchunks.extend(chunks)
        silhouete = chunksToShapely(allchunks)

    elif stype == 'OBJECTS':
        totfaces = 0
        for ob in objects:
            totfaces += len(ob.data.polygons)

        if totfaces < 20000000:  # boolean polygons method originaly was 20 000 poly limit, now limitless,
            # it might become teribly slow, but who cares?
            t = time.time()
            print('Shapely Getting Silhouette')
            polys = []
            for ob in objects:
                if use_modifiers:
                    ob = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
                    m = ob.to_mesh()
                else:
                    m = ob.data
                mw = ob.matrix_world
                mwi = mw.inverted()
                r = ob.rotation_euler
                m.calc_loop_triangles()
                id = 0
                e = 0.000001
                scaleup = 100
                for tri in m.loop_triangles:
                    n = tri.normal.copy()
                    n.rotate(r)

                    if tri.area > 0 and n.z != 0:  # n.z>0.0 and f.area>0.0 :
                        s = []
                        c = mw @ tri.center
                        c = c.xy
                        for vert_index in tri.vertices:
                            v = mw @ m.vertices[vert_index].co
                            s.append((v.x, v.y))
                        if len(s) > 2:
                            # print(s)
                            p = spolygon.Polygon(s)
                            # print(dir(p))
                            if p.is_valid:
                                # polys.append(p)
                                polys.append(p.buffer(e, resolution=0))
                        id += 1

            if totfaces < 20000:
                p = sops.unary_union(polys)
            else:
                print('Computing in Parts')
                bigshapes = []
                i = 1
                part = 20000
                while i * part < totfaces:
                    print(i)
                    ar = polys[(i - 1) * part:i * part]
                    bigshapes.append(sops.unary_union(ar))
                    i += 1
                if (i - 1) * part < totfaces:
                    last_ar = polys[(i - 1) * part:]
                    bigshapes.append(sops.unary_union(last_ar))
                print('Joining')
                p = sops.unary_union(bigshapes)

            print(time.time() - t)

            t = time.time()
            silhouete = shapelyToMultipolygon(p)  # [polygon_utils_cam.Shapely2Polygon(p)]

    return silhouete


def getAmbient(o):
    """Get the ambient shape based on the object's properties.

    This function calculates the ambient shape for a given object based on
    its properties such as cutter diameter, ambient behavior, and limit
    curve. If the object has an ambient cutter restriction, it adjusts the
    ambient shape accordingly. The function also handles the intersection
    with a limit curve if specified.

    Args:
        o (object): An object containing properties that define the ambient shape,
            including attributes like update_ambient_tag, ambient_cutter_restrict,
            ambient_behaviour, ambient_radius, use_limit_curve, limit_curve,
            cutter_diameter, and other relevant geometrical properties.

    Returns:
        None: The function modifies the object in place and does not return a value.
    """

    if o.update_ambient_tag:
        if o.ambient_cutter_restrict:  # cutter stays in ambient & limit curve
            m = o.cutter_diameter / 2
        else:
            m = 0

        if o.ambient_behaviour == 'AROUND':
            r = o.ambient_radius - m
            # in this method we need ambient from silhouete
            o.ambient = getObjectOutline(r, o, True)
        else:
            o.ambient = spolygon.Polygon(((o.min.x + m, o.min.y + m), (o.min.x + m, o.max.y - m),
                                          (o.max.x - m, o.max.y - m), (o.max.x - m, o.min.y + m)))

        if o.use_limit_curve:
            if o.limit_curve != '':
                limit_curve = bpy.data.objects[o.limit_curve]
                polys = curveToShapely(limit_curve)
                o.limit_poly = shapely.ops.unary_union(polys)

                if o.ambient_cutter_restrict:
                    o.limit_poly = o.limit_poly.buffer(
                        o.cutter_diameter / 2, resolution=o.optimisation.circle_detail)
            o.ambient = o.ambient.intersection(o.limit_poly)
    o.update_ambient_tag = False


def getObjectOutline(radius, o, Offset):
    """Get the outline of a set of polygons with an optional offset.

    This function takes a radius and an object containing polygon data, and
    computes the outlines of the polygons. It applies a buffer operation to
    each polygon based on the specified radius and offset direction. The
    resulting outlines can be merged into a single geometry or returned as a
    collection of individual geometries depending on the properties of the
    input object.

    Args:
        radius (float): The radius used for buffering the polygons.
        o (object): An object containing properties for the operation,
            including details about the polygons and options for
            merging.
        Offset (bool): A flag indicating whether to apply a positive or
            negative offset to the buffer operation.

    Returns:
        geometry: The resulting outline as a MultiPolygon or a merged geometry.
    """
  # FIXME: make this one operation independent
    # circle detail, optimize, optimize thresold.

    polygons = getOperationSilhouete(o)

    i = 0
    # print('offseting polygons')

    if Offset:
        offset = 1
    else:
        offset = -1

    outlines = []
    i = 0
    if o.straight:
        join = 2
    else:
        join = 1

    if isinstance(polygons, list):
        polygon_list = polygons
    else:
        polygon_list = polygons.geoms

    for p1 in polygon_list:  # sort by size before this???
        # print(p1.type, len(polygons))
        i += 1
        if radius > 0:
            p1 = p1.buffer(radius * offset, resolution=o.optimisation.circle_detail,
                           join_style=join, mitre_limit=2)
        outlines.append(p1)

    # print(outlines)
    if o.dont_merge:
        outline = sgeometry.MultiPolygon(outlines)
    else:
        outline = shapely.ops.unary_union(outlines)
    return outline


def addOrientationObject(o):
    """Set up orientations for an object in 4 and 5 axis milling.

    This function creates an orientation object in the Blender scene if it
    does not already exist. It configures the orientation based on the
    specified machine axes and rotary axis settings of the provided object.
    The orientation object is represented as an empty with arrows, and its
    rotation locks and angles are adjusted according to the machine
    configuration.

    Args:
        o (object): An object containing machine axes and rotary axis information.
    """
    name = o.name + ' orientation'
    s = bpy.context.scene
    if s.objects.find(name) == -1:
        bpy.ops.object.empty_add(type='ARROWS', align='WORLD', location=(0, 0, 0))

        ob = bpy.context.active_object
        ob.empty_draw_size = 0.05
        ob.show_name = True
        ob.name = name
    ob = s.objects[name]
    if o.machine_axes == '4':

        if o.rotary_axis_1 == 'X':
            ob.lock_rotation = [False, True, True]
            ob.rotation_euler[1] = 0
            ob.rotation_euler[2] = 0
        if o.rotary_axis_1 == 'Y':
            ob.lock_rotation = [True, False, True]
            ob.rotation_euler[0] = 0
            ob.rotation_euler[2] = 0
        if o.rotary_axis_1 == 'Z':
            ob.lock_rotation = [True, True, False]
            ob.rotation_euler[0] = 0
            ob.rotation_euler[1] = 0
    elif o.machine_axes == '5':
        ob.lock_rotation = [False, False, True]

        ob.rotation_euler[2] = 0  # this will be a bit hard to rotate.....


# def addCutterOrientationObject(o):


def removeOrientationObject(o):
    """Remove an orientation object from the current Blender scene.

    This function attempts to remove an object from the Blender scene based
    on the provided object's name. It constructs the name of the orientation
    object by appending ' orientation' to the name of the input object. If
    an object with that name exists in the scene, it will be deleted.

    Args:
        o (Object): The Blender object whose orientation object is to be removed.
    """
  # not working
    name = o.name + ' orientation'
    if bpy.context.scene.objects.find(name) > -1:
        ob = bpy.context.scene.objects[name]
        delob(ob)


def addTranspMat(ob, mname, color, alpha):
    """Add a transparent material to a given object.

    This function checks if a material with the specified name already
    exists in the Blender data. If it does, it retrieves that material; if
    not, it creates a new material with the given name and sets it to use
    nodes. The function then assigns the material to the specified object,
    either replacing an existing material or adding it to the object's
    material slot.

    Args:
        ob (bpy.types.Object): The Blender object to which the material will be added.
        mname (str): The name of the material to be added or retrieved.
        color (tuple): A tuple representing the RGB color of the material.
        alpha (float): The transparency value of the material, ranging from 0.0 (fully
            transparent) to 1.0 (fully opaque).
    """

    if mname in bpy.data.materials:
        mat = bpy.data.materials[mname]
    else:
        mat = bpy.data.materials.new(name=mname)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]

        # Assign it to object
        if ob.data.materials:
            ob.data.materials[0] = mat
        else:
            ob.data.materials.append(mat)


def addMachineAreaObject():
    """Add a machine area object to the current Blender scene.

    This function checks if a machine object named 'CAM_machine' already
    exists in the current scene. If it does, the function retrieves that
    object. If it does not exist, the function creates a new cube mesh
    object, applies transformations, and modifies its geometry to represent
    a machine area. The function ensures that the scene's unit settings are
    set to metric before creating the object and restores the original unit
    settings afterward. The created object is configured to be non-
    renderable and non-selectable.

    Returns:
        None: This function does not return any value.
    """

    s = bpy.context.scene
    ao = bpy.context.active_object
    if s.objects.get('CAM_machine') is not None:
        o = s.objects['CAM_machine']
    else:
        oldunits = s.unit_settings.system
        oldLengthUnit = s.unit_settings.length_unit
        # need to be in metric units when adding machine mesh object
        # in order for location to work properly
        s.unit_settings.system = 'METRIC'
        bpy.ops.mesh.primitive_cube_add(
            align='WORLD', enter_editmode=False, location=(1, 1, -1), rotation=(0, 0, 0))
        o = bpy.context.active_object
        o.name = 'CAM_machine'
        o.data.name = 'CAM_machine'
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
        # o.type = 'SOLID'
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.delete(type='ONLY_FACE')
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE', action='TOGGLE')
        bpy.ops.mesh.select_all(action='TOGGLE')
        bpy.ops.mesh.subdivide(number_cuts=32, smoothness=0, quadcorner='STRAIGHT_CUT', fractal=0,
                               fractal_along_normal=0, seed=0)
        bpy.ops.mesh.select_nth(nth=2, offset=0)
        bpy.ops.mesh.delete(type='EDGE')
        bpy.ops.mesh.primitive_cube_add(
            align='WORLD', enter_editmode=False, location=(1, 1, -1), rotation=(0, 0, 0))

        bpy.ops.object.editmode_toggle()
        # addTranspMat(o, "violet_transparent", (0.800000, 0.530886, 0.725165), 0.1)
        o.display_type = 'BOUNDS'
        o.hide_render = True
        o.hide_select = True
        # o.select = False
        s.unit_settings.system = oldunits
        s.unit_settings.length_unit = oldLengthUnit

    # bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

    o.dimensions = bpy.context.scene.cam_machine.working_area
    if ao is not None:
        ao.select_set(True)
    # else:
    #     bpy.context.scene.objects.active = None


def addMaterialAreaObject():
    """Add a material area object to the current Blender scene.

    This function checks if a material area object named 'CAM_material'
    already exists in the current scene. If it does, it retrieves that
    object; if not, it creates a new cube object to serve as the material
    area. The function then applies transformations to set the dimensions
    and location of the object based on the current camera operation's
    bounds. The created or retrieved object is configured to be non-
    renderable and non-selectable in the viewport.  Raises:     None
    """

    s = bpy.context.scene
    operation = s.cam_operations[s.cam_active_operation]
    getOperationSources(operation)
    getBounds(operation)

    ao = bpy.context.active_object
    if s.objects.get('CAM_material') is not None:
        o = s.objects['CAM_material']
    else:
        bpy.ops.mesh.primitive_cube_add(
            align='WORLD', enter_editmode=False, location=(1, 1, -1), rotation=(0, 0, 0))
        o = bpy.context.active_object
        o.name = 'CAM_material'
        o.data.name = 'CAM_material'
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

        # addTranspMat(o, 'blue_transparent', (0.458695, 0.794658, 0.8), 0.1)
        o.display_type = 'BOUNDS'
        o.hide_render = True
        o.hide_select = True
        o.select_set(state=True, view_layer=None)
    # bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

    o.dimensions = bpy.context.scene.cam_machine.working_area

    o.dimensions = (
        operation.max.x - operation.min.x, operation.max.y - operation.min.y, operation.max.z - operation.min.z)
    o.location = (operation.min.x, operation.min.y, operation.max.z)
    if ao is not None:
        ao.select_set(True)
    # else:
    #     bpy.context.scene.objects.active = None


def getContainer():
    """Get or create a container object for camera objects.

    This function checks if a container object named 'CAM_OBJECTS' exists in
    the current Blender scene. If it does not exist, the function creates a
    new empty object of type 'PLAIN_AXES', names it 'CAM_OBJECTS', sets its
    location to the origin, and hides it. If the container already exists,
    it simply retrieves the existing object.

    Returns:
        bpy.types.Object: The container object for camera objects.
    """

    s = bpy.context.scene
    if s.objects.get('CAM_OBJECTS') is None:
        bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD')
        container = bpy.context.active_object
        container.name = 'CAM_OBJECTS'
        container.location = [0, 0, 0]
        container.hide = True
    else:
        container = s.objects['CAM_OBJECTS']

    return container


# progress('finished')

# tools for voroni graphs all copied from the delaunayVoronoi addon:
class Point:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


def unique(L):
    """Return a list of unhashable elements in L, but without duplicates.

    This function processes a list of unhashable elements, specifically
    focusing on lists that represent 3D coordinates. It sorts the input list
    and then scans it from the end to remove duplicates based on the first
    two coordinates (X and Y) and checks for colinearity in the Z
    coordinate. The function returns a tuple containing the count of
    duplicate vertices and the count of Z colinear elements.

    Args:
        L (list): A list of lists, where each inner list represents

    Returns:
        tuple: A tuple containing two integers:
            - The first integer is the count of duplicate vertices.
            - The second integer is the count of Z colinear elements.
    """
    # For unhashable objects, you can sort the sequence and then scan from the end of the list,
    # deleting duplicates as you go
    nDupli = 0
    nZcolinear = 0
    # sort() brings the equal elements together; then duplicates are easy to weed out in a single pass.
    L.sort()
    last = L[-1]
    for i in range(len(L) - 2, -1, -1):
        if last[:2] == L[i][:2]:  # XY coordinates compararison
            if last[2] == L[i][2]:  # Z coordinates compararison
                nDupli += 1  # duplicates vertices
            else:  # Z colinear
                nZcolinear += 1
            del L[i]
        else:
            last = L[i]
    return (nDupli,
            nZcolinear)  # list data type is mutable,
    # input list will automatically update and doesn't need to be returned


def checkEqual(lst):
    return lst[1:] == lst[:-1]


def prepareIndexed(o):
    """Prepare and index objects for transformation in Blender.

    This function stores the world matrices and parent relationships of the
    objects contained within the provided object `o`. It then clears the
    current parent relationships while maintaining the transformations, sets
    a new orientation object, and parents all objects to this orientation
    object. Finally, it resets the location and rotation of the orientation
    object to the origin.

    Args:
        o (Object): The object containing the collection of objects to
    """

    s = bpy.context.scene
    # first store objects positions/rotations
    o.matrices = []
    o.parents = []
    for ob in o.objects:
        o.matrices.append(ob.matrix_world.copy())
        o.parents.append(ob.parent)

    # then rotate them
    for ob in o.objects:
        ob.select = True
    s.objects.active = ob
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

    s.cursor.location = (0, 0, 0)
    oriname = o.name + ' orientation'
    ori = s.objects[oriname]
    o.orientation_matrix = ori.matrix_world.copy()
    o.rotationaxes = rotTo2axes(ori.rotation_euler, 'CA')
    ori.select = True
    s.objects.active = ori
    # we parent all objects to the orientation object
    bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
    for ob in o.objects:
        ob.select = False
    # then we move the orientation object to 0,0
    bpy.ops.object.location_clear()
    bpy.ops.object.rotation_clear()
    ori.select = False
    for ob in o.objects:
        activate(ob)

        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

    # rot=ori.matrix_world.inverted()
    # #rot.x=-rot.x
    # #rot.y=-rot.y
    # #rot.z=-rot.z
    # rotationaxes = rotTo2axes(ori.rotation_euler,'CA')
    #
    # #bpy.context.space_data.pivot_point = 'CURSOR'
    # #bpy.context.space_data.pivot_point = 'CURSOR'
    #
    # for ob in o.objects:
    #     ob.rotation_euler.rotate(rot)


def cleanupIndexed(operation):
    """Clean up indexed operations by setting object orientations and paths.

    This function updates the orientation and location of a specified object
    in the Blender scene based on the provided operation. It retrieves the
    orientation matrix from the operation and applies it to the
    corresponding objects. Additionally, it sets the parent-child
    relationships for the objects involved in the operation.

    Args:
        operation (OperationType): An object containing information about
    """

    s = bpy.context.scene
    oriname = operation.name + 'orientation'

    ori = s.objects[oriname]
    path = s.objects["cam_path_{}{}".format(operation.name)]

    ori.matrix_world = operation.orientation_matrix
    # set correct path location
    path.location = ori.location
    path.rotation_euler = ori.rotation_euler

    print(ori.matrix_world, operation.orientation_matrix)
    # TODO: fix this here wrong order can cause objects out of place
    for i, ob in enumerate(operation.objects):
        ob.parent = operation.parents[i]
    for i, ob in enumerate(operation.objects):
        ob.matrix_world = operation.matrices[i]


def rotTo2axes(e, axescombination):
    """Converts an orientation object rotation to a rotation defined by two
    rotational axes on the machine.

    This function takes an orientation object and a specified axes
    combination, then computes the angles corresponding to the defined axes.
    It supports different combinations of axes for indexed machining. The
    function utilizes vector mathematics to determine the signed angles
    based on the rotation provided by the orientation object.

    Args:
        e (OrientationObject): The orientation object representing the rotation to be converted.
        axescombination (str): A string indicating the axes combination ('CA' or 'CB') for which to
            compute angles.

    Returns:
        tuple: A tuple containing two float values representing the computed angles for
            the specified axes combination.
    """
    v = Vector((0, 0, 1))
    v.rotate(e)
    # if axes
    if axescombination == 'CA':
        v2d = Vector((v.x, v.y))
        # ?is this right?It should be vector defining 0 rotation
        a1base = Vector((0, -1))
        if v2d.length > 0:
            cangle = a1base.angle_signed(v2d)
        else:
            return (0, 0)
        v2d = Vector((v2d.length, v.z))
        a2base = Vector((0, 1))
        aangle = a2base.angle_signed(v2d)
        print('angles', cangle, aangle)
        return (cangle, aangle)

    elif axescombination == 'CB':
        v2d = Vector((v.x, v.y))
        # ?is this right?It should be vector defining 0 rotation
        a1base = Vector((1, 0))
        if v2d.length > 0:
            cangle = a1base.angle_signed(v2d)
        else:
            return (0, 0)
        v2d = Vector((v2d.length, v.z))
        a2base = Vector((0, 1))

        bangle = a2base.angle_signed(v2d)

        print('angles', cangle, bangle)

        return (cangle, bangle)

    # v2d=((v[a[0]],v[a[1]]))
    # angle1=a1base.angle(v2d)#C for ca
    # print(angle1)
    # if axescombination[0]=='C':
    #     e1=Vector((0,0,-angle1))
    # elif axescombination[0]=='A':#TODO: finish this after prototyping stage
    #     pass;
    # v.rotate(e1)
    # vbase=Vector(0,1,0)
    # bangle=v.angle(vzbase)
    # print(v)
    # print(bangle)

    # return (angle1, angle2)


def reload_paths(o):
    """Reload the path data for a given object.

    This function retrieves the path data for the specified object from a
    pickle file and updates the object's mesh in the Blender scene. It
    checks if a previous path mesh exists and removes it if necessary. The
    new path data includes warnings, duration, and vertex information which
    is used to create a new mesh. The function also ensures that the
    object's name is consistent with the path data.

    Args:
        o (Object): The object for which the path data is being reloaded.
    """

    oname = "cam_path_" + o.name
    s = bpy.context.scene
    # for o in s.objects:
    ob = None
    old_pathmesh = None
    if oname in s.objects:
        old_pathmesh = s.objects[oname].data
        ob = s.objects[oname]

    picklepath = getCachePath(o) + '.pickle'
    f = open(picklepath, 'rb')
    d = pickle.load(f)
    f.close()

    # passed=False
    # while not passed:
    #     try:
    #         f=open(picklepath,'rb')
    #         d=pickle.load(f)
    #         f.close()
    #         passed=True
    #     except:
    #         print('sleep')
    #         time.sleep(1)

    o.info.warnings = d['warnings']
    o.info.duration = d['duration']
    verts = d['path']

    edges = []
    for a in range(0, len(verts) - 1):
        edges.append((a, a + 1))

    oname = "cam_path_" + o.name
    mesh = bpy.data.meshes.new(oname)
    mesh.name = oname
    mesh.from_pydata(verts, edges, [])

    if oname in s.objects:
        s.objects[oname].data = mesh
    else:
        object_utils.object_data_add(bpy.context, mesh, operator=None)
        ob = bpy.context.active_object
        ob.name = oname
    ob = s.objects[oname]
    ob.location = (0, 0, 0)
    o.path_object_name = oname
    o.changed = False

    if old_pathmesh is not None:
        bpy.data.meshes.remove(old_pathmesh)


# def setup_operation_preset():
#     scene = bpy.context.scene
#     cam_operations = scene.cam_operations
#     active_operation = scene.cam_active_operation
#     try:
#         o = cam_operations[active_operation]
#     except IndexError:
#         bpy.ops.scene.cam_operation_add()
#         o = cam_operations[active_operation]
#     return o


# Moved from init - the following code was moved here to permit the import fix
USE_PROFILER = False

was_hidden_dict = {}

_IS_LOADING_DEFAULTS = False


def updateMachine(self, context):
    """Update the machine with the given context.

    This method is responsible for updating the machine's state or
    configuration based on the provided context. It prints a message
    indicating that the update process has started. If the system is not
    currently loading defaults, it will proceed to add a machine area
    object.

    Args:
        context: The context in which the machine update is being performed.
    """

    print('Update Machine')
    if not _IS_LOADING_DEFAULTS:
        addMachineAreaObject()


def updateMaterial(self, context):
    """Update the material in the given context.

    This function is responsible for updating the material properties based
    on the provided context. It prints a message indicating that the
    material update process has started and then calls the
    `addMaterialAreaObject` function to perform the actual update.

    Args:
        context: The context in which the material update is to be performed.
    """

    print('Update Material')
    addMaterialAreaObject()


def updateOperation(self, context):
    """Update the visibility and selection state of camera operations in the
    scene.

    This method manages the visibility of objects in the scene based on the
    current camera operation settings. If the 'hide_all_others' flag is set
    to True, it hides all other objects except for the currently active
    camera operation object. If 'hide_all_others' is False, it restores
    visibility for previously hidden objects. The method also attempts to
    highlight the active object in the 3D view and make it the active object
    in the scene.

    Args:
        context (bpy.context): The Blender context containing scene and
    """

    scene = context.scene
    ao = scene.cam_operations[scene.cam_active_operation]
    operationValid(self, context)

    if ao.hide_all_others:
        for _ao in scene.cam_operations:
            if _ao.path_object_name in bpy.data.objects:
                other_obj = bpy.data.objects[_ao.path_object_name]
                current_obj = bpy.data.objects[ao.path_object_name]
                if other_obj != current_obj:
                    other_obj.hide = True
                    other_obj.select = False
    else:
        for path_obj_name in was_hidden_dict:
            print(was_hidden_dict)
            if was_hidden_dict[path_obj_name]:
                # Find object and make it hidde, then reset 'hidden' flag
                obj = bpy.data.objects[path_obj_name]
                obj.hide = True
                obj.select = False
                was_hidden_dict[path_obj_name] = False

    # try highlighting the object in the 3d view and make it active
    bpy.ops.object.select_all(action='DESELECT')
    # highlight the cutting path if it exists
    try:
        ob = bpy.data.objects[ao.path_object_name]
        ob.select_set(state=True, view_layer=None)
        # Show object if, it's was hidden
        if ob.hide:
            ob.hide = False
            was_hidden_dict[ao.path_object_name] = True
        bpy.context.scene.objects.active = ob
    except Exception as e:
        print(e)

# Moved from init - part 2


def isValid(o, context):
    """Check the validity of a geometry source.

    This function verifies if the provided geometry source is valid based on
    its type. It checks if the object name ends with '_cut_bridges' for
    OBJECT sources, if the collection name exists and is not empty for
    COLLECTION sources, and if the source image name exists for IMAGE
    sources. The function returns True if the geometry source is valid and
    False otherwise.

    Args:
        o: An object containing properties such as geometry_source, object_name,
            collection_name, and source_image_name.
        context: The context in which the validity is being checked (not used in this
            function).

    Returns:
        bool: True if the geometry source is valid, False otherwise.
    """

    valid = True
    if o.geometry_source == 'OBJECT':
        if not o.object_name.endswith('_cut_bridges'):  #  let empty bridge cut be valid
            if o.object_name not in bpy.data.objects:
                valid = False
    if o.geometry_source == 'COLLECTION':
        if o.collection_name not in bpy.data.collections:
            valid = False
        elif len(bpy.data.collections[o.collection_name].objects) == 0:
            valid = False

    if o.geometry_source == 'IMAGE':
        if o.source_image_name not in bpy.data.images:
            valid = False
    return valid


def operationValid(self, context):
    """Validate the current camera operation in the given context.

    This method checks if the current camera operation is valid based on the
    provided context. It updates the operation's validity status and sets
    appropriate warnings if the operation is invalid. Additionally, it
    manages specific settings related to image geometry sources.

    Args:
        context (Context): The context containing the scene and camera operations.

    Returns:
        None: This function does not return a value, but it modifies the state
        of the operation and updates warnings accordingly.
    """

    scene = context.scene
    o = scene.cam_operations[scene.cam_active_operation]
    o.changed = True
    o.valid = isValid(o, context)
    invalidmsg = "Invalid Source Object for Operation.\n"
    if o.valid:
        o.info.warnings = ""
    else:
        o.info.warnings = invalidmsg

    if o.geometry_source == 'IMAGE':
        o.optimisation.use_exact = False
    o.update_offsetimage_tag = True
    o.update_zbufferimage_tag = True
    print('validity ')


def isChainValid(chain, context):
    """Check the validity of a chain of operations within a given context.

    This function verifies whether all operations in the provided chain are
    valid according to the context's scene. It first checks if the chain has
    any operations. If the chain is empty, it returns an indication of
    invalidity. For each operation in the chain, it checks if the operation
    exists in the scene's camera operations and whether it is valid. If any
    operation is not found or is invalid, an appropriate error message is
    returned.

    Args:
        chain (Chain): The chain of operations to validate.
        context (Context): The context containing the scene and camera operations.

    Returns:
        tuple: A tuple containing a boolean indicating validity and an error message.
            The first element is True if the chain is valid, otherwise False.
            The second element is an error message if invalid, or an empty string if
            valid.
    """

    s = context.scene
    if len(chain.operations) == 0:
        return (False, "")
    for cho in chain.operations:
        found_op = None
        for so in s.cam_operations:
            if so.name == cho.name:
                found_op = so
        if found_op == None:
            return (False, f"Couldn't Find Operation {cho.name}")
        if isValid(found_op, context) is False:
            return (False, f"Operation {found_op.name} Is Not Valid")
    return (True, "")


def updateOperationValid(self, context):
    updateOperation(self, context)


# Update functions start here
def updateChipload(self, context):
    """Update the chipload based on feedrate, spindle RPM, and cutter
    parameters.

    This method calculates the chipload for a machining operation. It first
    computes the old chipload using the formula: chipload = feedrate /
    (spindle_rpm * cutter_flutes). Then, it attempts to adjust this value to
    account for chip thinning when cutting at less than 50% cutter
    engagement with cylindrical end mills. The calculation involves two
    formulas: one for nominal chipload and another that incorporates chip
    thinning compensation. The function currently lacks consistency in
    results, and there may be issues with unit conversions or the underlying
    mathematics.

    Args:
        context: The context in which the update is being performed (not used in this
            implementation).

    Returns:
        None: This function does not return a value but updates the chipload attribute
            of the instance.
    """
    print('Update Chipload ')
    o = self
    # Old chipload
    o.info.chipload = (o.feedrate / (o.spindle_rpm * o.cutter_flutes))
    # New chipload with chip thining compensation.
    # I have tried to combine these 2 formulas to compinsate for the phenomenon of chip thinning when cutting at less
    # than 50% cutter engagement with cylindrical end mills. formula 1 Nominal Chipload is
    # " feedrate mm/minute = spindle rpm x chipload x cutter diameter mm x cutter_flutes "
    # formula 2 (.5*(cutter diameter mm devided by dist_between_paths)) divided by square root of
    # ((cutter diameter mm devided by dist_between_paths)-1) x Nominal Chipload
    # Nominal Chipload = what you find in end mill data sheats recomended chip load at %50 cutter engagment.
    # I am sure there is a better way to do this. I dont get consistent result and
    # I am not sure if there is something wrong with the units going into the formula, my math or my lack of
    # underestanding of python or programming in genereal. Hopefuly some one can have a look at this and with any luck
    # we will be one tiny step on the way to a slightly better chipload calculating function.

    # self.chipload = ((0.5*(o.cutter_diameter/o.dist_between_paths))/(sqrt((o.feedrate*1000)/(o.spindle_rpm*o.cutter_diameter*o.cutter_flutes)*(o.cutter_diameter/o.dist_between_paths)-1)))
    print(o.info.chipload)


def updateOffsetImage(self, context):
    """Refresh the Offset Image Tag for re-rendering.

    This method updates the chip load and marks the offset image tag for re-
    rendering. It sets the `changed` attribute to True, indicating that an
    update has occurred, and also sets the `update_offsetimage_tag`
    attribute to True to signal that the offset image tag needs to be
    refreshed.

    Args:
        context: The context in which the update is being performed.
    """
    updateChipload(self, context)
    print('Update Offset')
    self.changed = True
    self.update_offsetimage_tag = True


def updateZbufferImage(self, context):
    """Update the Z-buffer and offset image tags for recalculation.

    This method marks the Z-buffer and offset image tags as changed,
    indicating that they need to be updated during the calculation process.
    It also calls the `getOperationSources` function to ensure that the
    necessary sources for the operation are retrieved.

    Args:
        context: The context in which the update is being performed.
    """
    # print('updatezbuf')
    # print(self,context)
    self.changed = True
    self.update_zbufferimage_tag = True
    self.update_offsetimage_tag = True
    getOperationSources(self)


def updateStrategy(o, context):
    """Update the strategy of the given object based on its machine axes.

    This function modifies the state of the object `o` by setting its
    `changed` attribute to `True` and printing a message indicating that the
    strategy is being updated. It checks the value of `o.machine_axes` and,
    depending on its value, either adds or removes an orientation object.
    Finally, it calls the `updateExact` function to perform further updates
    based on the provided context.

    Args:
        o (object): The object whose strategy is to be updated.
        context (object): The context in which the update is performed.
    """

    """"""
    o.changed = True
    print('Update Strategy')
    if o.machine_axes == '5' or (
            o.machine_axes == '4' and o.strategy4axis == 'INDEXED'):  # INDEXED 4 AXIS DOESN'T EXIST NOW...
        addOrientationObject(o)
    else:
        removeOrientationObject(o)
    updateExact(o, context)


def updateCutout(o, context):
    pass


def updateExact(o, context):
    """Update the state of the given object for exact operations.

    This function modifies the properties of the object `o` to indicate that
    an update has occurred. It sets several flags to true, indicating that
    the object's state has changed and that certain image tags need to be
    updated. Additionally, it checks the optimization settings and the
    strategy being used to determine whether exact mode can be utilized. If
    the current operation cannot use exact mode, it disables the use of
    OpenCamLib.

    Args:
        o (object): The object to be updated, which contains properties
            related to optimization and strategy.
        context (object): The context in which the update is being performed.
    """

    print('Update Exact ')
    o.changed = True
    o.update_zbufferimage_tag = True
    o.update_offsetimage_tag = True
    if o.optimisation.use_exact:
        if o.strategy == 'POCKET' or o.strategy == 'MEDIAL_AXIS' or o.inverse:
            o.optimisation.use_opencamlib = False
            print('Current Operation Cannot Use Exact Mode')
    else:
        o.optimisation.use_opencamlib = False


def updateOpencamlib(o, context):
    """Update the OpenCAMLib settings for a given operation.

    This function modifies the properties of the provided operation object
    based on its current strategy and optimization settings. If the
    operation's strategy is either 'POCKET' or 'MEDIAL_AXIS', and if
    OpenCAMLib is being used for optimization, the function will disable the
    use of both exact optimization and OpenCAMLib, indicating that the
    current operation cannot utilize OpenCAMLib.

    Args:
        o (object): The operation object that contains optimization settings
            and strategy information.
        context (object): The context in which the operation is being updated.

    Returns:
        None: This function does not return a value.
    """

    print('Update OpenCAMLib ')
    o.changed = True
    if o.optimisation.use_opencamlib and (
            o.strategy == 'POCKET' or o.strategy == 'MEDIAL_AXIS'):
        o.optimisation.use_exact = False
        o.optimisation.use_opencamlib = False
        print('Current Operation Cannot Use OpenCAMLib')


def updateBridges(o, context):
    """Update the status of bridges.

    This function marks the given object as changed and prints a message
    indicating that the bridges are being updated. It is typically used in
    scenarios where the state of the bridges needs to be refreshed or
    modified based on certain conditions or events.

    Args:
        o (object): The object representing the bridges that need to be updated.
        context (object): The context in which the update is being performed.
    """

    print('Update Bridges ')
    o.changed = True


def updateRotation(o, context):
    """Update the rotation of a specified object in the Blender context.

    This function modifies the rotation of a Blender object based on the
    properties of the provided object 'o'. It checks which rotations are
    enabled and applies them accordingly, either aligning the rotation with
    the X-axis or the Y-axis based on the 'A_along_x' attribute.

    Args:
        o (object): An object containing rotation settings and flags.
        context (bpy.context): The current Blender context.

    Returns:
        None: This function does not return a value.
    """

    print('Update Rotation')
    if o.enable_B or o.enable_A:
        print(o, o.rotation_A)
        ob = bpy.data.objects[o.object_name]
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        if o.A_along_x:  # A parallel with X
            if o.enable_A:
                bpy.context.active_object.rotation_euler.x = o.rotation_A
            if o.enable_B:
                bpy.context.active_object.rotation_euler.y = o.rotation_B
        else:  # A parallel with Y
            if o.enable_A:
                bpy.context.active_object.rotation_euler.y = o.rotation_A
            if o.enable_B:
                bpy.context.active_object.rotation_euler.x = o.rotation_B


# def updateRest(o, context):
#    print('update rest ')
#    # if o.use_layers:
# o.movement.parallel_step_back = False
#    o.changed = True

def updateRest(o, context):
    """Update the state of the object.

    This function modifies the state of the provided object by setting its
    'changed' attribute to True. It also prints a message indicating that
    the update operation has been performed. This function is typically used
    in scenarios where the object's state needs to be refreshed or marked as
    modified.

    Args:
        o (object): The object whose state is to be updated.
        context (object): The context in which the update is being performed.
    """

    print('Update Rest ')
    o.changed = True


#    if (o.strategy == 'WATERLINE'):
#        o.use_layers = True


def getStrategyList(scene, context):
    """Get a list of available strategies for the given scene and context.

    This function retrieves a predefined list of machining strategies that
    can be used in a specific scene. Each strategy is represented as a tuple
    containing an identifier, a display name, and a description of the
    operation. The list includes various operations such as cutouts,
    pockets, drilling, and more. The function may also include experimental
    strategies based on user preferences.

    Args:
        scene: The scene object in which the strategies will be applied.
        context: The context in which the function is called, typically containing
            information
            about the current state of the application.

    Returns:
        list: A list of tuples, each containing a strategy identifier, display name,
            and
            description of the strategy.
    """

    use_experimental = bpy.context.preferences.addons['cam'].preferences.experimental
    items = [
        ('CUTOUT', 'Profile(Cutout)', 'Cut the silhouete with offset'),
        ('POCKET', 'Pocket', 'Pocket operation'),
        ('DRILL', 'Drill', 'Drill operation'),
        ('PARALLEL', 'Parallel', 'Parallel lines on any angle'),
        ('CROSS', 'Cross', 'Cross paths'),
        ('BLOCK', 'Block', 'Block path'),
        ('SPIRAL', 'Spiral', 'Spiral path'),
        ('CIRCLES', 'Circles', 'Circles path'),
        ('OUTLINEFILL', 'Outline Fill',
         'Detect outline and fill it with paths as pocket. Then sample these paths on the 3d surface'),
        ('CARVE', 'Project curve to surface', 'Engrave the curve path to surface'),
        ('WATERLINE', 'Waterline - Roughing -below zero',
         'Waterline paths - constant z below zero'),
        ('CURVE', 'Curve to Path', 'Curve object gets converted directly to path'),
        ('MEDIAL_AXIS', 'Medial axis',
         'Medial axis, must be used with V or ball cutter, for engraving various width shapes with a single stroke ')
    ]
    #   if use_experimental:
    #       items.extend([('MEDIAL_AXIS', 'Medial axis - EXPERIMENTAL',
    #                      'Medial axis, must be used with V or ball cutter, for engraving various width shapes with a single stroke ')]);
    # ('PENCIL', 'Pencil - EXPERIMENTAL','Pencil operation - detects negative corners in the model and mills only those.'),
    # ('CRAZY', 'Crazy path - EXPERIMENTAL', 'Crazy paths - dont even think about using this!'),
    #                     ('PROJECTED_CURVE', 'Projected curve - EXPERIMENTAL', 'project 1 curve towards other curve')])
    return items

# The following functions are temporary
# until all content in __init__.py is cleaned up


def update_material(self, context):
    addMaterialAreaObject()


def update_operation(self, context):
    """Update the operation based on the current context.

    This function retrieves the active camera operation from the Blender
    context and updates it using the `updateRest` function. It accesses the
    active operation from the scene's camera operations and passes the
    current context to the update function.

    Args:
        context: The context in which the operation is being updated.
    """

    # from . import updateRest
    active_op = bpy.context.scene.cam_operations[bpy.context.scene.cam_active_operation]
    updateRest(active_op, bpy.context)


def update_exact_mode(self, context):
    """Update the exact mode of the active camera operation.

    This function retrieves the currently active camera operation from the
    Blender context and updates its exact mode using the `updateExact`
    function. It accesses the active operation through the `cam_operations`
    list in the current scene and passes the context to the updating
    function.

    Args:
        context: The Blender context used for updating the camera operation.
    """

    # from . import updateExact
    active_op = bpy.context.scene.cam_operations[bpy.context.scene.cam_active_operation]
    updateExact(active_op, bpy.context)


def update_opencamlib(self, context):
    """Update the OpenCamLib with the current active operation.

    This function retrieves the currently active camera operation from the
    Blender context and updates the OpenCamLib accordingly. It accesses the
    active operation from the scene's camera operations and passes it along
    with the current context to the updateOpencamlib function.

    Args:
        context: The context in which the operation is being performed.
    """

    # from . import updateOpencamlib
    active_op = bpy.context.scene.cam_operations[bpy.context.scene.cam_active_operation]
    updateOpencamlib(active_op, bpy.context)


def update_zbuffer_image(self, context):
    """Update the Z-buffer image based on the active camera operation.

    This function retrieves the currently active camera operation from the
    Blender context and updates the Z-buffer image accordingly. It utilizes
    an external function, `updateZbufferImage`, to perform the actual
    update. The context is passed to ensure that the update is performed
    with the correct scene information.

    Args:
        context: The Blender context containing the current scene and operations.
    """

    # from . import updateZbufferImage
    active_op = bpy.context.scene.cam_operations[bpy.context.scene.cam_active_operation]
    updateZbufferImage(active_op, bpy.context)


# Moved from init - part 3

@bpy.app.handlers.persistent
def check_operations_on_load(context):
    """Checks for broken computations on load and resets them.

    This function ensures that necessary add-ons are enabled and resets any
    ongoing computations in the camera operations. It also sets the
    interface level to the previously used level when loading a new file,
    checks for updates to the add-on, and copies user presets if they have
    not been copied yet. Additionally, it updates the operation presets if
    required.

    Args:
        context: The context in which the function is called,
            typically containing information about the current
            Blender session.
    """

    addons = bpy.context.preferences.addons

    modules = [
        "curve_tools",
        "curve_simplify",
        "add_curve_extra_objects",
    ]

    for module in modules:
        if module not in addons:
            bpy.ops.preferences.addon_enable(module=module)

    s = bpy.context.scene
    for o in s.cam_operations:
        if o.computing:
            o.computing = False
    # set interface level to previously used level for a new file
    if not bpy.data.filepath:
        _IS_LOADING_DEFAULTS = True
        s.interface.level = bpy.context.preferences.addons["cam"].preferences.default_interface_level
        machine_preset = bpy.context.preferences.addons[
            "cam"].preferences.machine_preset = bpy.context.preferences.addons["cam"].preferences.default_machine_preset
        if len(machine_preset) > 0:
            print("Loading Preset:", machine_preset)
            # load last used machine preset
            bpy.ops.script.execute_preset(
                filepath=machine_preset, menu_idname="CAM_MACHINE_MT_presets"
            )
        _IS_LOADING_DEFAULTS = False
    # check for updated version of the plugin
    bpy.ops.render.cam_check_updates()
    # copy presets if not there yet
    if bpy.context.preferences.addons["cam"].preferences.just_updated:
        preset_source_path = Path(__file__).parent / "presets"
        preset_target_path = Path(bpy.utils.script_path_user()) / "presets"

        def copy_if_not_exists(src, dst):
            """Copy a file from source to destination if it does not already exist.

            This function checks if the destination file exists. If it does not, the
            function copies the file from the source path to the destination path
            using a high-level file copy operation that preserves metadata.

            Args:
                src (str): The path to the source file that needs to be copied.
                dst (str): The path to the destination where the file should be copied.
            """

            if Path(dst).exists() == False:
                shutil.copy2(src, dst)

        shutil.copytree(
            preset_source_path,
            preset_target_path,
            copy_function=copy_if_not_exists,
            dirs_exist_ok=True,
        )

        bpy.context.preferences.addons["cam"].preferences.just_updated = False
        bpy.ops.wm.save_userpref()

    if not bpy.context.preferences.addons["cam"].preferences.op_preset_update:
        # Update the Operation presets
        op_presets_source = Path(__file__).parent / "presets" / "cam_operations"
        op_presets_target = Path(bpy.utils.script_path_user()) / "presets" / "cam_operations"
        shutil.copytree(op_presets_source, op_presets_target, dirs_exist_ok=True)
        bpy.context.preferences.addons["cam"].preferences.op_preset_update = True


# add pocket op for medial axis and profile cut inside to clean unremoved material
def Add_Pocket(self, maxdepth, sname, new_cutter_diameter):
    """Add a pocket operation for the medial axis and perform a profile cut.

    This function first deselects all objects in the current Blender scene
    and then checks for existing medial pocket objects, deleting them if
    found. It verifies whether a medial pocket operation already exists in
    the camera operations. If not, it creates a new pocket operation with
    the specified parameters. The function also modifies the selected object
    to create a silhouette offset based on the new cutter diameter.

    Args:
        maxdepth (float): The maximum depth of the pocket to be created.
        sname (str): The name of the object to which the pocket will be added.
        new_cutter_diameter (float): The diameter of the cutter used for the operation.
    """

    bpy.ops.object.select_all(action='DESELECT')
    s = bpy.context.scene
    mpocket_exists = False
    for ob in s.objects:  # delete old medial pocket
        if ob.name.startswith("medial_poc"):
            ob.select_set(True)
            bpy.ops.object.delete()

    for op in s.cam_operations:  # verify medial pocket operation exists
        if op.name == "MedialPocket":
            mpocket_exists = True

    ob = bpy.data.objects[sname]
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    silhoueteOffset(ob, -new_cutter_diameter/2, 1, 0.3)
    bpy.context.active_object.name = 'medial_pocket'

    if not mpocket_exists:     # create a pocket operation if it does not exist already
        s.cam_operations.add()
        o = s.cam_operations[-1]
        o.object_name = 'medial_pocket'
        s.cam_active_operation = len(s.cam_operations) - 1
        o.name = 'MedialPocket'
        o.filename = o.name
        o.strategy = 'POCKET'
        o.use_layers = False
        o.material.estimate_from_model = False
        o.material.size[2] = -maxdepth
        o.minz_from = 'MATERIAL'
