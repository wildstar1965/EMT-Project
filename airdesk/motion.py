"""Rest-to-rest Cartesian motion and explicit simulated phone sensing."""
from __future__ import annotations
from dataclasses import dataclass
import math
from .common import nominal_gap


@dataclass(frozen=True)
class PhonePose:
    x_mm: float
    y_mm: float
    yaw_deg: float = 0.0


def receiver_position(cfg, pose):
    angle = math.radians(pose.yaw_deg)
    dx, dy = (cfg["phone"][k] for k in ("receiver_offset_x_mm", "receiver_offset_y_mm"))
    return (pose.x_mm + math.cos(angle) * dx - math.sin(angle) * dy,
            pose.y_mm + math.sin(angle) * dx + math.cos(angle) * dy)


def phone_corners(cfg, pose):
    angle = math.radians(pose.yaw_deg)
    a, b = cfg["phone"]["width_mm"] / 2, cfg["phone"]["length_mm"] / 2
    return [(pose.x_mm + math.cos(angle) * x - math.sin(angle) * y,
             pose.y_mm + math.sin(angle) * x + math.cos(angle) * y)
            for x, y in ((-a, -b), (a, -b), (a, b), (-a, b))]


def placement_error(cfg, pose):
    if not all(math.isfinite(v) for v in (pose.x_mm, pose.y_mm, pose.yaw_deg)):
        return "Non-finite phone coordinates"
    t, m = cfg["table"], cfg["mechanical"]
    if any(abs(x) > t["width_mm"] / 2 + 1e-9 or abs(y) > t["depth_mm"] / 2 + 1e-9
           for x, y in phone_corners(cfg, pose)):
        return "Phone footprint extends beyond the tabletop"
    x, y = receiver_position(cfg, pose)
    if abs(x) > m["x_travel_mm"] / 2 + 1e-9 or abs(y) > m["y_travel_mm"] / 2 + 1e-9:
        return "Receiver is outside the reachable charging area"
    return ""


class Move:
    def __init__(self, start, end, speed, acceleration):
        self.start, self.end = tuple(start), tuple(end)
        self.distance = math.dist(start, end)
        self.accel = acceleration
        if self.distance == 0:
            self.ramp = self.cruise = self.duration = self.peak_speed = 0.
        else:
            self.ramp = min(speed / acceleration, math.sqrt(self.distance / acceleration))
            self.peak_speed = acceleration * self.ramp
            self.cruise = max(0., (self.distance - acceleration * self.ramp**2) / self.peak_speed)
            self.duration = 2 * self.ramp + self.cruise

    def sample(self, time_s):
        t = min(max(time_s, 0.), self.duration)
        if t >= self.duration:
            return self.end, (0., 0.)
        if t < self.ramp:
            s, v = .5 * self.accel * t**2, self.accel * t
        elif t < self.ramp + self.cruise:
            s = .5 * self.accel * self.ramp**2 + self.peak_speed * (t - self.ramp)
            v = self.peak_speed
        else:
            remaining = self.duration - t
            s, v = self.distance - .5 * self.accel * remaining**2, self.accel * remaining
        unit = [(b - a) / self.distance for a, b in zip(self.start, self.end)]
        return tuple(a + u * s for a, u in zip(self.start, unit)), tuple(u * v for u in unit)


class Controller:
    def __init__(self, cfg, power=None):
        self.cfg, self.power = cfg, power
        m = cfg["mechanical"]
        self.position = (-m["x_travel_mm"] / 2, -m["y_travel_mm"] / 2)
        self.velocity = (0., 0.)
        self.phone = None
        self.time = 0.
        self.move = None
        self.move_start = self.stable_since = self.arrived_at = 0.
        self.state = "HOME"
        self.reason = "Virtual homing: reference position is assumed, not sensed hardware"
        self.watts = 0.
        self.energy_wh = 0.

    def place(self, pose):
        if pose != self.phone:
            self.phone = pose
            self.stable_since = self.time
            self.watts = 0.
            self.state = "POSITIONING" if self.move else "IDLE"
            self.reason = "Phone changed; transmitter disabled"

    def step(self, dt):
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("Positive finite time step required")
        self.time += dt
        self.watts = 0.
        if self.time < .5:
            self.state = "HOME"
            return self.snapshot()
        # A changed target is queued until the current rest-to-rest move stops.
        # This preserves bounded acceleration; it never snaps velocity to zero.
        if self.move:
            self.position, self.velocity = self.move.sample(self.time - self.move_start)
            if self.time - self.move_start < self.move.duration:
                self.state, self.reason = "POSITIONING", "Transmitter disabled during motion"
                return self.snapshot()
            self.move = None
            self.arrived_at = self.time
        if self.phone is None:
            self.state, self.reason = "IDLE", "Place a phone within the charging area"
            return self.snapshot()
        error = placement_error(self.cfg, self.phone)
        if error:
            self.state, self.reason = "UNREACHABLE", error
            return self.snapshot()
        target = receiver_position(self.cfg, self.phone)
        if math.dist(target, self.position) > 1e-7:
            m = self.cfg["mechanical"]
            self.move = Move(self.position, target, m["speed_mm_s"], m["accel_mm_s2"])
            self.move_start = self.time
            self.state, self.reason = "POSITIONING", "Moving to receiver coil centre"
        elif self.time - max(self.arrived_at, self.stable_since) < self.cfg["mechanical"]["settle_s"]:
            self.state, self.reason = "SETTLING", "Waiting for a stable, stationary placement"
        elif self.power and self.power.available:
            # Only the exactly aligned nominal-gap model has an approved power point.
            self.watts = self.power.watts
            self.state = "CHARGING"
            self.reason = "Simulated power into the 5 ohm receiver load; no Qi protocol"
            self.energy_wh += self.watts * dt / 3600
        else:
            self.state = "UNVERIFIED"
            self.reason = self.power.reason if self.power else "No validated electrical operating point loaded"
        return self.snapshot()

    def snapshot(self):
        target = receiver_position(self.cfg, self.phone) if self.phone else (None, None)
        return {"time_s": self.time, "x_mm": self.position[0], "y_mm": self.position[1],
                "vx_mm_s": self.velocity[0], "vy_mm_s": self.velocity[1], "state": self.state,
                "phone_present": self.phone is not None,
                "phone_x_mm": self.phone.x_mm if self.phone else None,
                "phone_y_mm": self.phone.y_mm if self.phone else None,
                "phone_yaw_deg": self.phone.yaw_deg if self.phone else None,
                "receiver_x_mm": target[0], "receiver_y_mm": target[1],
                "alignment_error_mm": math.dist(self.position, target) if self.phone else None,
                "power_w": self.watts, "energy_wh": self.energy_wh, "reason": self.reason}
