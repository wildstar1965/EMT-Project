"""Drive the existing assembly only. Never builds components or alters constraints."""
import math
import time
import cadlib as c
from airdesk.common import nominal_gap, stamp, artifact
from airdesk.evidence import VerifiedPower
from airdesk.motion import PhonePose, Move
from airdesk.native_tracking import checked_target, charging_check

OUTPUT = c.RESULTS / "fusion" / "native"


def centre(design, name):
    bounds = c.find(design, name).bRepBodies.item(0).boundingBox
    return tuple((getattr(bounds.minPoint,k)+getattr(bounds.maxPoint,k))*5 for k in ("x","y","z"))


def joint_pair(design):
    root = design.rootComponent
    joints = [root.asBuiltJoints.itemByName(name) for name in ("X_Position","Y_Position")]
    if any(not j or j.isSuppressed or not c.fusion.SliderJointMotion.cast(j.jointMotion) for j in joints):
        raise RuntimeError("AirDesk requires its existing, unsuppressed X_Position and Y_Position sliders")
    signs = [float(root.attributes.itemByName("AirDesk",key).value) for key in ("x_sign","y_sign")]
    if any(s not in (-1,1) for s in signs):
        raise RuntimeError("Invalid AirDesk joint direction calibration")
    return joints, signs


def actual_limits(design):
    joints, signs = joint_pair(design)
    result=[]
    for joint, sign in zip(joints,signs):
        limit=joint.jointMotion.slideLimits
        if not limit.isMinimumValueEnabled or not limit.isMaximumValueEnabled:
            raise RuntimeError("Both existing slider travel limits must remain enabled")
        result.append(sorted((limit.minimumValue*10*sign,limit.maximumValue*10*sign)))
    return result


def topology(design):
    root=design.rootComponent
    return {"occurrences": sorted(o.fullPathName for o in root.allOccurrences),
            "bodies": sorted((o.fullPathName,b.name,round(b.physicalProperties.volume,8))
                             for o in root.allOccurrences for b in o.bRepBodies),
            "joints": sorted((j.name,j.occurrenceOne.fullPathName,j.occurrenceTwo.fullPathName,
                              j.jointMotion.jointType,j.isSuppressed) for j in root.asBuiltJoints),
            "motion_links": sorted((link.name,link.isSuppressed) for link in root.motionLinks),
            "slider_limits_mm": actual_limits(design)}


def current_pose(design):
    phone=c.find(design,"Phone")
    matrix=phone.transform2
    if abs(matrix.translation.z) > 1e-6 or abs(matrix.getCell(2,2)-1)>1e-6:
        raise RuntimeError("Phone must be face up on the original tabletop plane")
    return PhonePose(matrix.translation.x*10,matrix.translation.y*10,
                     math.degrees(math.atan2(matrix.getCell(1,0),matrix.getCell(0,0))))


def capture(design):
    phone=c.find(design,"Phone")
    joints,_=joint_pair(design)
    return {"phone_transform":phone.initialTransform.copy(),"phone_visible":phone.isLightBulbOn,
            "phone_grounded":phone.isGroundToParent,
            "slides":[j.jointMotion.slideValue for j in joints]}


def set_phone(design, transform):
    phone=c.find(design,"Phone")
    # Same persistent placement operation verified by the original replay stage.
    phone.timelineObject.rollTo(False)
    try:
        phone.initialTransform=transform
    finally:
        design.timeline.moveToEnd()


def restore(design, saved):
    set_phone(design,saved["phone_transform"])
    phone=c.find(design,"Phone")
    phone.isLightBulbOn=saved["phone_visible"]
    phone.isGroundToParent=saved["phone_grounded"]
    joints,_=joint_pair(design)
    for j,value in zip(joints,saved["slides"]):
        j.jointMotion.slideValue=value
    c.adsk_events()


def drive(design, target):
    joints,signs=joint_pair(design)
    # Y carries the X assembly. Reacquire after every timeline edit.
    for index in (1,0):
        joints[index].jointMotion.slideValue=target[index]/(10*signs[index])


def place(design, cfg, pose, *, animate=True, publish=None, evidence_path=None):
    app=c.core.Application.get()
    if app.activeProduct != design:
        # API wrappers need not be the same Python object; compare the root token.
        active=c.fusion.Design.cast(app.activeProduct)
        if not active or active.rootComponent.entityToken != design.rootComponent.entityToken:
            raise RuntimeError("The target AirDesk document is not active")
    checked_target(cfg,pose,actual_limits(design))
    if not c.find(design,"Phone").isGroundToParent:
        raise RuntimeError("Phone is no longer grounded. Restore its original AirDesk grounding before placement")
    current_pose(design)
    saved=capture(design)
    before=topology(design)
    start=centre(design,"Tx_Winding")[:2]
    target=checked_target(cfg,pose,actual_limits(design))
    samples=[]

    def status(state,reason,**extra):
        data={"state":state,"reason":reason,"power_w":0.,**extra}
        if publish: publish(data)

    try:
        status("POSITIONING","Transmitter disabled during phone placement and gantry motion")
        transform=c.core.Matrix3D.create()
        transform.setToRotation(math.radians(pose.yaw_deg),c.core.Vector3D.create(0,0,1),c.point(0,0,0))
        transform.translation=c.core.Vector3D.create(pose.x_mm/10,pose.y_mm/10,0)
        set_phone(design,transform)
        c.find(design,"Phone").isLightBulbOn=True
        drive(design,start)
        c.adsk_events()
        move=Move(start,target,cfg["mechanical"]["speed_mm_s"],cfg["mechanical"]["accel_mm_s2"])
        ticks=max(1,math.ceil(move.duration/.05)) if animate else 1
        for index in range(1,ticks+1):
            tick=time.monotonic()
            desired,_=move.sample(move.duration*index/ticks)
            drive(design,desired)
            c.adsk_events()
            measured=centre(design,"Tx_Winding")
            error=math.dist(desired,measured[:2])
            if error>.01:
                raise RuntimeError(f"Existing joint drive differs from actual coil position by {error:.3f} mm")
            samples.append({"trajectory_time_s":move.duration*index/ticks,"command_mm":desired,
                            "measured_tx_mm":measured,"error_mm":error})
            if animate: time.sleep(max(0,move.duration/ticks-(time.monotonic()-tick)))
        status("SETTLING","Waiting for a stationary placement",target_mm=target)
        settled_at=time.monotonic()
        while time.monotonic()-settled_at < cfg["mechanical"]["settle_s"]:
            c.adsk_events()
            time.sleep(.02)
        power=VerifiedPower(cfg,evidence_path)  # Revalidate hashes on every placement.
        tx,rx=centre(design,"Tx_Winding"),centre(design,"Rx_Winding")
        if math.dist(rx[:2],target)>.01:
            raise RuntimeError("Actual receiver centre differs from the rotated phone receiver offset")
        result=charging_check(cfg,power,tx,rx,stationary=True,
                              stable_seconds=time.monotonic()-settled_at,
                              present=c.find(design,"Phone").isVisible)
        if topology(design)!=before:
            raise RuntimeError("Assembly topology or existing joint constraints changed unexpectedly")
        data=stamp(cfg,"fusion_native_placement") | result | {
            "executed":True,"fusion_version":app.version,
            "phone_pose_mm_deg":[pose.x_mm,pose.y_mm,pose.yaw_deg],"target_mm":target,
            "measured_tx_mm":tx,"measured_rx_mm":rx,"topology_preserved":True,
            "samples":samples,"source_model":power.model,
            "operating_point":artifact(evidence_path or c.RESULTS/"operating_point.json") if power.available else None}
        c.write_json(OUTPUT/"last_placement.json",data)
        with (OUTPUT/"placements.jsonl").open("a",encoding="utf-8") as stream:
            import json
            stream.write(json.dumps({k:v for k,v in data.items() if k!="samples"})+"\n")
        if publish: publish(data)
        return data
    except Exception:
        restore(design,saved)
        status("UNVERIFIED","Placement failed; previous phone and joint positions restored")
        raise
