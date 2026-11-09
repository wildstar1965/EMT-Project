"""Run inside Fusion: Utilities > Scripts and Add-Ins > add this folder."""
import json
import traceback
from pathlib import Path
import adsk.core
import adsk.fusion

ROOT = Path(__file__).resolve().parents[2]


def run(context):
    app = adsk.core.Application.get()
    output = ROOT / "results" / "fusion"
    output.mkdir(parents=True, exist_ok=True)
    result = {"stage": "smoke", "passed": False, "fusion_version": app.version}
    try:
        document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        document.name = "AirDesk_API_Smoke"
        design = adsk.fusion.Design.cast(app.activeProduct)
        root = design.rootComponent
        sketch = root.sketches.add(root.xYConstructionPlane)
        sketch.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0), adsk.core.Point3D.create(1, 1, 0))
        root.features.extrudeFeatures.addSimple(sketch.profiles.item(0),
            adsk.core.ValueInput.createByString("10 mm"), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        body = root.bRepBodies.item(0)
        box = body.boundingBox
        size = [10 * (getattr(box.maxPoint, axis) - getattr(box.minPoint, axis)) for axis in ("x", "y", "z")]
        result.update(size_mm=size, volume_cm3=body.physicalProperties.volume)
        assert all(abs(v - 10) < 1e-6 for v in size), size
        assert abs(body.physicalProperties.volume - 1) < 1e-6
        manager = design.exportManager
        assert manager.execute(manager.createFusionArchiveExportOptions(str(output / "smoke.f3d")))
        app.activeViewport.fit()
        app.activeViewport.saveAsImageFile(str(output / "smoke.png"), 1200, 800)
        result["passed"] = True
    except Exception:
        result["error"] = traceback.format_exc()
    (output / "smoke.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    app.userInterface.messageBox("AirDesk API smoke test " + ("PASSED" if result["passed"] else "FAILED")
                                 + "\nEvidence: " + str(output / "smoke.json"))
