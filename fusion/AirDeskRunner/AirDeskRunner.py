"""Stage dispatcher only. Each geometry/motion stage remains a separate script."""
from pathlib import Path
import json
import runpy
import traceback
import sys
import adsk.core

ROOT = Path(__file__).resolve().parents[2]
STAGES = {"frame": "01_Frame/01_Frame.py", "gantry": "02_Gantry/02_Gantry.py",
          "joints": "03_Joints/03_Joints.py", "replay": "04_Replay/04_Replay.py"}


def run(context):
    stage = (ROOT / "config" / "fusion_stage.txt").read_text(encoding="utf-8").strip()
    output = ROOT / "results" / "fusion"
    output.mkdir(parents=True, exist_ok=True)
    (output / "last_run.json").write_text(json.dumps({"stage": stage, "status": "running"}), encoding="utf-8")
    try:
        path = ROOT / "fusion" / STAGES[stage]
        sys.modules.pop("cadlib", None)
        runpy.run_path(str(path))["run"](context)
        (ROOT / "results" / "fusion" / "last_error.json").unlink(missing_ok=True)
        (output / "last_run.json").write_text(json.dumps({"stage": stage, "status": "passed"}), encoding="utf-8")
    except Exception:
        error = {"stage": stage, "passed": False, "error": traceback.format_exc()}
        output = ROOT / "results" / "fusion"
        output.mkdir(parents=True, exist_ok=True)
        (output / "last_error.json").write_text(json.dumps(error, indent=2), encoding="utf-8")
        (output / "last_run.json").write_text(json.dumps({"stage": stage, "status": "failed"}), encoding="utf-8")
        adsk.core.Application.get().log(error["error"])
