"""Run inside Fusion to restore AirDesk's acceptance screenshot viewing angle."""
from pathlib import Path
import json

import adsk.core
import adsk.fusion


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design or not design.rootComponent.attributes.itemByName("AirDesk", "config"):
        app.userInterface.messageBox("Select your AirDesk_600x400 design tab first.", "AirDesk view")
        return

    viewport = app.activeViewport
    camera = viewport.camera
    # The same Z-up camera used by cadlib.save_stage (Fusion units are cm).
    camera.isSmoothTransition = False
    camera.cameraType = adsk.core.CameraTypes.OrthographicCameraType
    camera.target = adsk.core.Point3D.create(0, 0, -7.5)
    camera.eye = adsk.core.Point3D.create(85, -100, 80)
    camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
    camera.isFitView = True
    viewport.camera = camera
    viewport.refresh()

    output = Path(__file__).resolve().parents[1] / "results" / "fusion" / "restored_view.json"
    output.write_text(json.dumps({
        "document": app.activeDocument.name,
        "eye_cm": list(viewport.camera.eye.asArray()),
        "target_cm": list(viewport.camera.target.asArray()),
        "up_vector": list(viewport.camera.upVector.asArray()),
        "camera_only": True,
    }, indent=2), encoding="utf-8")
    app.log("AirDesk: restored the acceptance viewing angle.")
