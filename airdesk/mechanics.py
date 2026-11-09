"""Preliminary analytical checks; not a structural or motor qualification."""
import math
import numpy as np
from .common import RESULTS, nominal_gap, stamp, write_json


def plate_deflection(cfg, terms=99):
    t, p = cfg["table"], cfg["phone"]
    a, b, h = (t[k] / 1000 for k in ("width_mm", "depth_mm", "thickness_mm"))
    rigidity = t["elastic_modulus_pa"] * h**3 / (12 * (1 - t["poisson_ratio"]**2))
    pressure, load = t["density_kg_m3"] * 9.81 * h, p["mass_kg"] * 9.81
    gravity = phone = 0.0
    for m in range(1, terms + 1, 2):
        for n in range(1, terms + 1, 2):
            den = rigidity * math.pi**4 * ((m / a)**2 + (n / b)**2)**2
            sign = math.sin(m * math.pi / 2) * math.sin(n * math.pi / 2)
            gravity += 16 * pressure * sign / (m * n * math.pi**2 * den)
            phone += (4 * load * np.sinc(m * p["width_mm"] / 1000 / (2 * a))
                      * np.sinc(n * p["length_mm"] / 1000 / (2 * b)) / (a * b * den))
    return {"self_weight_mm": gravity * 1000, "phone_mm": phone * 1000,
            "total_mm": (gravity + phone) * 1000}


def report(cfg):
    m = cfg["mechanical"]
    advance = m["belt_pitch_mm"] * m["pulley_teeth"]
    radius = advance / (2 * math.pi * 1000)
    force = m["assumed_moving_mass_kg"] * m["accel_mm_s2"] / 1000 + m["assumed_drag_n"]
    sag = plate_deflection(cfg)
    data = stamp(cfg, "analytical_mechanics") | {
        "gap_mm": nominal_gap(cfg), "plate_deflection": sag,
        "residual_clearance_mm": m["top_clearance_mm"] - sag["total_mm"] - m["sag_tolerance_allowance_mm"],
        "command_resolution_mm": advance / (m["motor_steps_rev"] * m["microsteps"]),
        "motor_speed_rpm": m["speed_mm_s"] / advance * 60,
        "required_running_torque_nm_with_margin": force * radius / m["drive_efficiency"] * m["torque_margin"],
        "motor_selection_verified": False,
        "assumptions": ["Simply supported plate, centred uniformly distributed phone load", "Linear small-deflection elastic analysis", "Assumed moving mass and drag; no selected motor torque curve"]}
    write_json(RESULTS / "mechanics.json", data)
    return data
