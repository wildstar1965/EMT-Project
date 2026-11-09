import copy
import math
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
import pytest
from airdesk.common import load_config
from airdesk.evidence import VerifiedPower
from airdesk.motion import PhonePose
from airdesk.native_tracking import checked_target, charging_check


def test_native_target_uses_rotated_receiver_offset_and_actual_joint_limits():
    cfg=copy.deepcopy(load_config())
    cfg["phone"]["receiver_offset_x_mm"]=15
    assert checked_target(cfg,PhonePose(20,30,90))==pytest.approx((20,45))
    with pytest.raises(ValueError,match="existing Fusion"):
        checked_target(cfg,PhonePose(20,30,90),[(-200,200),(-40,40)])


@pytest.mark.parametrize("pose",[PhonePose(201,0),PhonePose(0,121),PhonePose(280,160),PhonePose(float('nan'),0)])
def test_native_rejects_unreachable_or_unsupported_placement(pose):
    with pytest.raises(ValueError): checked_target(load_config(),pose)


def test_native_accepts_all_travel_corners_with_rotated_phone():
    cfg=load_config()
    for x in (-200,200):
        for y in (-120,120):
            assert checked_target(cfg,PhonePose(x,y,90))==pytest.approx((x,y))


@pytest.mark.parametrize("tx,rx,stationary,dwell,present",[
    ((0,0,-7.6),(0,0,1.5),False,.5,True),
    ((0,0,-7.6),(0,0,1.5),True,.49,True),
    ((0,0,-7.6),(1,0,1.5),True,.5,True),
    ((0,0,-7.6),(0,0,2),True,.5,True),
    ((0,0,-7.6),(0,0,1.5),True,.5,False),
    ((math.nan,0,-7.6),(0,0,1.5),True,.5,True),
])
def test_native_never_charges_outside_measured_nominal_conditions(tx,rx,stationary,dwell,present):
    power=SimpleNamespace(available=True,watts=5.,reason="test model")
    result=charging_check(load_config(),power,tx,rx,stationary=stationary,stable_seconds=dwell,present=present)
    assert result["state"]!="CHARGING" and result["power_w"]==0


def test_native_uses_actual_existing_evidence_and_rejects_missing_evidence():
    cfg=load_config()
    power=VerifiedPower(cfg)
    assert power.available,power.reason
    result=charging_check(cfg,power,(10,20,-7.6),(10,20,1.5),stationary=True,stable_seconds=.5)
    assert result["state"]=="CHARGING" and result["power_w"]==power.watts
    with patch.object(Path,"read_text",side_effect=FileNotFoundError("Missing operating-point evidence")):
        missing=VerifiedPower(cfg)
    result=charging_check(cfg,missing,(10,20,-7.6),(10,20,1.5),stationary=True,stable_seconds=.5)
    assert result["state"]=="UNVERIFIED" and result["power_w"]==0
