import copy
import math
from types import SimpleNamespace
import pytest
from pathlib import Path
from airdesk.common import load_config
from airdesk.motion import Controller, Move, PhonePose, placement_error, receiver_position
from airdesk.evidence import VerifiedPower


def advance(controller, seconds, dt=.01):
    for _ in range(round(seconds / dt)):
        controller.step(dt)


def test_rotated_receiver_offset_and_support():
    cfg = copy.deepcopy(load_config())
    cfg["phone"]["receiver_offset_x_mm"] = 10
    assert receiver_position(cfg, PhonePose(0, 0, 90)) == pytest.approx((0, 10))
    assert not placement_error(cfg, PhonePose(0, 0))
    assert placement_error(cfg, PhonePose(230, 0))
    assert placement_error(cfg, PhonePose(0, 120, 45))
    assert placement_error(cfg, PhonePose(float("nan"), 0))


@pytest.mark.parametrize("end", [(0, 0), (.1, .1), (400, 240), (0, 240), (400, 0)])
def test_profiles_obey_speed_acceleration_and_endpoints(end):
    move = Move((0, 0), end, 100, 300)
    assert move.sample(0)[0] == (0, 0)
    assert move.sample(move.duration)[0] == end
    assert move.sample(move.duration)[1] == (0, 0)
    previous = (0., 0.)
    for tick in range(1, math.ceil(move.duration / .001) + 1):
        _, velocity = move.sample(tick * .001)
        assert math.hypot(*velocity) <= 100 + 1e-8
        assert math.dist(previous, velocity) / .001 <= 300 + 1e-5
        previous = velocity
    assert move.duration + .5 < 6


def test_missing_evidence_never_charges():
    cfg = load_config()
    c = Controller(cfg, VerifiedPower(cfg, Path(__file__).parent / "intentionally_missing.json"))
    c.place(PhonePose(0, 0))
    advance(c, 8)
    assert c.state == "UNVERIFIED" and c.watts == 0


def test_removal_relocation_and_invalid_placement_disable_immediately():
    # Explicit test double; never written into the project's solver evidence.
    c = Controller(load_config(), SimpleNamespace(available=True, watts=5.0))
    c.place(PhonePose(0, 0))
    advance(c, 8)
    assert c.state == "CHARGING" and c.watts == 5
    c.place(PhonePose(100, 50))
    assert c.watts == 0
    advance(c, .4)
    old_velocity = c.velocity
    c.place(PhonePose(-100, -50))
    c.step(.01)
    assert math.dist(old_velocity, c.velocity) / .01 <= 300 + 1e-5
    advance(c, 10)
    assert c.position == pytest.approx((-100, -50)) and c.state == "CHARGING"
    c.place(None)
    assert c.watts == 0
    c.step(.01)
    assert c.state == "IDLE"
    c.place(PhonePose(250, 0))
    advance(c, 1)
    assert c.state == "UNREACHABLE" and c.watts == 0
