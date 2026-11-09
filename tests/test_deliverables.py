"""Integration checks on real output, skipped when an upstream stage was not run."""
import csv
import json
import math
import pytest
from airdesk.common import RESULTS, load_config
from airdesk.evidence import VerifiedPower


def load_result(relative):
    path=RESULTS/relative
    if not path.exists(): pytest.skip(f"Stage not executed: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_femm_and_circuit_evidence():
    em=load_result("femm/study.json")
    assert em["executed"] and em["numerical_checks_passed"]
    assert em["convergence_relative_error"]<.02
    assert em["air_reference_relative_error"]<.05
    load_result("operating_point.json")
    power=VerifiedPower(load_config())
    assert power.available,power.reason
    assert 4.5<=power.watts<=5.6
    assert load_result("plots/waveform_check.json")["passed"]


def test_recorded_controller_trace_has_no_false_charging_or_limit_violation():
    metadata=load_result("demo/trajectory.json")
    assert metadata["electrical_verified"]
    with (RESULTS/"demo/trajectory.csv").open(newline="",encoding="utf-8") as stream:
        rows=list(csv.DictReader(stream))
    previous=None
    for row in rows:
        x,y=float(row["x_mm"]),float(row["y_mm"])
        velocity=(float(row["vx_mm_s"]),float(row["vy_mm_s"]))
        assert abs(x)<=200+1e-7 and abs(y)<=120+1e-7
        assert math.hypot(*velocity)<=100+1e-7
        if previous:
            dt=float(row["time_s"])-float(previous["time_s"])
            old=(float(previous["vx_mm_s"]),float(previous["vy_mm_s"]))
            assert math.dist(old,velocity)/dt<=300+1e-5
        if row["state"]=="CHARGING":
            assert row["phone_present"]=="True"
            assert float(row["alignment_error_mm"])<=2
            assert velocity==(0.,0.)
            assert float(row["power_w"])>4.5
        else:
            assert float(row["power_w"])==0
        previous=row
    assert {"HOME","IDLE","POSITIONING","SETTLING","CHARGING","UNREACHABLE"}<={r["state"] for r in rows}


def test_real_fusion_motion_and_replay():
    validation=load_result("fusion/motion_validation.json")
    assert validation["passed"] and not validation["moving_interferences"]
    assert len(validation["samples"])==9
    assert max(r["error_mm"] for r in validation["samples"])<.01
    replay=load_result("fusion/replay.json")
    assert replay["passed"] and replay["trajectory_samples"]==560
    assert replay["maximum_position_error_mm"]<.01
