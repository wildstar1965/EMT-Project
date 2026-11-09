import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cadlib as c


def tx_position(design):
    box = c.find(design,"Tx_Winding").bRepBodies.item(0).boundingBox
    return tuple((getattr(box.minPoint,k)+getattr(box.maxPoint,k))*5 for k in ("x","y","z"))


def slider(root, moving, fixed, name, direction, travel):
    existing = next((j for j in root.asBuiltJoints if j.name == name), None)
    if existing:
        return existing
    geometry = c.joint_geometry(root,(0,0,0),name)
    data = root.asBuiltJoints.createInput(moving,fixed,geometry)
    data.setAsSliderJointMotion(direction)
    joint = root.asBuiltJoints.add(data)
    joint.name = name
    limits = joint.jointMotion.slideLimits
    limits.minimumValue = -travel/20
    limits.maximumValue = travel/20
    limits.isMinimumValueEnabled = limits.isMaximumValueEnabled = True
    return joint


def motor(root, moving, fixed, name, direction, origin, linear, advance):
    existing = next((j for j in root.asBuiltJoints if j.name == name), None)
    if existing:
        return existing
    geometry = c.joint_geometry(root,origin,name)
    data = root.asBuiltJoints.createInput(moving,fixed,geometry)
    data.setAsRevoluteJointMotion(direction)
    joint = root.asBuiltJoints.add(data)
    joint.name = name
    link = root.motionLinks.createInput(linear,joint)
    link.motionOne = c.fusion.JointMotionTypes.SliderJointSlideMotionType
    link.motionTwo = c.fusion.JointMotionTypes.RevoluteJointRotateMotionType
    link.valueOne = c.core.ValueInput.createByString(f"{advance} mm")
    link.valueTwo = c.core.ValueInput.createByString("360 deg")
    root.motionLinks.add(link).name = name+"_BeltRatio"
    return joint


def moving_interferences(design):
    entities = c.core.ObjectCollection.create()
    for occ in design.rootComponent.allOccurrences:
        if any(word in occ.fullPathName for word in ("Phone", "Belt", "CableEnvelope")):
            continue
        for body in occ.bRepBodies:
            entities.add(body)
    data = design.createInterferenceInput(entities)
    data.areCoincidentFacesIncluded = False
    results = design.analyzeInterference(data)
    found = []
    for result in results:
        one, two = result.entityOne, result.entityTwo
        first = one.assemblyContext.fullPathName if one.assemblyContext else one.parentComponent.name
        second = two.assemblyContext.fullPathName if two.assemblyContext else two.parentComponent.name
        group1, group2 = first.split("+")[0], second.split("+")[0]
        if group1 == group2:
            continue  # Fixed subassembly joints/fastener envelopes are not travel interference.
        volume = result.interferenceBody.physicalProperties.volume
        if volume > 1e-6:
            found.append({"one": first, "two": second, "volume_mm3": volume*1000})
    return found


def run(context):
    app, design, cfg = c.active()
    c.refresh_appearances(design)
    c.write_json(c.RESULTS/"fusion"/"appearance_catalog.json", {lib.name:[a.name for a in lib.appearances if any(k in a.name.lower() for k in ("plastic","paint","glass","acrylic"))][:60] for lib in app.materialLibraries})
    root, m = design.rootComponent, cfg["mechanical"]
    frame, bridge, carriage = (c.find(design,n) for n in ("Frame","Bridge","Carriage"))
    jy = slider(root,bridge,frame,"Y_Position",c.fusion.JointDirections.YAxisJointDirection,m["y_travel_mm"])
    jx = slider(root,carriage,bridge,"X_Position",c.fusion.JointDirections.XAxisJointDirection,m["x_travel_mm"])
    jx.jointMotion.slideValue = jy.jointMotion.slideValue = 0
    jy.jointMotion.slideValue = 1
    c.adsk_events()
    sy = 1 if tx_position(design)[1] > 0 else -1
    jy.jointMotion.slideValue = 0
    jx.jointMotion.slideValue = 1
    c.adsk_events()
    sx = 1 if tx_position(design)[0] > 0 else -1
    jx.jointMotion.slideValue = 0
    root.attributes.add("AirDesk","x_sign",str(sx))
    root.attributes.add("AirDesk","y_sign",str(sy))
    advance = m["belt_pitch_mm"]*m["pulley_teeth"]
    motor(root,c.find(design,"X_DriveRotor"),bridge,"X_Motor",c.fusion.JointDirections.ZAxisJointDirection,
          (-275,20,-33),jx,advance)
    motor(root,c.find(design,"Y_DriveRotor"),frame,"Y_Motor",c.fusion.JointDirections.XAxisJointDirection,
          (0,-155,-110),jy,advance)
    samples, collisions = [], []
    for x in (-m["x_travel_mm"]/2,0,m["x_travel_mm"]/2):
        for y in (-m["y_travel_mm"]/2,0,m["y_travel_mm"]/2):
            jy.jointMotion.slideValue = y/(10*sy)
            jx.jointMotion.slideValue = x/(10*sx)
            c.adsk_events()
            measured = tx_position(design)
            error = math.hypot(measured[0]-x,measured[1]-y)
            samples.append({"command_mm":[x,y],"measured_tx_mm":measured,"error_mm":error})
            if error > .01:
                raise RuntimeError(f"Joint transform mismatch: {samples[-1]}")
            for hit in moving_interferences(design):
                collisions.append({"at_mm":[x,y],**hit})
    jy.jointMotion.slideValue = jx.jointMotion.slideValue = 0
    report = {"samples":samples,"moving_interferences":collisions,"passed":not collisions,
              "exclusions":["Fixed subassembly mating volumes", "Belt/clamp contact envelopes", "Cable-chain clearance envelopes", "Phone internals"]}
    c.write_json(c.RESULTS/"fusion"/"motion_validation.json",report)
    if collisions:
        raise RuntimeError(f"{len(collisions)} moving interferences found; inspect motion_validation.json")
    c.save_stage(design,"03_assembly",{"motion_validation":report,"motor_links":2,"actuated_gantry_dof":2})
