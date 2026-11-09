"""Pure calculations for native Fusion placement; no GUI or solver dependency."""
import math
from .common import nominal_gap
from .motion import placement_error, receiver_position


def checked_target(cfg, pose, limits=None):
    reason = placement_error(cfg, pose)
    if reason:
        raise ValueError(reason)
    target = receiver_position(cfg, pose)
    if limits is not None:
        for value, (lower, upper) in zip(target, limits):
            if not lower - 1e-8 <= value <= upper + 1e-8:
                raise ValueError("Receiver exceeds an existing Fusion slider limit")
    return target


def charging_check(cfg, power, tx, rx, *, stationary, stable_seconds, present=True):
    """Accept only measured alignment covered by the nominal aligned model."""
    result = {"state": "UNVERIFIED", "power_w": 0.0,
              "alignment_error_mm": None, "gap_mm": None,
              "reason": "Measured coil coordinates are unavailable"}
    if not present:
        return result | {"state": "IDLE", "reason": "Phone is not visible"}
    if len(tx) != 3 or len(rx) != 3 or not all(math.isfinite(v) for v in (*tx, *rx)):
        return result
    error = math.hypot(rx[0]-tx[0], rx[1]-tx[1])
    gap = rx[2]-tx[2]
    result.update(alignment_error_mm=error, gap_mm=gap)
    if not stationary:
        return result | {"state": "POSITIONING", "reason": "Transmitter disabled during motion"}
    if not math.isfinite(stable_seconds) or stable_seconds < cfg["mechanical"]["settle_s"]:
        return result | {"state": "SETTLING", "reason": "Waiting for a stationary placement"}
    # 2 mm is a positioning requirement, not permission to extrapolate the aligned
    # electrical model. Allow only 0.01 mm CAD numerical residual here.
    if error > min(.01, cfg["mechanical"]["alignment_tolerance_mm"]):
        return result | {"reason": "Measured offset is not covered by the aligned operating point"}
    if abs(gap-nominal_gap(cfg)) > .001:
        return result | {"reason": "Measured winding gap differs from the validated nominal gap"}
    if not power.available or not math.isfinite(power.watts) or power.watts <= 0:
        return result | {"reason": power.reason}
    return result | {"state": "CHARGING", "power_w": power.watts,
                     "reason": "Simulated power into the 5 ohm load; no Qi or battery model"}
