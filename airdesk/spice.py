"""LTspice batches and evidence. No generated netlist is counted as a run."""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path
from .common import ROOT, RESULTS, artifact, artifacts_intact, config_hash, sha256, stamp, write_json
from .environment import locate_ltspice
from .inductance import dc_resistance


def read_log(path):
    raw = Path(path).read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-16-le" if b"\x00" in raw[:100] else "utf-8")
    return raw.decode(encoding, errors="replace")


def execute(path, timeout=120):
    path = Path(path).resolve()
    # Old output cannot be mistaken for a successful new run.
    for ext in (".log", ".raw"):
        old = path.with_suffix(ext)
        if old.exists():
            old.unlink()
    proc = subprocess.run([locate_ltspice(), "-b", str(path)], cwd=path.parent,
                          capture_output=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    logfile, rawfile = path.with_suffix(".log"), path.with_suffix(".raw")
    if proc.returncode or not logfile.exists() or not rawfile.exists():
        raise RuntimeError(f"LTspice failed ({proc.returncode}): {path}; inspect its log")
    log = read_log(logfile)
    if re.search(r"fatal|singular matrix|timestep too small|unknown subcircuit|(?:current|voltage) not found|measurement.*failed", log, re.I):
        raise RuntimeError(f"LTspice solver error: {logfile}")
    measures = {}
    for line in log.splitlines():
        match = re.match(r"\s*([a-zA-Z][\w]*):.*?=\s*([-+\d.eE]+)(?:\s|$)", line)
        if match:
            try:
                measures[match[1].lower()] = float(match[2])
            except ValueError:
                pass
    if not measures or not all(math.isfinite(v) for v in measures.values()):
        raise RuntimeError(f"Missing/invalid LTspice measurements: {logfile}")
    return measures, [artifact(path), artifact(logfile), artifact(rawfile)]


def smoke(cfg):
    folder = RESULTS / "ltspice"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "rc_smoke.cir"
    path.write_text("""AirDesk RC smoke: one time constant should reach 1-exp(-1)
V1 in 0 PULSE(0 1 0 1n 1n 10m 20m)
R1 in out 1k
C1 out 0 1u
.tran 0 5m 0 1u uic
.meas tran at_tau FIND V(out) AT=1m
.end
""", encoding="ascii")
    measures, files = execute(path)
    passed = abs(measures.get("at_tau", 0) - (1 - math.exp(-1))) < .002
    data = stamp(cfg, "ltspice_smoke") | {"executed": True, "passed": passed, "measurements": measures, "artifacts": files}
    write_json(folder / "smoke.json", data)
    if not passed:
        raise RuntimeError("LTspice RC reference failed its analytical comparison")
    return data


def netlist(cfg, em, supply, frequency=None, load=None, capacitance_scale=1.0, resistance_scale=1.0, compensation_inductances=None):
    e = cfg["electrical"]
    f0 = cfg["em"]["nominal_frequency_hz"]
    f = frequency or f0
    lt, lr = em["ltx_h"], em["lrx_h"]
    # Installed capacitors stay fixed during gap/frequency/material sweeps.
    reference = compensation_inductances or (lt,lr)
    cp, cs = (capacitance_scale / ((2 * math.pi * f0)**2 * l) for l in reference)
    # FEMM open-circuit AC terminal loss plus a declared additional copper-loss allowance.
    rt = resistance_scale * (max(em["rtx_ohm"], dc_resistance(cfg["tx"]))
                             + (e["extra_winding_loss_factor"] - 1) * dc_resistance(cfg["tx"]))
    rr = resistance_scale * (max(em["rrx_ohm"], dc_resistance(cfg["rx"]))
                             + (e["extra_winding_loss_factor"] - 1) * dc_resistance(cfg["rx"]))
    return f"""AirDesk series-series resonant WPT -- assumed devices, no Qi protocol
* L/M/R from FEMM. Ferrite/mutual loss approximations documented in study.json.
* Driver and switching network are representative models, not qualified parts.
.param F={f:.12g} VB={supply:.12g} RL={load or e['load_ohm']:.12g}
.param RT={rt:.12g} RR={rr:.12g} ESR={e['capacitor_esr_ohm']:.12g}
VBUS bus 0 {{VB}}
Rdriver bus 0 {e['driver_load_ohm']:.12g}
VGA ga 0 PULSE(0 10 1u 10n 10n {{0.5/F-{e['deadtime_s']:.12g}}} {{1/F}})
VGB gb 0 PULSE(0 10 {{1u+0.5/F}} 10n 10n {{0.5/F-{e['deadtime_s']:.12g}}} {{1/F}})
S1 bus left ga 0 POWER
S2 left 0 gb 0 POWER
S3 bus right gb 0 POWER
S4 right 0 ga 0 POWER
.model POWER SW(Ron={e['switch_ron_ohm']:.12g} Roff=1G Vt=5 Vh=0)
D5 left bus BODY
D6 0 left BODY
D7 right bus BODY
D8 0 right BODY
.model BODY D(Is=1n Rs=0.025 N=1.2 Cjo=200p Tt=20n BV=60)
Coss1 bus left 200p
Coss2 left 0 200p
Coss3 bus right 200p
Coss4 right 0 200p
CPT left tx {cp:.12g} Rser={{ESR}}
LTX tx right {lt:.12g} Rser={{RT}}
LRX rx 0 {lr:.12g} Rser={{RR}}
KLINK LTX LRX {em['k']:.12g}
CSR rx ac {cs:.12g} Rser={{ESR}}
D1 ac outp RECT
D2 0 outp RECT
D3 outn ac RECT
D4 outn 0 RECT
.model RECT D(Is=20u Rs=0.035 N=1.1 Cjo=200p BV=40)
COUT outp outn {e['output_cap_f']:.12g} Rser=0.03
RLOAD outp outn {{RL}}
RREF outn 0 1G
.options plotwinsize=0
.save V(outp) V(outn) V(bus) V(tx) V(right) V(left) V(ac) I(LTX) I(LRX) I(VBUS) I(COUT) V(ga) V(gb)
.save I(S1) I(S2) I(S3) I(S4) I(D1) I(D2) I(D3) I(D4) I(D5) I(D6) I(D7) I(D8)
.tran 0 8m 0 {{1/(F*80)}}
.meas tran vout AVG V(outp,outn) FROM=6m TO=8m
.meas tran vout_previous AVG V(outp,outn) FROM=4m TO=6m
.meas tran ripple PP V(outp,outn) FROM=6m TO=8m
.meas tran pin AVG (-V(bus)*I(VBUS)) FROM=6m TO=8m
.meas tran pout AVG (V(outp,outn)*V(outp,outn)/RL) FROM=6m TO=8m
.meas tran itx RMS I(LTX) FROM=6m TO=8m
.meas tran irx RMS I(LRX) FROM=6m TO=8m
.meas tran vtx_peak MAX abs(V(tx,right)) FROM=6m TO=8m
.meas tran copper_core_loss AVG (I(LTX)*I(LTX)*RT+I(LRX)*I(LRX)*RR) FROM=6m TO=8m
.meas tran capacitor_loss AVG (I(LTX)*I(LTX)*ESR+I(LRX)*I(LRX)*ESR+I(COUT)*I(COUT)*0.03) FROM=6m TO=8m
* I(S) reference direction is reversed in exported data; conduction loss uses I^2 Ron.
* Off-state leakage with Roff=1G is below one microwatt at the allowed supply.
.meas tran switch_loss AVG ((I(S1)*I(S1)+I(S2)*I(S2)+I(S3)*I(S3)+I(S4)*I(S4))*{e['switch_ron_ohm']:.12g}) FROM=6m TO=8m
.meas tran rectifier_loss AVG (V(ac,outp)*I(D1)-V(outp)*I(D2)+V(outn,ac)*I(D3)+V(outn)*I(D4)) FROM=6m TO=8m
.meas tran body_loss AVG (V(left,bus)*I(D5)-V(left)*I(D6)+V(right,bus)*I(D7)-V(right)*I(D8)) FROM=6m TO=8m
.meas tran driver_loss AVG (V(bus)*V(bus)/{e['driver_load_ohm']:.12g}) FROM=6m TO=8m
.end
"""


def run(cfg, full=False):
    source = RESULTS / "femm" / "study.json"
    em_study = json.loads(source.read_text(encoding="utf-8"))
    if (em_study["config_sha256"] != config_hash(cfg) or not em_study["numerical_checks_passed"]
            or not artifacts_intact(em_study["nominal"]["artifacts"])):
        raise RuntimeError("A current, numerically checked FEMM nominal study is required")
    folder = RESULTS / "ltspice"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    nominal_em = em_study["nominal"]

    def case(name, em, supply, frequency=None, load=None, cap_scale=1., resistance_scale=1.):
        path = folder / (name + ".cir")
        deck=netlist(cfg, em, supply, frequency, load, cap_scale, resistance_scale,
                     (nominal_em["ltx_h"],nominal_em["lrx_h"]))
        path.write_text(deck, encoding="ascii")
        measured, files = execute(path)
        required = {"vout", "vout_previous", "ripple", "pin", "pout", "itx", "irx", "vtx_peak",
                    "copper_core_loss", "capacitor_loss", "switch_loss", "rectifier_loss", "body_loss", "driver_loss"}
        if not required <= measured.keys():
            raise RuntimeError(f"Missing measurements in {path}: {required - measured.keys()}")
        loss = sum(measured[key] for key in required if key.endswith("loss"))
        energy_error = abs(measured["pin"] - measured["pout"] - loss) / max(measured["pin"], 1e-9)
        refined=False
        if energy_error>=.02:
            path.write_text(deck.replace("1/(F*80)","1/(F*240)"),encoding="ascii")
            measured,files=execute(path)
            if not required<=measured.keys():
                raise RuntimeError("Missing measurements after time-step refinement")
            loss=sum(measured[key] for key in required if key.endswith("loss"))
            energy_error=abs(measured["pin"]-measured["pout"]-loss)/max(measured["pin"],1e-9)
            refined=True
        settled = abs(measured["vout"] - measured["vout_previous"]) / max(abs(measured["vout"]), 1e-9) < .005
        row = {"name": name, "supply_v": supply, "gap_mm": em["gap_mm"], "frequency_hz": frequency or cfg["em"]["nominal_frequency_hz"],
               "load_ohm": load or cfg["electrical"]["load_ohm"], "capacitance_scale": cap_scale,
               "resistance_scale": resistance_scale, "measurements": measured, "settled": settled,
               "time_step_refined": refined,"numerical_checks_passed":settled and energy_error<.02,
               "energy_balance_relative_error": energy_error, "efficiency": measured["pout"] / measured["pin"],
               "artifacts": files}
        rows.append(row)
        write_json(folder / "progress.json", stamp(cfg, "ltspice_progress") | {"cases": rows})
        print(f"LTspice {name}: {measured['vout']:.4f} V, {measured['pout']:.4f} W, balance error {energy_error:.3%}", flush=True)
        return row

    low, high = .5, cfg["electrical"]["supply_max_v"]
    best = None
    for index in range(10):
        supply = (low + high) / 2
        row = case(f"tune_{index:02d}", nominal_em, supply)
        voltage = row["measurements"]["vout"]
        best = row
        if abs(voltage / cfg["electrical"]["target_v"] - 1) < .005:
            break
        if voltage < cfg["electrical"]["target_v"]:
            low = supply
        else:
            high = supply
    nominal = case("nominal", nominal_em, best["supply_v"])
    if full:
        for index, em in enumerate(em_study["cases"]):
            if em["ferrite"] and em["frequency_hz"] > 0 and em["name"] != "nominal_ac":
                case(f"em_sweep_{index:02d}", em, best["supply_v"], em["frequency_hz"])
        for value in (2.5, 10., 1000.):
            case(f"load_{value:g}", nominal_em, best["supply_v"], load=value)
        for scale in (.95, 1.05):
            case(f"capacitors_{scale:g}", nominal_em, best["supply_v"], cap_scale=scale)
        case("loss_allowance_1p5", nominal_em, best["supply_v"], resistance_scale=1.5)
    measures = nominal["measurements"]
    passed = (abs(measures["vout"] / cfg["electrical"]["target_v"] - 1) <= .05
              and 4.5 <= measures["pout"] <= 5.6 and nominal["settled"]
              and nominal["energy_balance_relative_error"] < .02 and 0 < nominal["efficiency"] < 1
              and all(value>=-1e-8 for key,value in measures.items() if key.endswith("loss")))
    evidence = stamp(cfg, "electrical_operating_point") | {
        "executed": True, "passed": passed, "model": "FEMM aligned + LTspice assumed nonideal resonant link",
        "offset_mm": 0., "gap_mm": nominal_em["gap_mm"], "nominal": nominal,
        "em_source": artifact(source), "full_sweep": full,
        "artifacts": nominal["artifacts"] + nominal_em["artifacts"] + [artifact(source),artifact(Path(__file__)),artifact(ROOT/"airdesk"/"femm_study.py")],
        "limitations": cfg["limitations"] + ["Open-loop supply tuned for a fixed load, not a regulated Qi charger", "Efficiency is DC-bus to equivalent load; excludes wall adapter and gantry motors", "Reduced magnetic-loss model ignores mutual dissipative impedance"]}
    write_json(folder / "study.json", stamp(cfg, "ltspice_study") | {"cases": rows, "nominal_passed": passed})
    write_json(RESULTS / "operating_point.json", evidence)
    return evidence
