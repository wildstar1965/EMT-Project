from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "design.json"
RESULTS = ROOT / "results"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_config(path=CONFIG):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    if cfg.get("schema_version") != 1:
        raise ValueError("Unsupported configuration schema")
    for name in ("tx", "rx"):
        coil = cfg[name]
        if not 0 < coil["inner_radius_mm"] < coil["outer_radius_mm"]:
            raise ValueError(f"Invalid {name} coil radii")
        if int(coil["turns"]) != coil["turns"] or coil["turns"] <= 0:
            raise ValueError(f"Invalid {name} turn count")
    for group, fields in {
        "table": ["width_mm", "depth_mm", "thickness_mm"],
        "mechanical": ["x_travel_mm", "y_travel_mm", "speed_mm_s", "accel_mm_s2", "settle_s"],
        "electrical": ["load_ohm", "target_v", "supply_max_v"],
    }.items():
        if any(not math.isfinite(cfg[group][key]) or cfg[group][key] <= 0 for key in fields):
            raise ValueError(f"Invalid positive parameter in {group}")
    return cfg


def config_hash(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def nominal_gap(cfg):
    return (cfg["tx"]["thickness_mm"] / 2 + cfg["mechanical"]["top_clearance_mm"]
            + cfg["table"]["thickness_mm"] + cfg["phone"]["receiver_depth_mm"])


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def stamp(cfg, kind):
    return {"schema_version": 1, "kind": kind, "created_utc": datetime.now(timezone.utc).isoformat(),
            "config_sha256": config_hash(cfg)}


def artifact(path):
    path = Path(path).resolve()
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}


def artifacts_intact(items):
    try:
        return bool(items) and all(sha256(ROOT / p["path"]) == p["sha256"] for p in items)
    except (OSError, KeyError, ValueError):
        return False
