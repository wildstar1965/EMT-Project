import json
import xml.etree.ElementTree as ET
from .common import ROOT, RESULTS, config_hash, stamp, write_json
from .evidence import VerifiedPower


def report(cfg):
    def read(path):
        try: return json.loads((RESULTS/path).read_text(encoding="utf-8"))
        except OSError: return {}
    mechanics=read("mechanics.json")
    em=read("femm/study.json")
    op=read("operating_point.json")
    circuit=read("ltspice/study.json")
    fields=read("femm/field_report.json")
    waveform=read("plots/waveform_check.json")
    cad=read("fusion/motion_validation.json")
    replay=read("fusion/replay.json")
    final=read("fusion/04_final.json")
    latest=read("fusion/last_run.json")
    power=VerifiedPower(cfg)
    suites=[]
    xml=RESULTS/"tests.xml"
    if xml.exists():
        suites=list(ET.parse(xml).getroot().iter("testsuite"))
    counts={key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ("tests","failures","errors","skipped")}
    bad=[r for r in circuit.get("cases",[]) if not r.get("numerical_checks_passed",False)]
    flagged=[]
    for row in bad:
        reasons=[]
        if not row.get("settled",False):
            reasons.append("Output-voltage change between measurement windows is at least 0.5%; not settled")
        if row["energy_balance_relative_error"] >= .02:
            reasons.append("Power-balance residual is at least 2%")
        flagged.append({key:row[key] for key in ("name","gap_mm","frequency_hz","settled","energy_balance_relative_error")}
                       | {"failure_reasons":reasons})
    checks={"femm_numerical_checks":bool(em.get("numerical_checks_passed")),
            "nominal_electrical_evidence":power.available,"waveform_crosscheck":bool(waveform.get("passed")),
            "field_export":bool(fields.get("passed")),"cad_nine_pose_motion":bool(cad.get("passed")),
            "fusion_replay":bool(replay.get("passed")) and latest.get("status")=="passed",
            "final_cad_export":bool(final.get("passed")) and final.get("config_sha256")==config_hash(cfg),
            "tests":counts["tests"]>0 and counts["failures"]==0 and counts["errors"]==0 and counts["skipped"]==0}
    data=stamp(cfg,"project_validation")|{"passed":all(checks.values()),"checks":checks,"test_counts":counts,
        "nominal_power_w":power.watts,"flagged_sensitivity_cases":flagged,
        "qualification_limits":cfg["limitations"]+["Motor running-torque selection remains unqualified", "Nine-pose interference sampling is not continuous swept-volume proof", "Flagged sensitivity points are excluded from verified charging data"]}
    write_json(RESULTS/"validation.json",data)
    m=op.get("nominal",{}).get("measurements",{})
    lines=["# AirDesk validation report","",f"Generated: {data['created_utc']}","",
           "This report distinguishes the implemented simulation from physical-product qualification.","",
           "## Executed acceptance checks","","| Check | Result |","|---|---|"]
    lines += [f"| {name.replace('_',' ')} | {'PASS' if passed else 'NOT VERIFIED'} |" for name,passed in checks.items()]
    lines += ["",f"Tests: **{counts['tests']} total, {counts['failures']} failures, {counts['errors']} errors, {counts['skipped']} skipped**.","",
        "## Measured nominal electrical result","",f"- Receiver output: **{m.get('vout',0):.4f} V, {m.get('pout',0):.4f} W** into 5 Ω.",
        f"- DC-bus input: **{m.get('pin',0):.4f} W** at {op.get('nominal',{}).get('supply_v',0):.6f} V.",
        f"- Model DC-bus-to-load efficiency: **{100*op.get('nominal',{}).get('efficiency',0):.2f}%**.",
        f"- Power-balance residual: **{100*op.get('nominal',{}).get('energy_balance_relative_error',0):.4f}%**.",
        f"- Output ripple: **{1000*m.get('ripple',0):.2f} mV peak-to-peak**.",
        f"- Tx / Rx RMS currents: **{m.get('itx',0):.4f} / {m.get('irx',0):.4f} A**.",
        f"- Tx winding peak terminal voltage: **{m.get('vtx_peak',0):.2f} V**.",
        f"- Independent raw-waveform power crosscheck relative error: **{waveform.get('relative_error',0):.3g}**.","",
        "These results use assumed ferrite and device models. They exclude wall-adapter and gantry-motor power and do not establish Qi compatibility or thermal safety.","",
        "## Electromagnetic and mechanical checks","",
        f"- FEMM cases executed: {len(em.get('cases',[]))}; field samples exported: {fields.get('samples',0)}.",
        f"- Nominal aligned coupling: {em.get('nominal',{}).get('k',0):.6f} at 9.1 mm.",
        f"- Mesh / boundary / air-core comparison errors: {100*em.get('convergence_relative_error',0):.3f}% / {100*em.get('boundary_relative_error',0):.3f}% / {100*em.get('air_reference_relative_error',0):.3f}%.",
        f"- Analytical central tabletop deflection: {mechanics.get('plate_deflection',{}).get('total_mm',0):.3f} mm.",
        f"- Clearance after analytical sag and 0.5 mm tolerance allowance: {mechanics.get('residual_clearance_mm',0):.3f} mm.",
        f"- Fusion waypoint checks: {len(cad.get('samples',[]))}; detected moving interferences: {len(cad.get('moving_interferences',[]))}.",
        f"- Fusion trajectory samples: {replay.get('trajectory_samples',0)}; maximum recorded XY error: {replay.get('maximum_position_error_mm',0):.6g} mm.",
        "- Interference exclusions: fixed-subassembly mating overlaps, belts/clamps, cable envelopes, and phone internals.","",
        "## Sensitivity limits and outstanding hardware work","",
        f"LTspice cases executed: {len(circuit.get('cases',[]))}. Numerically flagged sensitivity cases: {len(bad)}.","",
        "| Flagged case | Gap | Frequency | Power-balance residual | Reason |","|---|---:|---:|---:|---|"]
    lines += [f"| {r['name']} | {r['gap_mm']:.1f} mm | {r['frequency_hz']/1000:.0f} kHz | {r['energy_balance_relative_error']*100:.3f}% | {'; '.join(r['failure_reasons'])} |" for r in flagged]
    lines += ["","Flagged points retain their raw files but are not accepted operating points and cannot enable charging in the demo.","",
        "The 1 kΩ load study reaches about 40 V: the open-loop power stage needs regulation and protection before a physical receiver could use it. The 5 Ω nominal result is the sole enabled charging operating point.","",
        "The current BOM uses reference envelopes. A vendor motor torque-speed curve, physical coil measurements, component stress/rating selection, foreign-object protection, and thermal tests remain hardware qualification work.","",
        "## Reproducibility evidence","",
        "Raw solver files and their hashes are retained under `results/femm` and `results/ltspice`. The operating-point manifest also binds the current solver-source files. CAD stages export Fusion archives, STEP files, viewport images, and geometry reports. `results/demo/trajectory.csv` is the shared animation input. See the root README for exact commands.",""]
    (ROOT/"docs"/"VALIDATION.md").write_text("\n".join(lines),encoding="utf-8")
    return data
