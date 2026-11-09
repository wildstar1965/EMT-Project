# AirDesk reference architecture

The approved first version is a simulation of one face-up phone on a 600 × 400 × 200 mm demonstrator. The tabletop is 5 mm acrylic, supported by 2020 extrusion. Receiver-centre travel is X ±200 mm and Y ±120 mm. The entire rotated phone footprint must remain supported.

## Data and control

`config/design.json` is the shared source for mechanical envelopes, coil geometry, assumed materials, motion limits, and electrical targets. Geometry and UI use millimetres. Inductance integration and SPICE use SI units. Fusion converts length to its internal centimetres.

Phone pose plus a rotated receiver offset produces the XY target. The controller performs virtual homing, synchronized rest-to-rest moves with 100 mm/s maximum speed and 300 mm/s² acceleration, and a 0.5 s stationary dwell. A new target during motion waits for a controlled stop at the previous target; transmitter power is disabled immediately. Removal and invalid placement also disable power.

FEMM solves the aligned coil pair and supplies inductance, coupling, and terminal-loss approximations to LTspice. LTspice tunes the nominal DC supply below 12 V and validates the approximately 5 V / 5 W point into 5 Ω. Installed compensation capacitors remain fixed in gap/frequency/material sweeps. A hashed operating-point manifest enables the simulated charging indication only for the exactly aligned nominal geometry. Off-axis plots do not unlock charging.

The scripted trajectory is exported as CSV plus metadata. Python provides interactive placement and an animation; Fusion drives real slider joints and replays the same file, measuring actual transmitter and receiver positions. The 3D GIF consists of captured Fusion frames with trace-derived annotations.

## Mechanical arrangement

- Grounded frame and fixed guide supports.
- One travelling bridge on two Y guides, synchronized by two GT2 belts on a common shaft.
- One X carriage on the bridge, carrying a nonconductive plate, ferrite, and transmitter winding.
- Two motor revolute joints linked to the two sliders at 40 mm travel per revolution (20 teeth × 2 mm pitch).
- A dropped X motor mount and extension shaft avoid collision with the fixed Y guide support. The extension needs bearing/coupling detail before manufacture.
- Coil-plane stack: 0.6 mm Tx half-thickness + 2 mm air clearance + 5 mm tabletop + 1.5 mm receiver depth = 9.1 mm.
- Rx ferrite faces into the phone; Tx ferrite faces toward the gantry. Phone pose is an externally supplied placement, not a third powered desk axis.

The preliminary plate calculation gives about 0.442 mm central sag under self-weight plus a 250 g phone, with a further 0.5 mm tolerance allowance. The illustrative motor requirement is about 0.079 N·m running torque at 150 rpm including a factor of two margin. These use assumed mass and drag; a selected motor torque curve and physical structure are not qualified.

## Model simplifications

The electromagnetic model contains axisymmetric winding packs, assumed ferrite permeability/loss angle, and an air boundary. Copper/litz terminal losses are modeled; mutual dissipative impedance is reported but omitted in the reduced coupled-inductor circuit. The circuit includes switch conduction, output capacitance/body diodes, winding losses, capacitor ESR, Schottky rectifier losses, and an assumed driver load. It does not include manufacturer-specific gate-drive dynamics, a Qi stack, a battery, or phone metal geometry.

The detailed FEMM gap sweep is a coil-separation study; gaps smaller than the nominal desk stack are sensitivity cases, not physically reachable heights for this tabletop. The offset model is air-core only. The CAD interference check excludes fixed mating overlaps, belt/clamp contacts, cable envelopes, and phone internals, and samples nine positions rather than proving continuous swept-volume clearance.

## Milestones and interfaces

1. Tool smoke tests with actual measured outputs.
2. Mechanical estimate and electromagnetic/circuit feasibility gate.
3. Frame and gantry as separately tested Fusion scripts.
4. Slider joints, motor links, and measured placement checks.
5. FEMM convergence, boundary, material, gap/frequency, and offset studies.
6. LTspice nominal tuning and sensitivity sweeps with power accounting.
7. Interactive demo, replay, animations, and reproducibility report.

JSON files include schema version, UTC creation time, configuration hash, and model identity. Artifact references include paths and SHA-256 hashes. CSV column names include physical units. The solver artifacts and measurements are authoritative; appearance changes and animation timing do not constitute electrical evidence.
