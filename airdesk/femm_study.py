"""Small, repeatable axisymmetric FEMM cases, with retained raw solver files."""
from __future__ import annotations

import csv
import math
from pathlib import Path
import numpy as np
from .common import RESULTS, artifact, nominal_gap, stamp, write_json
from .inductance import coil_mutual, dc_resistance, offset_mutual


def _region(f, x1, y1, x2, y2, material, mesh, circuit="<None>", turns=0, group=0):
    f.mi_drawrectangle(x1, y1, x2, y2)
    x, y = (x1 + x2) / 2, (y1 + y2) / 2
    f.mi_addblocklabel(x, y)
    f.mi_selectlabel(x, y)
    f.mi_setblockprop(material, 0, mesh, circuit, 0, group, turns)
    f.mi_clearselected()


def solve_case(f, cfg, folder, name, gap, frequency=0.0, ferrite=True, mesh=.3, boundary=150.0, mu=None):
    f.newdocument(0)
    f.mi_probdef(frequency, "millimeters", "axi", 1e-9, 0, 30)
    f.mi_addmaterial("Air", 1, 1, 0, 0, 0)
    permeability = mu if mu is not None else cfg["em"]["ferrite_mu_r_assumed"]
    f.mi_addmaterial("Assumed ferrite", permeability, permeability, 0, 0, 0, 0,
                     cfg["em"]["ferrite_loss_angle_deg_assumed"] if frequency else 0)
    for label in ("tx", "rx"):
        coil = cfg[label]
        # FEMM LamType=5: litz wire; strand diameter in mm, conductivity MS/m.
        f.mi_addmaterial(label + " litz", 1, 1, 0, 0, 58, 0, 0, 1, 5, 0, 0,
                         coil["strands"], coil["strand_diameter_mm"])
        f.mi_addcircprop(label, 0, 1)
    f.mi_addboundprop("A zero", 0, 0, 0, 0, 0, 0, 0, 0, 0)
    f.mi_drawrectangle(0, -boundary, boundary, boundary)
    for x, y in ((0, 0), (boundary, 0), (boundary / 2, -boundary), (boundary / 2, boundary)):
        f.mi_selectsegment(x, y)
        f.mi_setsegmentprop("A zero", 0, 1, 0, 0)
        f.mi_clearselected()
    f.mi_addblocklabel(boundary * .8, boundary * .8)
    f.mi_selectlabel(boundary * .8, boundary * .8)
    f.mi_setblockprop("Air", 0, 8, "<None>", 0, 0, 0)
    f.mi_clearselected()
    for group, (label, z) in enumerate((("tx", 0), ("rx", gap)), start=1):
        coil = cfg[label]
        half = coil["thickness_mm"] / 2
        _region(f, coil["inner_radius_mm"], z - half, coil["outer_radius_mm"], z + half,
                label + " litz", mesh, label, coil["turns"], group)
        if ferrite:
            ins = cfg["em"]["ferrite_insulation_mm"]
            thickness = coil["ferrite_thickness_mm"]
            bottom = -half - ins - thickness if label == "tx" else z + half + ins
            _region(f, 0, bottom, coil["ferrite_radius_mm"], bottom + thickness,
                    "Assumed ferrite", mesh, group=group + 2)
    flux, voltage = np.zeros((2, 2), dtype=complex), np.zeros((2, 2), dtype=complex)
    files = []
    for drive, circuit in enumerate(("tx", "rx")):
        for other in ("tx", "rx"):
            f.mi_modifycircprop(other, 1, 1 if other == circuit else 0)
        path = (folder / (name + "_" + circuit + ".fem")).resolve()
        f.mi_saveas(str(path))
        f.mi_analyze(1)
        f.mi_loadsolution()
        for sense, other in enumerate(("tx", "rx")):
            _, v, linkage = f.mo_getcircuitproperties(other)
            flux[sense, drive], voltage[sense, drive] = complex(linkage), complex(v)
        files.extend([artifact(path), artifact(path.with_suffix(".ans"))])
        f.mo_close()
    f.mi_close()
    ltx, lrx = float(flux[0, 0].real), float(flux[1, 1].real)
    mutual = float((flux[0, 1].real + flux[1, 0].real) / 2)
    if ltx <= 0 or lrx <= 0:
        raise ValueError("FEMM returned non-positive self inductance")
    k = mutual / math.sqrt(ltx * lrx)
    reciprocity = abs(flux[0, 1] - flux[1, 0]) / max(abs(flux[0, 1]), 1e-20)
    if abs(k) >= 1 or reciprocity > .01:
        raise ValueError(f"Nonphysical/unconverged FEMM result: k={k}, reciprocity={reciprocity}")
    return {"name": name, "gap_mm": gap, "frequency_hz": frequency, "ferrite": ferrite,
            "mesh_mm": mesh, "boundary_mm": boundary, "assumed_mu_r": permeability if ferrite else 1,
            "ltx_h": ltx, "lrx_h": lrx, "mutual_h": mutual, "k": k,
            "rtx_ohm": float(voltage[0, 0].real), "rrx_ohm": float(voltage[1, 1].real),
            "mutual_impedance_real_ohm": float(voltage[0, 1].real),
            "reciprocity_relative_error": float(reciprocity), "artifacts": files}


def run(cfg, full=False, ac_only=False):
    import femm
    folder = RESULTS / "femm"
    folder.mkdir(parents=True, exist_ok=True)
    gap, freq = nominal_gap(cfg), cfg["em"]["nominal_frequency_hz"]
    cases = []
    femm.openfemm(1)
    try:
        jobs = [("air_reference", gap, 0, False, .3, 150, None),
                ("nominal_coarse", gap, 0, True, .6, 150, None),
                ("nominal_medium", gap, 0, True, .3, 150, None),
                ("nominal_fine", gap, 0, True, .15, 150, None),
                ("boundary_check", gap, 0, True, .3, 300, None),
                ("nominal_ac", gap, freq, True, .3, 150, None)]
        if full:
            jobs += [(f"gap_{g:g}_f_{f:g}", g, f, True, .3, 150, None)
                     for g in cfg["em"]["gaps_mm"] for f in cfg["em"]["frequencies_hz"]
                     if not (g == gap and f == freq)]
            jobs += [(f"mu_{mu}", gap, freq, True, .3, 150, mu) for mu in (1000, 3000)]
        if ac_only:
            jobs = [("nominal_ac", gap, freq, True, .3, 150, None)]
        for job in jobs:
            result = solve_case(femm, cfg, folder, *job)
            cases.append(result)
            write_json(folder / "progress.json", stamp(cfg, "femm_progress") | {"cases": cases})
            print(f"FEMM {job[0]}: Ltx={result['ltx_h']*1e6:.4f} uH, k={result['k']:.5f}", flush=True)
    finally:
        femm.closefemm()
    if ac_only:
        return cases[0]
    by_name = {c["name"]: c for c in cases}
    medium, fine = by_name["nominal_medium"], by_name["nominal_fine"]
    convergence = max(abs(medium[k] / fine[k] - 1) for k in ("ltx_h", "lrx_h", "k"))
    boundary_error = max(abs(medium[k] / by_name["boundary_check"][k] - 1) for k in ("ltx_h", "lrx_h", "k"))
    analytic = coil_mutual(cfg["tx"], cfg["rx"], gap)
    air_error = abs(analytic / by_name["air_reference"]["mutual_h"] - 1)
    data = stamp(cfg, "femm_axisymmetric_study") | {"executed": True, "full_sweep": full,
        "convergence_relative_error": convergence, "boundary_relative_error": boundary_error,
        "air_reference_relative_error": air_error,
        "numerical_checks_passed": convergence < .02 and boundary_error < .02 and air_error < .05,
        "nominal": by_name["nominal_ac"], "cases": cases,
        "limitations": cfg["limitations"] + ["AC equivalent series resistances are open-circuit terminal losses; mutual loss is retained in report but omitted in reduced LTspice model", "Ferrite permeability/loss angle are assumptions; no saturation or thermal qualification"]}
    write_json(folder / "study.json", data)
    columns = [k for k in cases[0] if k != "artifacts"]
    with (folder / "cases.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        writer.writerows({k: row[k] for k in columns} for row in cases)
    return data


def offset_study(cfg):
    folder = RESULTS / "em_approximation"
    folder.mkdir(parents=True, exist_ok=True)
    gap = nominal_gap(cfg)
    rows = []
    for offset in (0, 2, 5, 10, 15, 20, 30, 50, 80):
        coarse = offset_mutual(cfg["tx"], cfg["rx"], gap, offset, 64)
        fine = offset_mutual(cfg["tx"], cfg["rx"], gap, offset, 128)
        rows.append({"offset_mm": offset, "gap_mm": gap, "mutual_h": fine,
                     "absolute_refinement_change_h": abs(fine - coarse), "model": "air_core_filament_only"})
    with (folder / "offset.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    data = stamp(cfg, "air_core_offset_approximation") | {"rows": rows, "valid_for_ferrite": False,
        "tx_dc_resistance_ohm": dc_resistance(cfg["tx"]), "rx_dc_resistance_ohm": dc_resistance(cfg["rx"])}
    write_json(folder / "study.json", data)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot([r["offset_mm"] for r in rows], [r["mutual_h"] * 1e6 for r in rows], "o-")
    ax.set(xlabel="Lateral offset (mm)", ylabel="Mutual inductance (µH)", title="Air-core estimate only — no ferrite or gantry metal")
    ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(folder / "offset.png", dpi=160)
    plt.close(fig)
    return data
