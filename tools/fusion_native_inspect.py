"""Run inside Fusion to retain native UI state as troubleshooting evidence."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"fusion"))
import cadlib as c
import native_command as native
import native_motion as motion


def run(context):
    app,design,cfg=c.active()
    palette=app.userInterface.palettes.itemById(native.PALETTE_ID)
    c.write_json(motion.OUTPUT/"ui_inspection.json",{
        "palette_exists":bool(palette),"palette_visible":palette.isVisible if palette else None,
        "retained_handlers":len(native._handlers),"sessions":len(native._sessions),
        "status":native._status,"active_command":app.userInterface.activeCommand,
        "phone_pose":list(vars(motion.current_pose(design)).values()),
        "tx_mm":motion.centre(design,"Tx_Winding")})
