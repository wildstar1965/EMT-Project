# AirDesk — Intelligent Wireless Charging Desk

A working simulation of a 600 × 400 mm desk demonstrator: place a virtual phone, move a two-motor Cartesian gantry underneath its receiver, and show charging only when matching FEMM/LTspice evidence passes validation.

## Start here

**For phone placement directly inside Fusion:** load the `fusion/AirDeskNative` add-in, click **Place Phone**, select the tabletop, and click **Move phone**. The existing joints align the coil and a Fusion panel displays measured alignment and validated simulated power. See the [native Fusion guide](docs/NATIVE_FUSION.md) for installation, actual test evidence, and the limits of ordinary viewport dragging.

The original standalone demonstration and replay remain available below.

Open PowerShell in this folder and launch the interactive demonstration:

```powershell
.\.venv\Scripts\python.exe -m airdesk demo
```

You can also double-click **Start-AirDesk.cmd**.

Click or drag in the top view to place/move the phone. Scroll to rotate it. Press **R** to remove it and **S** to save an interactive trajectory. The marked 400 × 240 mm area limits receiver-centre travel; the whole phone must also fit on the tabletop. Moving the phone immediately disables charging. A new target arriving during a move is queued until the current acceleration-limited move stops.

The shown watts are **simulated power into a 5 Ω equivalent load**, not battery charging or a Qi connection. Missing, changed, or failed electrical evidence gives **UNVERIFIED**, never a fabricated successful charging indication.

Ready-to-review outputs:

- [Interactive-demo animation](results/demo/tracking.gif) and [preview](results/demo/preview.png).
- [Fusion 3D animation](results/fusion/tracking_3d.gif).
- [Final Fusion assembly](results/fusion/04_final.f3d) and [STEP export](results/fusion/04_final.step).
- [Validation report](docs/VALIDATION.md), [design architecture](docs/ARCHITECTURE.md), and [preliminary BOM](docs/BOM.csv).
- [Electrical waveforms and losses](results/plots/electrical.png), [FEMM field](results/femm/field.png), and [gap sweep](results/plots/coupling_gap.png).

## Reproduce the numerical stages

The checked installation uses Windows, Python 3.14.5, FEMM 4.2 x64, and LTspice 26.1.1. Exact Python package versions are in `requirements-lock.txt`. To create a new environment:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

FEMM and LTspice are separate desktop installations. FEMM must register its COM interface. `AIRDESK_LTSPICE` can override the detected executable path. See [tool provenance](docs/TOOL_PROVENANCE.md).

Run these stages in order from the repository root:

```powershell
.\.venv\Scripts\python.exe -m airdesk environment
.\.venv\Scripts\python.exe -m airdesk mechanics
.\.venv\Scripts\python.exe -m airdesk spice-smoke
.\.venv\Scripts\python.exe -m airdesk femm --full
.\.venv\Scripts\python.exe -m airdesk femm --fields-only
.\.venv\Scripts\python.exe -m airdesk offset
.\.venv\Scripts\python.exe -m airdesk spice --full
.\.venv\Scripts\python.exe -m airdesk plots
.\.venv\Scripts\python.exe -m airdesk demo --export --gif
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Each command writes actual results into `results/`. A generated `.fem` or `.cir` file alone is not accepted as proof of execution: the workflow retains `.ans`, `.raw`, `.log`, measurements, and hashes. Non-passing solver acceptance returns a nonzero exit code. Re-running upstream stages can invalidate downstream hashes; regenerate the dependent stages in order.

Write the test record and rebuild the validation report after the Fusion stages:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --junitxml=results/tests.xml
.\.venv\Scripts\python.exe -m airdesk report
```

`Run-AirDesk.ps1` is an optional wrapper for environments that permit PowerShell scripts. This machine's execution policy blocks `.ps1` launchers; the direct Python commands and `.cmd` launcher work without changing that policy.

## Run the Fusion stages

**Fusion scripts must run inside Fusion, not ordinary Python.** Open Fusion and its Design workspace. The smoke script creates a separate document and saves a 10 mm cube plus its measured dimensions.

Use **Utilities → Scripts and Add-Ins → add from device** to add `fusion/00_Smoke`, then run it. Add `fusion/AirDeskRunner` for the remaining stages. Alternatively open **Text Commands** with **Ctrl+Alt+C**, select **Txt**, and enter a command like this, replacing the path if needed:

```text
Python.RunScript "C:/Users/tejar/OneDrive/Desktop/AIrdesk/fusion/00_Smoke/00_Smoke.py"
```

For each stage below, put its stage name in `config/fusion_stage.txt` and run `fusion/AirDeskRunner/AirDeskRunner.py` using the same method:

| Stage name | Action | Acceptance evidence |
|---|---|---|
| `frame` | Creates a new AirDesk document; builds frame, tabletop, and guide supports | `results/fusion/01_frame.json`, `.f3d`, `.step`, `.png` |
| `gantry` | Adds moving assemblies, coils, phone, motors, and transmission envelopes to that document | `02_gantry.json` and geometry exports |
| `joints` | Creates two sliders, two motor revolutes, and two belt motion links; checks nine travel poses | `motion_validation.json`, `03_assembly.*` |
| `replay` | Replays the generated demonstration and checks actual coil positions at each sample | `replay.json`, `replay_frames/`, `04_final.*` |

Keep the AirDesk document active during later stages. Do not interact with Fusion while a stage is running. A failed stage writes `last_error.json`; successful completion clears it. `last_run.json` reports the latest stage's status. To rebuild geometry after changing dimensions, start with `frame` in a new document. Running `gantry` twice on an existing gantry is intentionally rejected.

After a successful replay, make the animated 3D artifact:

```powershell
.\.venv\Scripts\python.exe -m airdesk cad-gif
```

The Fusion stages are separate scripts with a small shared API library; the runner only dispatches them. Existing user designs are not overwritten. All project archives are local exports; cloud saving is unnecessary.

## Interpretation and limits

- The nominal circuit has an **open-loop DC bus tuned for the specified load**. It is not a regulated charger. The measured light-load voltage rise demonstrates the need for regulation, overvoltage protection, and Qi-compatible control in a physical build.
- FEMM is axisymmetric. The offset study is a separately labelled air-core filament approximation; it does not validate laterally displaced ferrite-backed coils or the effect of nearby gantry metal.
- Ferrite properties, semiconductor models, and extra winding losses are engineering assumptions. Reported efficiency is DC-bus-to-load model efficiency; wall-adapter and positioning-motor power are excluded.
- CAD uses simplified extrusions, bearing envelopes, concentric winding envelopes, belt runs, and cable clearances. Motor running torque, real bearing/fastener selection, tolerances, thermal behavior, and furniture loads are not physically qualified.
- All geometry uses Z-up and millimetres externally; the Fusion adapter converts to centimetres. Major dimension changes require rechecking the reference mount layout and all clearances.
- The desktop helper under `tools/` was used to launch official API scripts during development. It relies on the inspected UI layout; normal use should follow the Fusion script instructions above.
