"""Run INSIDE Fusion. Original geometry/pose is preserved; no replay files overwritten."""
import importlib
from pathlib import Path
import sys
import time
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cadlib as c
import native_motion as motion
from airdesk.motion import PhonePose


def run(context):
    importlib.reload(motion)
    output=motion.OUTPUT
    output.mkdir(parents=True,exist_ok=True)
    report={"passed":False,"status":"running","placements":[],"rejections":[]}
    c.write_json(output/"selftest.json",report)
    saved=None
    try:
        app,design,cfg=c.active()
        before=motion.topology(design)
        saved=motion.capture(design)
        # A local backup is an export of the existing assembly, never a rebuild.
        backup=output/f"before_native_{time.time_ns()}.f3d"
        if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(str(backup))):
            raise RuntimeError("Could not export the pre-test assembly backup")
        report["backup"]=str(backup.relative_to(c.ROOT))
        report["fusion_version"]=app.version
        report["topology_before"]=before
        for x,y,yaw in ((0,0,0),(-200,-120,0),(200,-120,90),(200,120,0),(-200,120,90),(30,-20,35)):
            result=motion.place(design,cfg,PhonePose(x,y,yaw),animate=False)
            if result["state"]!="CHARGING" or result["alignment_error_mm"]>.01:
                raise RuntimeError(f"Nominal placement check failed: {result['reason']}")
            report["placements"].append({k:result[k] for k in ("phone_pose_mm_deg","measured_tx_mm","measured_rx_mm","state","power_w","alignment_error_mm")})
        stable=motion.capture(design)
        for pose in (PhonePose(201,0),PhonePose(0,121),PhonePose(290,190)):
            try: motion.place(design,cfg,pose,animate=False)
            except ValueError as exc:
                report["rejections"].append(str(exc))
            else: raise RuntimeError("Invalid placement was accepted")
            current=motion.capture(design)
            if not current["phone_transform"].isEqualTo(stable["phone_transform"]) or current["slides"]!=stable["slides"]:
                raise RuntimeError("Rejected placement modified the assembly")
        missing=motion.place(design,cfg,PhonePose(0,0),animate=False,evidence_path=output/"intentionally_absent_evidence.json")
        if missing["state"]!="UNVERIFIED" or missing["power_w"]!=0:
            raise RuntimeError("Missing evidence enabled charging")
        report["missing_evidence_rejected"]=True
        motion.restore(design,saved)
        restored=motion.capture(design)
        report["original_pose_restored"]=(restored["phone_transform"].isEqualTo(saved["phone_transform"])
                                           and restored["slides"]==saved["slides"])
        report["topology_preserved"]=motion.topology(design)==before
        if not report["original_pose_restored"] or not report["topology_preserved"]:
            raise RuntimeError("Original assembly was not restored")
        report.update(passed=True,status="passed")
        app.activeViewport.saveAsImageFile(str(output/"selftest_restored.png"),1600,1000)
    except Exception:
        report.update(status="failed",error=traceback.format_exc())
        if saved:
            try: motion.restore(design,saved)
            except Exception: report["restore_error"]=traceback.format_exc()
    c.write_json(output/"selftest.json",report)
    c.core.Application.get().log("AirDesk native self-test: "+report["status"])
