import json
import math
from .common import RESULTS, config_hash, nominal_gap, artifacts_intact


class VerifiedPower:
    def __init__(self, cfg, path=None):
        self.available, self.watts = False, 0.
        self.reason = "Electrical simulation not verified"
        self.model = "No verified model"
        self.data = None
        try:
            data = json.loads((path or RESULTS / "operating_point.json").read_text(encoding="utf-8"))
            if data.get("config_sha256") != config_hash(cfg):
                raise ValueError("Electrical results are stale for this configuration")
            if not data.get("executed") or not data.get("passed"):
                raise ValueError("Electrical operating point has not passed acceptance")
            if not artifacts_intact(data.get("artifacts", [])):
                raise ValueError("Electrical evidence is missing or has changed")
            if abs(data["gap_mm"] - nominal_gap(cfg)) > 1e-8 or data["offset_mm"] != 0:
                raise ValueError("Operating point does not match the aligned nominal gap")
            nominal, e = data["nominal"], cfg["electrical"]
            measured = nominal["measurements"]
            if (not nominal["settled"] or nominal["energy_balance_relative_error"] >= .02
                or not 0 < nominal["efficiency"] < 1 or nominal["load_ohm"] != e["load_ohm"]
                or abs(measured["vout"] / e["target_v"] - 1) > e["voltage_tolerance_fraction"]
                or not 4.5 <= measured["pout"] <= 5.6):
                raise ValueError("Nominal operating point is outside the accepted electrical envelope")
            self.watts, self.available = measured["pout"], True
            self.model, self.reason, self.data = data["model"], "Verified simulated operating point", data
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.reason = str(exc)
