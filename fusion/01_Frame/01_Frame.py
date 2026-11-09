import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cadlib as c
from airdesk.evidence import VerifiedPower


def run(context):
    cfg = c.load_config()
    evidence = VerifiedPower(cfg)
    if not evidence.available:
        raise RuntimeError("Detailed CAD gate: " + evidence.reason)
    app = c.core.Application.get()
    document = app.documents.add(c.core.DocumentTypes.FusionDesignDocumentType)
    document.name = "AirDesk_600x400"
    design = c.fusion.Design.cast(app.activeProduct)
    design.designType = c.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    root.attributes.add("AirDesk", "config", c.config_hash(cfg))
    for group in ("table", "mechanical", "phone", "tx", "rx"):
        for key, value in cfg[group].items():
            if key.endswith("_mm"):
                design.userParameters.add(group + "_" + key, c.core.ValueInput.createByString(f"{value} mm"), "mm", "Regenerate from config/design.json after changes")
    frame = c.component(root, "Frame", True)
    fc = frame.component
    t, m = cfg["table"], cfg["mechanical"]
    w, d, h, e = t["width_mm"], t["depth_mm"], t["height_mm"], m["extrusion_mm"]
    for level, z in (("Upper", -t["thickness_mm"]-e), ("Lower", -h)):
        for side, y in (("Front", -d/2), ("Rear", d/2-e)):
            c.part(fc, level+side, (-w/2, y, z), (w, e, e), design, (65, 74, 85))
        for side, x in (("Left", -w/2), ("Right", w/2-e)):
            c.part(fc, level+side, (x, -d/2+e, z), (e, d-2*e, e), design, (65, 74, 85))
    for i, x in enumerate((-w/2, w/2-e)):
        for j, y in enumerate((-d/2, d/2-e)):
            c.part(fc, f"Leg_{i}_{j}", (x, y, -h+e), (e, e, h-t["thickness_mm"]-2*e), design, (65, 74, 85))
    top = c.part(fc, "Tabletop", (-w/2, -d/2, -t["thickness_mm"]), (w, d, t["thickness_mm"]), design, (165, 220, 230))
    top.opacity = .25
    for side, x in (("Left", -m["y_rail_spacing_mm"]/2), ("Right", m["y_rail_spacing_mm"]/2)):
        c.part(fc, side+"_RailSupport", (x-10, -175, -92), (20, 350, 20), design, (80, 90, 105))
        for y in (-180, 180):
            c.part(fc, f"{side}_SupportBracket_{y}", (x-10, y-10, -92), (20, 20, 67), design, (80, 90, 105))
        c.part(fc, side+"_YRail", (x-6, -m["y_rail_mm"]/2, -72), (12, m["y_rail_mm"], 10), design, (160, 175, 190))
    bbox = top.component.bRepBodies.item(0).boundingBox
    measured = [(getattr(bbox.maxPoint, key)-getattr(bbox.minPoint, key))*10 for key in ("x","y","z")]
    assert all(abs(a-b) < 1e-6 for a,b in zip(measured, (w,d,t["thickness_mm"])))
    c.save_stage(design, "01_frame", {"tabletop_size_mm": measured})
