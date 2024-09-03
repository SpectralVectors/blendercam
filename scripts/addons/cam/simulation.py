"""BlenderCAM 'simulation.py' © 2012 Vilem Novak

Functions to generate a mesh simulation from CAM Chain / Operation data.
"""

import math
import time

import numpy as np

import bpy
from mathutils import Vector

from .async_op import progress_async
from .image_utils import (
    getCutterArray,
    numpysave,
)
from .simple import getSimulationPath
from .utils import (
    getBoundsMultiple,
    getOperationSources,
)


def createSimulationObject(name, operations, i):
    oname = "csim_" + name

    o = operations[0]

    if oname in bpy.data.objects:
        ob = bpy.data.objects[oname]
    else:
        bpy.ops.mesh.primitive_plane_add(
            align="WORLD", enter_editmode=False, location=(0, 0, 0), rotation=(0, 0, 0)
        )
        ob = bpy.context.active_object
        ob.name = oname

        bpy.ops.object.modifier_add(type="SUBSURF")
        ss = ob.modifiers[-1]
        ss.subdivision_type = "SIMPLE"
        ss.levels = 6
        ss.render_levels = 6
        bpy.ops.object.modifier_add(type="SUBSURF")
        ss = ob.modifiers[-1]
        ss.subdivision_type = "SIMPLE"
        ss.levels = 4
        ss.render_levels = 3
        bpy.ops.object.modifier_add(type="DISPLACE")

    ob.location = ((o.max.x + o.min.x) / 2, (o.max.y + o.min.y) / 2, o.min.z)
    ob.scale.x = (o.max.x - o.min.x) / 2
    ob.scale.y = (o.max.y - o.min.y) / 2
    print(o.max.x, o.min.x)
    print(o.max.y, o.min.y)
    print("bounds")
    disp = ob.modifiers[-1]
    disp.direction = "Z"
    disp.texture_coords = "LOCAL"
    disp.mid_level = 0

    if oname in bpy.data.textures:
        t = bpy.data.textures[oname]

        t.type = "IMAGE"
        disp.texture = t

        t.image = i
    else:
        bpy.ops.texture.new()
        for t in bpy.data.textures:
            if t.name == "Texture":
                t.type = "IMAGE"
                t.name = oname
                t = t.type_recast()
                t.type = "IMAGE"
                t.image = i
                disp.texture = t
    ob.hide_render = True
    bpy.ops.object.shade_smooth()


async def doSimulation(name, operations):
    """Perform Simulation of Operations. Currently only for 3 Axis"""
    for o in operations:
        getOperationSources(o)
    limits = getBoundsMultiple(
        operations
    )  # this is here because some background computed operations still didn't have bounds data
    i = await generateSimulationImage(operations, limits)
    #    cp = getCachePath(operations[0])[:-len(operations[0].name)] + name
    cp = getSimulationPath() + name
    print("cp=", cp)
    iname = cp + "_sim.exr"

    numpysave(i, iname)
    i = bpy.data.images.load(iname)
    createSimulationObject(name, operations, i)


async def generateSimulationImage(operations, limits):
    minx, miny, minz, maxx, maxy, maxz = limits
    # print(minx,miny,minz,maxx,maxy,maxz)
    sx = maxx - minx
    sy = maxy - miny

    o = operations[0]  # getting sim detail and others from first op.
    simulation_detail = o.optimisation.simulation_detail
    borderwidth = o.borderwidth
    resx = math.ceil(sx / simulation_detail) + 2 * borderwidth
    resy = math.ceil(sy / simulation_detail) + 2 * borderwidth

    # create array in which simulation happens, similar to an image to be painted in.
    si = np.full(shape=(resx, resy), fill_value=maxz, dtype=float)

    num_operations = len(operations)

    start_time = time.time()

    for op_count, o in enumerate(operations):
        ob = bpy.data.objects["cam_path_{}".format(o.name)]
        m = ob.data
        verts = m.vertices

        if o.do_simulation_feedrate:
            kname = "feedrates"
            m.use_customdata_edge_crease = True

            if m.shape_keys is None or m.shape_keys.key_blocks.find(kname) == -1:
                ob.shape_key_add()
                if len(m.shape_keys.key_blocks) == 1:
                    ob.shape_key_add()
                shapek = m.shape_keys.key_blocks[-1]
                shapek.name = kname
            else:
                shapek = m.shape_keys.key_blocks[kname]
            shapek.data[0].co = (0.0, 0, 0)

        totalvolume = 0.0

        cutterArray = getCutterArray(o, simulation_detail)
        cutterArray = -cutterArray
        lasts = verts[1].co
        perc = -1
        vtotal = len(verts)
        dropped = 0

        xs = 0
        ys = 0

        for i, vert in enumerate(verts):
            if perc != int(100 * i / vtotal):
                perc = int(100 * i / vtotal)
                total_perc = (perc + op_count * 100) / num_operations
                await progress_async(f"Simulation", int(total_perc))

            if i > 0:
                volume = 0
                volume_partial = 0
                s = vert.co
                v = s - lasts

                l = v.length
                if (lasts.z < maxz or s.z < maxz) and not (
                    v.x == 0 and v.y == 0 and v.z > 0
                ):  # only simulate inside material, and exclude lift-ups
                    if v.x == 0 and v.y == 0 and v.z < 0:
                        # if the cutter goes straight down, we don't have to interpolate.
                        pass

                    elif v.length > simulation_detail:  # and not :

                        v.length = simulation_detail
                        lastxs = xs
                        lastys = ys
                        while v.length < l:
                            xs = int(
                                (lasts.x + v.x - minx) / simulation_detail
                                + borderwidth
                                + simulation_detail / 2
                            )
                            # -middle
                            ys = int(
                                (lasts.y + v.y - miny) / simulation_detail
                                + borderwidth
                                + simulation_detail / 2
                            )
                            # -middle
                            z = lasts.z + v.z
                            # print(z)
                            if lastxs != xs or lastys != ys:
                                volume_partial = simCutterSpot(
                                    xs, ys, z, cutterArray, si, o.do_simulation_feedrate
                                )
                                if o.do_simulation_feedrate:
                                    totalvolume += volume
                                    volume += volume_partial
                                lastxs = xs
                                lastys = ys
                            else:
                                dropped += 1
                            v.length += simulation_detail

                    xs = int(
                        (s.x - minx) / simulation_detail
                        + borderwidth
                        + simulation_detail / 2
                    )  # -middle
                    ys = int(
                        (s.y - miny) / simulation_detail
                        + borderwidth
                        + simulation_detail / 2
                    )  # -middle
                    volume_partial = simCutterSpot(
                        xs, ys, s.z, cutterArray, si, o.do_simulation_feedrate
                    )
                if (
                    o.do_simulation_feedrate
                ):  # compute volumes and write data into shapekey.
                    volume += volume_partial
                    totalvolume += volume
                    if l > 0:
                        load = volume / l
                    else:
                        load = 0

                    # this will show the shapekey as debugging graph and will use same data to estimate parts
                    # with heavy load
                    if l != 0:
                        shapek.data[i].co.y = (load) * 0.000002
                    else:
                        shapek.data[i].co.y = shapek.data[i - 1].co.y
                    shapek.data[i].co.x = shapek.data[i - 1].co.x + l * 0.04
                    shapek.data[i].co.z = 0
                lasts = s

        # print('dropped '+str(dropped))
        if o.do_simulation_feedrate:  # smoothing ,but only backward!
            xcoef = shapek.data[len(shapek.data) - 1].co.x / len(shapek.data)
            for a in range(0, 10):
                # print(shapek.data[-1].co)
                nvals = []
                val1 = 0  #
                val2 = 0
                w1 = 0  #
                w2 = 0

                for i, d in enumerate(shapek.data):
                    val = d.co.y

                    if i > 1:
                        d1 = shapek.data[i - 1].co
                        val1 = d1.y
                        if d1.x - d.co.x != 0:
                            w1 = 1 / (abs(d1.x - d.co.x) / xcoef)

                    if i < len(shapek.data) - 1:
                        d2 = shapek.data[i + 1].co
                        val2 = d2.y
                        if d2.x - d.co.x != 0:
                            w2 = 1 / (abs(d2.x - d.co.x) / xcoef)

                    # print(val,val1,val2,w1,w2)

                    val = (val + val1 * w1 + val2 * w2) / (1.0 + w1 + w2)
                    nvals.append(val)
                for i, d in enumerate(shapek.data):
                    d.co.y = nvals[i]

            # apply mapping - convert the values to actual feedrates.
            total_load = 0
            max_load = 0
            for i, d in enumerate(shapek.data):
                total_load += d.co.y
                max_load = max(max_load, d.co.y)
            normal_load = total_load / len(shapek.data)

            thres = 0.5

            scale_graph = 0.05  # warning this has to be same as in export in utils!!!!

            totverts = len(shapek.data)
            for i, d in enumerate(shapek.data):
                if d.co.y > normal_load:
                    d.co.z = scale_graph * max(0.3, normal_load / d.co.y)
                else:
                    d.co.z = scale_graph * 1
                if i < totverts - 1:
                    m.edges[i].crease = d.co.y / (normal_load * 4)

    si = si[borderwidth:-borderwidth, borderwidth:-borderwidth]
    si += -minz

    await progress_async("Simulated:", time.time() - start_time, "s")
    return si


def simCutterSpot(xs, ys, z, cutterArray, si, getvolume=False):
    """Simulates a Cutter Cutting Into Stock, Taking Away the Volume,
    and Optionally Returning the Volume that Has Been Milled. This Is Now Used for Feedrate Tweaking.
    """
    m = int(cutterArray.shape[0] / 2)
    size = cutterArray.shape[0]
    # whole cutter in image there
    if xs > m and xs < si.shape[0] - m and ys > m and ys < si.shape[1] - m:
        if getvolume:
            volarray = si[xs - m : xs - m + size, ys - m : ys - m + size].copy()
        si[xs - m : xs - m + size, ys - m : ys - m + size] = np.minimum(
            si[xs - m : xs - m + size, ys - m : ys - m + size], cutterArray + z
        )
        if getvolume:
            volarray = si[xs - m : xs - m + size, ys - m : ys - m + size] - volarray
            vsum = abs(volarray.sum())
            # print(vsum)
            return vsum

    elif xs > -m and xs < si.shape[0] + m and ys > -m and ys < si.shape[1] + m:
        # part of cutter in image, for extra large cutters

        startx = max(0, xs - m)
        starty = max(0, ys - m)
        endx = min(si.shape[0], xs - m + size)
        endy = min(si.shape[0], ys - m + size)
        castartx = max(0, m - xs)
        castarty = max(0, m - ys)
        caendx = min(size, si.shape[0] - xs + m)
        caendy = min(size, si.shape[1] - ys + m)

        if getvolume:
            volarray = si[startx:endx, starty:endy].copy()
        si[startx:endx, starty:endy] = np.minimum(
            si[startx:endx, starty:endy],
            cutterArray[castartx:caendx, castarty:caendy] + z,
        )
        if getvolume:
            volarray = si[startx:endx, starty:endy] - volarray
            vsum = abs(volarray.sum())
            # print(vsum)
            return vsum
    return 0
