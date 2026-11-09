import csv
import json
import math
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cadlib as c
from airdesk.common import artifacts_intact
from airdesk.evidence import VerifiedPower


def centre(design,name):
    box=c.find(design,name).bRepBodies.item(0).boundingBox
    return tuple((getattr(box.minPoint,k)+getattr(box.maxPoint,k))*5 for k in ("x","y","z"))


def run(context):
    app,design,cfg=c.active()
    metadata=json.loads((c.RESULTS/"demo"/"trajectory.json").read_text(encoding="utf-8"))
    if metadata["config_sha256"]!=c.config_hash(cfg):
        raise RuntimeError("Trajectory configuration is stale")
    inputs=[metadata["trajectory"]]
    if metadata["operating_point"]: inputs.append(metadata["operating_point"])
    if not artifacts_intact(inputs):
        raise RuntimeError("Trajectory or electrical evidence changed; regenerate the demo")
    power=VerifiedPower(cfg)
    root=design.rootComponent
    for joint in root.asBuiltJoints:
        joint.isLightBulbOn=False
    jx=root.asBuiltJoints.itemByName("X_Position")
    jy=root.asBuiltJoints.itemByName("Y_Position")
    sx=float(root.attributes.itemByName("AirDesk","x_sign").value)
    sy=float(root.attributes.itemByName("AirDesk","y_sign").value)
    phone=c.find(design,"Phone")
    phone.isGroundToParent=True
    with (c.RESULTS/"demo"/"trajectory.csv").open(encoding="utf-8",newline="") as stream:
        rows=list(csv.DictReader(stream))
    folder=c.RESULTS/"fusion"/"replay_frames"
    folder.mkdir(parents=True,exist_ok=True)
    camera=app.activeViewport.camera
    camera.isSmoothTransition=False
    camera.target=c.point(0,0,-60)
    camera.eye=c.point(800,-1000,1050)
    camera.upVector=c.core.Vector3D.create(0,0,1)
    camera.isFitView=True
    app.activeViewport.camera=camera
    observations=[]
    previous=None
    previous_pose=None
    started=time.monotonic()
    for index,row in enumerate(rows):
        tick=time.monotonic()
        x,y=float(row["x_mm"]),float(row["y_mm"])
        present=row["phone_present"]=="True"
        phone.isLightBulbOn=present
        pose_key=(row["phone_x_mm"],row["phone_y_mm"],row["phone_yaw_deg"])
        if present and pose_key!=previous_pose:
            transform=c.core.Matrix3D.create()
            transform.setToRotation(math.radians(float(row["phone_yaw_deg"])),c.core.Vector3D.create(0,0,1),c.point(0,0,0))
            transform.translation=c.core.Vector3D.create(float(row["phone_x_mm"])/10,float(row["phone_y_mm"])/10,0)
            # Fusion requires rolling to the occurrence feature to edit its
            # persistent placement. Restore the timeline before joint driving.
            phone.timelineObject.rollTo(False)
            try:
                phone.initialTransform=transform
            finally:
                design.timeline.moveToEnd()
            phone=c.find(design,"Phone")
            jx=root.asBuiltJoints.itemByName("X_Position")
            jy=root.asBuiltJoints.itemByName("Y_Position")
            previous_pose=pose_key
        state=row["state"]
        if state!=previous:
            c.paint(design,c.find(design,"Tx_Winding").component,"Charging" if state=="CHARGING" else "Copper",
                    (45,200,125) if state=="CHARGING" else (205,115,48))
            app.log(f"AirDesk {row['time_s']} s: {state}, simulated load power {row['power_w']} W")
            previous=state
        # Appearance/phone edits can regenerate Fusion and reset driven positions.
        # Apply joint drives after those edits, then measure actual world geometry.
        jy.jointMotion.slideValue=y/(10*sy)
        jx.jointMotion.slideValue=x/(10*sx)
        c.adsk_events()
        tx=centre(design,"Tx_Winding")
        error=math.hypot(tx[0]-x,tx[1]-y)
        if error>.01:
            raise RuntimeError(f"Fusion replay transform mismatch: {error} mm, command {(x,y)}, measured {tx}")
        if state=="CHARGING":
            rx=centre(design,"Rx_Winding")
            if (not power.available or not present or math.hypot(tx[0]-rx[0],tx[1]-rx[1])>2
                or abs(rx[2]-tx[2]-9.1)>1e-6 or abs(float(row["power_w"])-power.watts)>1e-8):
                raise RuntimeError(f"Charging frame does not match CAD alignment/evidence: tx={tx}, rx={rx}, verified={power.available}, power={row['power_w']}")
        if index%4==0 or index==len(rows)-1:
            filename=f"frame_{index:04d}.png"
            app.activeViewport.saveAsImageFile(str(folder/filename),960,600)
            observations.append({"frame":filename,"time_s":float(row["time_s"]),"state":state,
                                 "power_w":float(row["power_w"]),"error_mm":error})
        time.sleep(max(0,.05-(time.monotonic()-tick)))
    c.write_json(c.RESULTS/"fusion"/"replay.json",{"passed":True,"config_sha256":c.config_hash(cfg),
        "trajectory_samples":len(rows),"wall_duration_s":time.monotonic()-started,"frames":observations,
        "maximum_position_error_mm":max(r["error_mm"] for r in observations)})
    c.save_stage(design,"04_final",{"replay_passed":True})
