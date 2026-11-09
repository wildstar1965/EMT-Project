"""Small official-Fusion-API building blocks. All public dimensions are mm."""
import json
import math
from pathlib import Path
import sys
import adsk.core as core
import adsk.fusion as fusion

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from airdesk.common import load_config, config_hash, write_json, RESULTS


def point(x, y, z):
    return core.Point3D.create(x / 10, y / 10, z / 10)


def component(parent, name, fixed=True):
    occurrence = parent.occurrences.addNewComponent(core.Matrix3D.create())
    occurrence.component.name = name
    occurrence.isGroundToParent = fixed
    return occurrence


def box(comp, name, xyz, size, cut=False):
    x, y, z = xyz
    dx, dy, dz = size
    if min(size) <= 0:
        raise ValueError(f"Non-positive dimensions: {name}")
    plane_input = comp.constructionPlanes.createInput()
    plane_input.setByOffset(comp.xYConstructionPlane, core.ValueInput.createByReal(z / 10))
    plane = comp.constructionPlanes.add(plane_input)
    sketch = comp.sketches.add(plane)
    sketch.name = name + " footprint"
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point(x, y, 0), point(x + dx, y + dy, 0))
    operation = fusion.FeatureOperations.CutFeatureOperation if cut else fusion.FeatureOperations.NewBodyFeatureOperation
    feature = comp.features.extrudeFeatures.addSimple(sketch.profiles.item(0), core.ValueInput.createByReal(dz / 10), operation)
    feature.name = name
    sketch.isLightBulbOn = False
    plane.isLightBulbOn = False
    if not cut:
        body = feature.bodies.item(0)
        body.name = name
        return body


def cylinder(comp, name, start, end, radius, inner=0):
    manager = fusion.TemporaryBRepManager.get()
    body = manager.createCylinderOrCone(point(*start), radius / 10, point(*end), radius / 10)
    if inner:
        hole = manager.createCylinderOrCone(point(*start), inner / 10, point(*end), inner / 10)
        if not manager.booleanOperation(body, hole, fusion.BooleanTypes.DifferenceBooleanType):
            raise RuntimeError("Failed annulus subtraction")
    feature = comp.features.baseFeatures.add()
    feature.name = name
    feature.startEdit()
    result = comp.bRepBodies.add(body, feature)
    feature.finishEdit()
    result.name = name
    return result


def paint(design, comp, name, color):
    name = "Visual2 " + name
    appearance = next((a for a in design.appearances if a.name == name), None)
    if not appearance:
        app = core.Application.get()
        for lib in app.materialLibraries:
            if lib.name != "Fusion Appearance Library":
                continue
            try:
                source = lib.appearances.itemByName("Plastic - Matte (Black)")
            except RuntimeError:
                source = None
            if not source and lib.appearances.count:
                source = lib.appearances.item(0)
            if source:
                appearance = design.appearances.addByCopy(source, name)
                for prop in appearance.appearanceProperties:
                    if prop.objectType == core.ColorProperty.classType() and prop.id in ("opaque_albedo","generic_diffuse"):
                        prop.value = core.Color.create(*color, 255)
                break
    if appearance:
        for body in comp.bRepBodies:
            body.appearance = appearance


def part(parent, name, xyz, size, design=None, color=None):
    occ = component(parent, name)
    box(occ.component, name, xyz, size)
    if design and color:
        paint(design, occ.component, "AirDesk " + str(color), color)
    return occ


def active():
    app = core.Application.get()
    design = fusion.Design.cast(app.activeProduct)
    if not design or not design.rootComponent.attributes.itemByName("AirDesk", "config"):
        raise RuntimeError("Open the AirDesk assembly produced by stage 01 first")
    cfg = load_config()
    if design.rootComponent.attributes.itemByName("AirDesk", "config").value != config_hash(cfg):
        raise RuntimeError("Configuration changed; regenerate the assembly from stage 01")
    return app, design, cfg


def find(design, name):
    for occ in design.rootComponent.allOccurrences:
        if occ.component.name == name:
            return occ
    raise KeyError(f"Component not found: {name}")


def save_stage(design, name, extra=None):
    app = core.Application.get()
    output = RESULTS / "fusion"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for occ in design.rootComponent.allOccurrences:
        for body in occ.bRepBodies:
            bounds = body.boundingBox
            rows.append({"component": occ.component.name, "body": body.name,
                "min_mm": [getattr(bounds.minPoint, k) * 10 for k in ("x", "y", "z")],
                "max_mm": [getattr(bounds.maxPoint, k) * 10 for k in ("x", "y", "z")],
                "volume_cm3": body.physicalProperties.volume, "is_solid": body.isSolid})
    if not rows or any(not r["is_solid"] or r["volume_cm3"] <= 0 for r in rows):
        raise RuntimeError("Invalid or empty solid geometry")
    manager = design.exportManager
    if not manager.execute(manager.createFusionArchiveExportOptions(str(output / (name + ".f3d")))):
        raise RuntimeError("Fusion archive export failed")
    if not manager.execute(manager.createSTEPExportOptions(str(output / (name + ".step")), design.rootComponent)):
        raise RuntimeError("STEP export failed")
    camera = app.activeViewport.camera
    camera.isSmoothTransition = False
    camera.cameraType = core.CameraTypes.OrthographicCameraType
    camera.target = point(0,0,-75)
    camera.eye = point(850,-1000,800)
    camera.upVector = core.Vector3D.create(0,0,1)
    camera.isFitView = True
    app.activeViewport.camera = camera
    adsk_events()
    app.activeViewport.saveAsImageFile(str(output / (name + ".png")), 1600, 1000)
    report = {"stage": name, "passed": True, "config_sha256": config_hash(load_config()),
              "fusion_version": app.version, "bodies": rows, "component_count": design.rootComponent.allOccurrences.count}
    if extra:
        report.update(extra)
    write_json(output / (name + ".json"), report)
    app.log(f"AirDesk {name}: {len(rows)} solids; local exports saved to {output}")


def adsk_events():
    import adsk
    adsk.doEvents()
    core.Application.get().activeViewport.refresh()


def joint_geometry(root, origin, name):
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(root.xYConstructionPlane,core.ValueInput.createByReal(origin[2]/10))
    plane = root.constructionPlanes.add(plane_input)
    sketch = root.sketches.add(plane)
    sketch.name = name + " datum"
    vertex = sketch.sketchPoints.add(point(origin[0],origin[1],0))
    plane.isLightBulbOn = sketch.isLightBulbOn = False
    return fusion.JointGeometry.createByPoint(vertex)


def refresh_appearances(design):
    for occ in design.rootComponent.allOccurrences:
        name = occ.component.name
        color = ((205,115,48) if "Winding" in name else (45,48,54) if "Ferrite" in name
                 else (42,140,170) if "Block" in name or "Carrier" in name
                 else (130,145,165) if "Rail" in name else (60,78,95))
        paint(design,occ.component,"AirDesk "+str(color),color)
    lib = next(lib for lib in core.Application.get().materialLibraries if lib.name=="Fusion Appearance Library")
    clear = next((a for a in design.appearances if a.name=="AirDesk clear acrylic"),None)
    if not clear:
        clear = design.appearances.addByCopy(lib.appearances.itemByName("Acrylic (Clear)"),"AirDesk clear acrylic")
    top = find(design,"Tabletop")
    for body in top.component.bRepBodies:
        body.appearance = clear
    top.opacity = .25
