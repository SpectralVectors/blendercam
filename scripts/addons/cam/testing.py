"""BlenderCAM 'testing.py' © 2012 Vilem Novak

Functions for automated testing.
"""

import bpy

from .gcodepath import getPath
from .simple import activate


def addTestCurve(loc):
    bpy.ops.curve.primitive_bezier_circle_add(
        radius=0.05, align="WORLD", enter_editmode=False, location=loc
    )
    bpy.ops.object.editmode_toggle()
    bpy.ops.curve.duplicate()
    bpy.ops.transform.resize(
        value=(0.5, 0.5, 0.5),
        constraint_axis=(False, False, False),
        orient_type="GLOBAL",
        mirror=False,
        use_proportional_edit=False,
        proportional_edit_falloff="SMOOTH",
        proportional_size=1,
    )
    bpy.ops.curve.duplicate()
    bpy.ops.transform.resize(
        value=(0.5, 0.5, 0.5),
        constraint_axis=(False, False, False),
        orient_type="GLOBAL",
        mirror=False,
        use_proportional_edit=False,
        proportional_edit_falloff="SMOOTH",
        proportional_size=1,
    )
    bpy.ops.object.editmode_toggle()


def addTestMesh(loc):
    bpy.ops.mesh.primitive_monkey_add(
        radius=0.01, align="WORLD", enter_editmode=False, location=loc
    )
    bpy.ops.transform.rotate(
        value=-1.5708,
        axis=(1, 0, 0),
        constraint_axis=(True, False, False),
        orient_type="GLOBAL",
    )
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.primitive_plane_add(
        radius=1, align="WORLD", enter_editmode=False, location=loc
    )
    bpy.ops.transform.resize(
        value=(0.01, 0.01, 0.01),
        constraint_axis=(False, False, False),
        orient_type="GLOBAL",
    )
    bpy.ops.transform.translate(
        value=(-0.01, 0, 0), constraint_axis=(True, False, False), orient_type="GLOBAL"
    )

    bpy.ops.object.editmode_toggle()


def deleteFirstVert(ob):
    activate(ob)
    bpy.ops.object.editmode_toggle()

    bpy.ops.mesh.select_all(action="DESELECT")

    bpy.ops.object.editmode_toggle()
    for i, v in enumerate(ob.data.vertices):
        v.select = False
        if i == 0:
            v.select = True
    ob.data.update()

    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.delete(type="VERT")
    bpy.ops.object.editmode_toggle()


def testCalc(o):
    bpy.ops.object.calculate_cam_path()
    deleteFirstVert(bpy.data.objects[o.name])


def testCutout(pos):
    addTestCurve((pos[0], pos[1], -0.05))
    bpy.ops.scene.cam_operation_add()
    o = bpy.context.scene.cam_operations[-1]
    o.strategy = "CUTOUT"
    testCalc(o)


def testPocket(pos):
    addTestCurve((pos[0], pos[1], -0.01))
    bpy.ops.scene.cam_operation_add()
    o = bpy.context.scene.cam_operations[-1]
    o.strategy = "POCKET"
    o.movement.helix_enter = True
    o.movement.retract_tangential = True
    testCalc(o)


def testParallel(pos):
    addTestMesh((pos[0], pos[1], -0.02))
    bpy.ops.scene.cam_operation_add()
    o = bpy.context.scene.cam_operations[-1]
    o.ambient_behaviour = "AROUND"
    o.material.radius_around_model = 0.01
    bpy.ops.object.calculate_cam_path()


def testWaterline(pos):
    addTestMesh((pos[0], pos[1], -0.02))
    bpy.ops.scene.cam_operation_add()
    o = bpy.context.scene.cam_operations[-1]
    o.strategy = "WATERLINE"
    o.optimisation.pixsize = 0.0002
    # o.ambient_behaviour='AROUND'
    # o.material_radius_around_model=0.01

    testCalc(o)


# bpy.ops.object.cam_simulate()


def testSimulation():
    pass


def cleanUp():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    while len(bpy.context.scene.cam_operations):
        bpy.ops.scene.cam_operation_remove()


def testOperation(i):
    s = bpy.context.scene
    o = s.cam_operations[i]
    report = ""
    report += "testing operation " + o.name + "\n"

    getPath(bpy.context, o)

    newresult = bpy.data.objects[o.path_object_name]
    origname = "test_cam_path_" + o.name
    if origname not in s.objects:
        report += "Operation Test Has Nothing to Compare with, Making the New Result as Comparable Result.\n\n"
        newresult.name = origname
    else:
        testresult = bpy.data.objects[origname]
        m1 = testresult.data
        m2 = newresult.data
        test_ok = True
        if len(m1.vertices) != len(m2.vertices):
            report += "Vertex Counts Don't Match\n\n"
            test_ok = False
        else:
            different_co_count = 0
            for i in range(0, len(m1.vertices)):
                v1 = m1.vertices[i]
                v2 = m2.vertices[i]
                if v1.co != v2.co:
                    different_co_count += 1
            if different_co_count > 0:
                report += "Vertex Position Is Different on %i Vertices \n\n" % (
                    different_co_count
                )
                test_ok = False
        if test_ok:
            report += "Test Ok\n\n"
        else:
            report += "Test Result Is Different\n \n "
    print(report)
    return report


def testAll():
    s = bpy.context.scene
    report = ""
    for i in range(0, len(s.cam_operations)):
        report += testOperation(i)
    print(report)


tests = [
    testCutout,
    testParallel,
    testWaterline,
    testPocket,
]

cleanUp()

# deleteFirstVert(bpy.context.active_object)
for i, t in enumerate(tests):
    p = i * 0.2
    t((p, 0, 0))
# 	cleanUp()


# cleanUp()
