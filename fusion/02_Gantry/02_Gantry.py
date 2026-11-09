import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cadlib as c


def winding(parent, name, coil, z, design, x=0, y=0):
    occ = c.component(parent, name)
    pitch = (coil["outer_radius_mm"] - coil["inner_radius_mm"]) / coil["turns"]
    for turn in range(coil["turns"]):
        radius = coil["inner_radius_mm"] + (turn+.5)*pitch
        c.cylinder(occ.component, f"Turn_{turn+1:02d}", (x,y,z-coil["thickness_mm"]/2),
                   (x,y,z+coil["thickness_mm"]/2), radius+.4*pitch, radius-.4*pitch)
    c.paint(design, occ.component, "AirDesk copper", (205, 115, 48))
    return occ


def run(context):
    app, design, cfg = c.active()
    root, m = design.rootComponent, cfg["mechanical"]
    if any(occ.component.name == "Bridge" for occ in root.occurrences):
        raise RuntimeError("Gantry already exists; regenerate stage 01 to rebuild")
    frame = c.find(design, "Frame").component
    bridge = c.component(root, "Bridge", False)
    carriage = c.component(root, "Carriage", False)
    phone = c.component(root, "Phone", False)
    xrotor = c.component(root, "X_DriveRotor", False)
    yrotor = c.component(root, "Y_DriveRotor", False)
    bc, cc = bridge.component, carriage.component
    for side, x in (("Left", -m["y_rail_spacing_mm"]/2), ("Right", m["y_rail_spacing_mm"]/2)):
        block = c.part(bc, side+"_YBlock", (x-13.5,-22.5,-71.8), (27,45,18.8), design, (35,115,155))
        c.box(block.component, "Guide clearance", (x-6.2,-23.5,-71.9), (12.4,47,10.1), cut=True)
    beam = c.part(bc, "Crossbeam", (-275,-20,-53), (550,40,20), design, (70,80,95))
    c.box(beam.component, "X shaft edge clearance", (-278,17,-54), (6,6,22), cut=True)
    c.part(bc, "X_Rail", (-m["x_rail_mm"]/2,-6,-33), (m["x_rail_mm"],12,10), design, (160,175,190))
    block = c.part(cc, "X_Block", (-22.5,-13.5,-32.8), (45,27,18.8), design, (35,115,155))
    c.box(block.component, "Guide clearance", (-23.5,-6.2,-32.9), (47,12.4,10.1), cut=True)
    c.part(cc, "Carrier standoff", (-15,-10,-14), (30,20,2.6), design, (235,235,220))
    tx_z = -cfg["table"]["thickness_mm"]-m["top_clearance_mm"]-cfg["tx"]["thickness_mm"]/2
    ferrite_top = tx_z-cfg["tx"]["thickness_mm"]/2-cfg["em"]["ferrite_insulation_mm"]
    ferrite_bottom = ferrite_top-cfg["tx"]["ferrite_thickness_mm"]
    c.part(cc, "Nonconductive_Carrier", (-m["carrier_mm"]/2,-m["carrier_mm"]/2,ferrite_bottom-2),
           (m["carrier_mm"],m["carrier_mm"],2), design, (230,235,222))
    txf = c.component(cc, "Tx_Ferrite")
    c.cylinder(txf.component, "Ferrite disk", (0,0,ferrite_bottom), (0,0,ferrite_top), cfg["tx"]["ferrite_radius_mm"])
    c.paint(design, txf.component, "AirDesk ferrite", (45,48,54))
    winding(cc, "Tx_Winding", cfg["tx"], tx_z, design)
    c.part(cc, "X_BeltClamp", (-8,13.5,-21), (16,10,5), design, (35,115,155))
    # Dropped X motor avoids intersecting the fixed Y guide support; an extension shaft connects it.
    c.part(bc, "X_MotorHousing", (-296,-1,-137), (42,42,42), design, (45,48,54))
    c.part(bc, "X_MotorDropBracket", (-298,-4,-95), (3,48,64), design, (150,160,175))
    c.part(bc, "X_MotorMountPlate", (-298,-4,-97), (46,48,2), design, (150,160,175))
    mount = c.part(bc, "X_MotorUpperMount", (-298,-4,-33), (46,48,2), design, (150,160,175))
    c.box(mount.component, "Shaft clearance", (-278,17,-33.1), (6,6,2.2), cut=True)
    c.cylinder(xrotor.component, "X_extension_shaft", (-275,20,-95), (-275,20,-15), 2.5)
    c.cylinder(xrotor.component, "X_20T_pulley", (-275,20,-26), (-275,20,-16), 6.3662)
    idler = c.component(bc, "X_Idler")
    c.cylinder(idler.component, "Idler", (270,20,-26), (270,20,-16), 6.3662)
    for y in (13.6338,26.3662):
        c.part(bc, f"X_Belt_{y:g}", (-275,y-.6,-24), (545,1.2,6), design, (30,35,42))
    c.part(frame, "Y_MotorHousing", (-299,-176,-131), (42,42,42), design, (45,48,54))
    c.cylinder(yrotor.component, "Y_common_shaft", (-257,-155,-110), (270,-155,-110), 4)
    for side, x in (("Left", -235), ("Right", 235)):
        c.cylinder(yrotor.component, side+"_Y_pulley", (x-5,-155,-110), (x+5,-155,-110), 6.3662)
        idler = c.component(frame, side+"_Y_Idler")
        c.cylinder(idler.component, "Idler", (x-5,155,-110), (x+5,155,-110), 6.3662)
        for z in (-116.3662,-103.6338):
            c.part(frame, f"{side}_Y_Belt_{z:g}", (x-3,-155,z-.6), (6,310,1.2), design, (30,35,42))
        c.part(bc, side+"_Y_BeltBracket", (x-4,-7,-104), (8,14,51), design, (35,115,155))
        bearing = c.component(frame, side+"_ShaftBearing")
        c.cylinder(bearing.component, "Bearing", (x-12,-155,-110), (x-6,-155,-110), 11, 4.2)
    for axis, positions in (("X", [(-245,35,-43),(235,35,-43)]), ("Y", [(-240,-166,-83),(-240,156,-83)])):
        parent = bc if axis == "X" else frame
        for i, pos in enumerate(positions):
            c.part(parent, f"{axis}_LimitSwitch_{i}", pos, (10,8,6), design, (190,60,60))
    p = cfg["phone"]
    shell = c.part(phone.component, "Phone_Shell", (-p["width_mm"]/2,-p["length_mm"]/2,0),
                   (p["width_mm"],p["length_mm"],p["thickness_mm"]), design, (40,50,68))
    c.box(shell.component, "Internal cavity", (-p["width_mm"]/2+3,-p["length_mm"]/2+3,.5),
          (p["width_mm"]-6,p["length_mm"]-6,p["thickness_mm"]-1), cut=True)
    shell.opacity = .5
    dx, dy = p["receiver_offset_x_mm"], p["receiver_offset_y_mm"]
    winding(phone.component, "Rx_Winding", cfg["rx"], p["receiver_depth_mm"], design, dx, dy)
    rxf = c.component(phone.component, "Rx_Ferrite")
    z = p["receiver_depth_mm"]+cfg["rx"]["thickness_mm"]/2+cfg["em"]["ferrite_insulation_mm"]
    c.cylinder(rxf.component,"Receiver ferrite",(dx,dy,z),(dx,dy,z+cfg["rx"]["ferrite_thickness_mm"]),cfg["rx"]["ferrite_radius_mm"])
    c.paint(design,rxf.component,"AirDesk ferrite",(45,48,54))
    # Transparent clearance envelopes, not manufactured cable-chain links.
    cable = c.part(frame,"Y_CableEnvelope",(273,-140,-155),(7,280,20),design,(65,150,165))
    cable.opacity = .3
    cable = c.part(bc,"X_CableEnvelope",(-200,-48,-65),(400,7,10),design,(65,150,165))
    cable.opacity = .3
    c.save_stage(design,"02_gantry", {"nominal_winding_plane_gap_mm": p["receiver_depth_mm"]-tx_z,
        "coil_top_clearance_mm": m["top_clearance_mm"],
        "simplifications": ["Windings are disconnected concentric turn envelopes; leads omitted", "Belts have straight run envelopes; tooth and wrap detail omitted", "Cable chains are clearance envelopes", "X motor uses a drop bracket and extension shaft", "Fasteners and bearing internals are not manufacturing detail"]})
