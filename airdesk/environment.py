import importlib.metadata
import os
import platform
import shutil
from pathlib import Path
from .common import ROOT, RESULTS, stamp, write_json


def locate_ltspice():
    candidates = [os.environ.get("AIRDESK_LTSPICE", ""), shutil.which("LTspice.exe") or "",
                  str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/ADI/LTspice/LTspice.exe"),
                  "C:/Program Files/ADI/LTspice/LTspice.exe"]
    for path in candidates:
        if path and Path(path).is_file():
            return str(Path(path).resolve())
    raise FileNotFoundError("LTspice not found. Install it or set AIRDESK_LTSPICE to LTspice.exe.")


def report(cfg):
    packages = {}
    for name in ("numpy", "scipy", "matplotlib", "pillow", "pytest", "pyfemm", "pywin32"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "NOT INSTALLED"
    try:
        ltspice = locate_ltspice()
    except FileNotFoundError as exc:
        ltspice = str(exc)
    fusion_root = Path(os.environ.get("LOCALAPPDATA", "")) / "Autodesk/webdeploy/production"
    data = stamp(cfg, "environment_inventory") | {"python": platform.python_version(),
        "platform": platform.platform(), "packages": packages, "ltspice": ltspice,
        "femm_executable_present": Path("C:/femm42/bin/femm.exe").is_file(),
        "fusion_executables": [str(p) for p in fusion_root.glob("*/Fusion360.exe")],
        "note": "Executable presence is not a successful solver or Fusion API run."}
    write_json(RESULTS / "environment.json", data)
    return data
