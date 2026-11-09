# AirDesk validation report

Generated: 2026-11-06T13:27:01.953789+00:00

This report distinguishes the implemented simulation from physical-product qualification.

## Executed acceptance checks

| Check | Result |
|---|---|
| femm numerical checks | PASS |
| nominal electrical evidence | PASS |
| waveform crosscheck | PASS |
| field export | PASS |
| cad nine pose motion | PASS |
| fusion replay | PASS |
| final cad export | PASS |
| tests | PASS |

Tests: **16 total, 0 failures, 0 errors, 0 skipped**.

## Measured nominal electrical result

- Receiver output: **5.0148 V, 5.0297 W** into 5 Ω.
- DC-bus input: **6.0737 W** at 7.417969 V.
- Model DC-bus-to-load efficiency: **82.81%**.
- Power-balance residual: **0.0525%**.
- Output ripple: **47.77 mV peak-to-peak**.
- Tx / Rx RMS currents: **0.9016 / 1.1166 A**.
- Tx winding peak terminal voltage: **27.50 V**.
- Independent raw-waveform power crosscheck relative error: **5.24e-08**.

These results use assumed ferrite and device models. They exclude wall-adapter and gantry-motor power and do not establish Qi compatibility or thermal safety.

## Electromagnetic and mechanical checks

- FEMM cases executed: 25; field samples exported: 2640.
- Nominal aligned coupling: 0.527573 at 9.1 mm.
- Mesh / boundary / air-core comparison errors: 0.142% / 0.098% / 1.010%.
- Analytical central tabletop deflection: 0.442 mm.
- Clearance after analytical sag and 0.5 mm tolerance allowance: 1.058 mm.
- Fusion waypoint checks: 9; detected moving interferences: 0.
- Fusion trajectory samples: 560; maximum recorded XY error: 6.34979e-08 mm.
- Interference exclusions: fixed-subassembly mating overlaps, belts/clamps, cable envelopes, and phone internals.

## Sensitivity limits and outstanding hardware work

LTspice cases executed: 33. Numerically flagged sensitivity cases: 2.

| Flagged case | Gap | Frequency | Power-balance residual | Reason |
|---|---:|---:|---:|---|
| em_sweep_20 | 12.0 mm | 110 kHz | 2.973% | Power-balance residual is at least 2% |
| load_1000 | 9.1 mm | 150 kHz | 0.261% | Output-voltage change between measurement windows is at least 0.5%; not settled |

Flagged points retain their raw files but are not accepted operating points and cannot enable charging in the demo.

The 1 kΩ load study reaches about 40 V: the open-loop power stage needs regulation and protection before a physical receiver could use it. The 5 Ω nominal result is the sole enabled charging operating point.

The current BOM uses reference envelopes. A vendor motor torque-speed curve, physical coil measurements, component stress/rating selection, foreign-object protection, and thermal tests remain hardware qualification work.

## Reproducibility evidence

Raw solver files and their hashes are retained under `results/femm` and `results/ltspice`. The operating-point manifest also binds the current solver-source files. CAD stages export Fusion archives, STEP files, viewport images, and geometry reports. `results/demo/trajectory.csv` is the shared animation input. See the root README for exact commands.
