"""Fusion add-in entry point. Add this directory in Scripts and Add-Ins."""
from pathlib import Path
import sys
import traceback
import importlib
import adsk.core

FUSION = Path(__file__).resolve().parents[1]
if str(FUSION) not in sys.path:
    sys.path.insert(0,str(FUSION))
import native_command


def run(context):
    try:
        native_command.stop()
        importlib.reload(native_command)
        native_command.start()
        # Fusion retains add-ins through their manifest; autoTerminate is for scripts.
    except Exception:
        native_command.record_error()
        adsk.core.Application.get().userInterface.messageBox(traceback.format_exc(),"AirDesk add-in")


def stop(context):
    native_command.stop()
