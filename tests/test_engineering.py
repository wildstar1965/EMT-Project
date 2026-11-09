import math
import pytest
from airdesk.common import load_config, nominal_gap
from airdesk.mechanics import plate_deflection
from airdesk.inductance import coil_mutual, offset_mutual, self_inductance


def test_gap_and_plate_convergence():
    cfg = load_config()
    assert nominal_gap(cfg) == pytest.approx(9.1)
    a, b = plate_deflection(cfg, 49), plate_deflection(cfg, 99)
    assert abs(a["total_mm"] - b["total_mm"]) < .001
    assert 0.40 < b["total_mm"] < .49


def test_mutual_inductance_independent_formulations_and_reciprocity():
    cfg = load_config()
    tx, rx = cfg["tx"], cfg["rx"]
    exact = coil_mutual(tx, rx, 9.1)
    numerical = offset_mutual(tx, rx, 9.1, 0, 64)
    assert numerical == pytest.approx(exact, rel=1e-5)
    assert coil_mutual(rx, tx, 9.1) == pytest.approx(exact, rel=1e-12)
    assert 0 < exact / math.sqrt(self_inductance(tx) * self_inductance(rx)) < 1
    assert coil_mutual(tx, rx, 12) < exact


def test_offset_symmetry_and_far_field():
    cfg = load_config()
    args = cfg["tx"], cfg["rx"], 9.1
    assert offset_mutual(*args, 15, 64) == pytest.approx(offset_mutual(*args, -15, 64), rel=1e-10)
    assert abs(offset_mutual(*args, 150, 64)) < coil_mutual(*args) / 100
