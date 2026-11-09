"""Native Fusion command, retained event handlers, and in-Fusion status palette."""
import json
import math
from pathlib import Path
import traceback
import adsk.core as core
import cadlib as c
import native_motion as motion
from airdesk.motion import PhonePose
from airdesk.native_tracking import checked_target

COMMAND_ID="AirDesk_PlacePhone"
PALETTE_ID="AirDesk_ChargingStatus"
PANEL_ID="SolidScriptsAddinsPanel"
_handlers=[]
_sessions=[]
_busy=False
_status={"state":"UNVERIFIED","power_w":0.,"reason":"Run Place Phone to check this assembly"}


def record_error():
    c.write_json(motion.OUTPUT/"last_error.json",{"error":traceback.format_exc()})


def bind(event,handler,owner=None):
    event.add(handler)
    (owner if owner is not None else _handlers).append((event,handler))


def publish(data):
    global _status
    _status=data
    ui=core.Application.get().userInterface
    palette=ui.palettes.itemById(PALETTE_ID)
    if palette:
        palette.sendInfoToHTML("status",json.dumps(data))


def invalidate(reason="Assembly may have changed; run Place Phone to check alignment again"):
    publish({"state":"UNVERIFIED","power_w":0.,"reason":reason})


class Html(core.HTMLEventHandler):
    def notify(self,args):
        try:
            if args.action=="ready": publish(_status)
            elif args.action=="place" and not _busy:
                core.Application.get().userInterface.commandDefinitions.itemById(COMMAND_ID).execute()
        except Exception: record_error()


class OtherCommand(core.ApplicationCommandEventHandler):
    def notify(self,args):
        if not _busy and args.commandId not in (COMMAND_ID,"SelectCommand"):
            invalidate()


class DocumentChange(core.DocumentEventHandler):
    def notify(self,args):
        invalidate("Active document changed; run Place Phone in the AirDesk assembly")


class SelectionChange(core.ActiveSelectionEventHandler):
    def notify(self,args):
        if not _busy and not _sessions and core.Application.get().userInterface.activeSelections.count:
            invalidate("Viewport selection changed; run Place Phone to verify again before displaying power")


def tabletop_face(entity):
    face=c.fusion.BRepFace.cast(entity)
    if not face: return False
    occ=face.assemblyContext
    name=occ.component.name if occ else face.body.parentComponent.name
    bounds=face.boundingBox
    return (name=="Tabletop" and abs(bounds.minPoint.z)<1e-6 and abs(bounds.maxPoint.z)<1e-6
            and core.Plane.cast(face.geometry) is not None)


class Session:
    def __init__(self,command):
        self.command=command
        self.handlers=[]
        self.app,self.design,self.cfg=c.active()
        self.limits=motion.actual_limits(self.design)
        self.updating=False
        self.selected=False
        pose=motion.current_pose(self.design)
        command.isExecutedWhenPreEmpted=False
        command.isPositionDependent=False
        command.okButtonText="Move phone"
        command.setDialogInitialSize(390,380)
        inputs=command.commandInputs
        inputs.addTextBoxCommandInput("instructions","", "Select the TOP face at the desired phone centre, or enter X/Y. Then click Move phone. Cancel leaves the assembly unchanged.",3,True)
        self.pick=inputs.addSelectionInput("tabletop_point","Tabletop position","Select a point on the top tabletop face")
        self.pick.addSelectionFilter("PlanarFaces")
        self.pick.setSelectionLimits(0,1)
        self.x=inputs.addValueInput("phone_x","Phone X","mm",core.ValueInput.createByReal(pose.x_mm/10))
        self.y=inputs.addValueInput("phone_y","Phone Y","mm",core.ValueInput.createByReal(pose.y_mm/10))
        self.yaw=inputs.addValueInput("phone_yaw","Phone rotation","deg",core.ValueInput.createByReal(math.radians(pose.yaw_deg)))
        self.message=inputs.addTextBoxCommandInput("placement_status","Placement check","",5,True)
        self.update_message()
        bind(command.preSelect,Preselect(),self.handlers)
        bind(command.select,Selected(self),self.handlers)
        bind(command.inputChanged,Changed(self),self.handlers)
        bind(command.validateInputs,Validate(self),self.handlers)
        bind(command.execute,Execute(self),self.handlers)
        bind(command.destroy,Destroy(self),self.handlers)
        palette=core.Application.get().userInterface.palettes.itemById(PALETTE_ID)
        if palette: palette.isVisible=True
        invalidate("Placement pending; transmitter disabled until measured alignment passes")
        c.write_json(motion.OUTPUT/"command_open.json",{"command_id":COMMAND_ID,"status":"ready"})

    def pose(self):
        if not all(i.isValidExpression for i in (self.x,self.y,self.yaw)):
            raise ValueError("Enter valid X, Y, and angle expressions")
        return PhonePose(self.x.value*10,self.y.value*10,math.degrees(self.yaw.value))

    def update_message(self):
        try:
            pose=self.pose()
            target=checked_target(self.cfg,pose,self.limits)
            self.message.text=(f"Receiver / carriage target: X {target[0]:.2f} mm, Y {target[1]:.2f} mm\n"
                "Phone footprint supported; travel allowed.\nCharging is checked after motion and settling.")
            return True
        except (ValueError,RuntimeError) as exc:
            self.message.text="PLACEMENT REJECTED\n"+str(exc)
            return False


class Created(core.CommandCreatedEventHandler):
    def notify(self,args):
        try:
            session=Session(args.command)
            _sessions.append(session)
        except Exception:
            record_error()
            core.Application.get().userInterface.messageBox(str(traceback.format_exc()),"Place Phone")


class Preselect(core.SelectionEventHandler):
    def notify(self,args):
        args.isSelectable=tabletop_face(args.selection.entity)


class Selected(core.SelectionEventHandler):
    def __init__(self,session): super().__init__(); self.session=session
    def notify(self,args):
        s=self.session
        try:
            if not tabletop_face(args.selection.entity): return
            point=args.selection.point
            s.updating=True
            s.x.value=point.x
            s.y.value=point.y
            s.selected=True
            s.updating=False
            s.update_message()
            c.write_json(motion.OUTPUT/"last_selection.json",{"source":"Fusion Command.select / Selection.point",
                "selected_point_mm":[point.x*10,point.y*10,point.z*10],"valid":s.update_message()})
        except Exception:
            s.updating=False
            record_error()


class Changed(core.InputChangedEventHandler):
    def __init__(self,session): super().__init__(); self.session=session
    def notify(self,args):
        if not self.session.updating:
            self.session.update_message()


class Validate(core.ValidateInputsEventHandler):
    def __init__(self,session): super().__init__(); self.session=session
    def notify(self,args):
        args.areInputsValid=self.session.update_message()


class Execute(core.CommandEventHandler):
    def __init__(self,session): super().__init__(); self.session=session
    def notify(self,args):
        global _busy
        s=self.session
        ui=s.app.userInterface
        enabled=ui.isUIEnabled
        try:
            pose=s.pose()
            checked_target(s.cfg,pose,motion.actual_limits(s.design))
            _busy=True
            ui.isUIEnabled=False
            result=motion.place(s.design,s.cfg,pose,publish=publish)
            result["interaction_source"]="tabletop_selection" if s.selected else "native_numeric_inputs"
            c.write_json(motion.OUTPUT/"last_command.json",result)
            (motion.OUTPUT/"last_error.json").unlink(missing_ok=True)
        except Exception as exc:
            record_error()
            invalidate("Placement failed: "+str(exc))
            args.executeFailed=True
            args.executeFailedMessage=str(exc)
        finally:
            ui.isUIEnabled=enabled
            _busy=False
            palette=ui.palettes.itemById(PALETTE_ID)
            if palette:
                palette.isVisible=True
                publish(_status)


class Destroy(core.CommandEventHandler):
    def __init__(self,session): super().__init__(); self.session=session
    def notify(self,args):
        if self.session in _sessions: _sessions.remove(self.session)
        self.session.handlers.clear()


def start():
    if _handlers: return
    app=core.Application.get()
    ui=app.userInterface
    definition=ui.commandDefinitions.itemById(COMMAND_ID)
    if definition: definition.deleteMe()
    definition=ui.commandDefinitions.addButtonDefinition(COMMAND_ID,"Place Phone",
        "Place the AirDesk phone on its tabletop and align the existing XY charging carriage.")
    bind(definition.commandCreated,Created())
    panel=ui.allToolbarPanels.itemById(PANEL_ID)
    if not panel: raise RuntimeError("Fusion Design Scripts and Add-Ins panel is unavailable")
    control=panel.controls.itemById(COMMAND_ID) or panel.controls.addCommand(definition)
    control.isPromoted=True
    palette=ui.palettes.itemById(PALETTE_ID)
    if palette: palette.deleteMe()
    palette=ui.palettes.add(PALETTE_ID,"AirDesk | Charging simulation",
        (Path(__file__).parent/"AirDeskNative"/"status.html").as_uri(),True,True,True,350,420,True)
    palette.dockingState=core.PaletteDockingStates.PaletteDockStateRight
    bind(palette.incomingFromHTML,Html())
    bind(ui.commandStarting,OtherCommand())
    bind(ui.activeSelectionChanged,SelectionChange())
    bind(app.documentActivated,DocumentChange())
    bind(app.documentDeactivated,DocumentChange())
    c.write_json(motion.OUTPUT/"addin.json",{"status":"loaded","fusion_version":app.version,
                 "command_id":COMMAND_ID,"ordinary_occurrence_drag_tracking":False})
    app.log("AirDesk: Place Phone is available in Design > Utilities > Add-Ins, and command search (S).")


def stop():
    ui=core.Application.get().userInterface
    for event,handler in _handlers:
        try: event.remove(handler)
        except RuntimeError: pass
    _handlers.clear()
    panel=ui.allToolbarPanels.itemById(PANEL_ID)
    control=panel.controls.itemById(COMMAND_ID) if panel else None
    if control: control.deleteMe()
    definition=ui.commandDefinitions.itemById(COMMAND_ID)
    if definition: definition.deleteMe()
    palette=ui.palettes.itemById(PALETTE_ID)
    if palette: palette.deleteMe()
    c.write_json(motion.OUTPUT/"addin.json",{"status":"stopped","command_id":COMMAND_ID})
