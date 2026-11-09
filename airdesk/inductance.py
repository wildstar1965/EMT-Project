"""Air-core circular-filament mutual inductance; SI internally.

Finite conductor self-inductance uses a thin round-wire approximation.
Neither routine models ferrite, metal eddy currents, or AC copper loss.
"""
import math
import numpy as np
from scipy.special import ellipk, ellipe

MU0 = 4e-7 * math.pi


def radii(coil):
    pitch = (coil["outer_radius_mm"] - coil["inner_radius_mm"]) / coil["turns"]
    return (coil["inner_radius_mm"] + pitch * (np.arange(coil["turns"]) + .5)) / 1000


def coaxial_mutual(a, b, separation):
    a, b = np.asarray(a), np.asarray(b)
    k2 = 4 * a * b / ((a + b)**2 + separation**2)
    if np.any(k2 >= 1):
        raise ValueError("Coincident filaments have singular mutual inductance")
    k = np.sqrt(k2)
    return MU0 * np.sqrt(a * b) * ((2 / k - k) * ellipk(k2) - 2 / k * ellipe(k2))


def coil_mutual(tx, rx, gap_mm):
    return float(coaxial_mutual(radii(tx)[:, None], radii(rx)[None, :], gap_mm / 1000).sum())


def self_inductance(coil):
    rs = radii(coil)
    equivalent_radius = math.sqrt(coil["strands"]) * coil["strand_diameter_mm"] / 2000
    value = sum(MU0 * r * (math.log(8 * r / equivalent_radius) - 2) for r in rs)
    for i, r in enumerate(rs):
        value += 2 * sum(float(coaxial_mutual(r, s, 0)) for s in rs[i + 1:])
    return value


def dc_resistance(coil):
    length = 2 * math.pi * radii(coil).sum()
    area = coil["strands"] * math.pi * (coil["strand_diameter_mm"] / 2000)**2
    return float(length / (58e6 * area))


def offset_mutual(tx, rx, gap_mm, offset_mm, segments=128):
    if gap_mm <= 0 or segments < 16:
        raise ValueError("Positive gap and at least 16 integration segments required")
    angle = (np.arange(segments) + .5) * (2 * math.pi / segments)
    unit = np.column_stack((np.cos(angle), np.sin(angle), np.zeros(segments)))
    tangent = np.column_stack((-np.sin(angle), np.cos(angle), np.zeros(segments)))
    shift = np.array([offset_mm / 1000, 0, gap_mm / 1000])
    dot = tangent @ tangent.T
    integral = 0.0
    for a in radii(tx):
        for b in radii(rx):
            distance = np.linalg.norm(a * unit[:, None, :] - (b * unit[None, :, :] + shift), axis=2)
            integral += a * b * np.sum(dot / distance)
    return float(MU0 / (4 * math.pi) * (2 * math.pi / segments)**2 * integral)
