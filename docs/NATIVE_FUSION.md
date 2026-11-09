# Native Fusion phone placement

AirDesk now includes the **Place Phone** Fusion add-in. All placement interaction and status display happen inside Fusion. It uses the existing Phone occurrence, X_Position and Y_Position sliders, motor motion links, and validated FEMM/LTspice operating point. No frame, gantry, motor, or coil is rebuilt.

## Install and run

1. Open the existing AirDesk design, or open `results/fusion/04_final.f3d` using **File > Open > Open from my computer**. Make the AirDesk root component active.
2. Open **Utilities > Add-Ins > Scripts and Add-Ins**. In the **Add-Ins** tab, choose **add from device** / the green plus, and select the `fusion/AirDeskNative` folder.
3. Select **AirDeskNative**, click **Run**, and optionally enable **Run on Startup**. The AirDesk charging status panel appears inside Fusion.
4. Click **Place Phone** in that panel. It is also registered in the Design workspace's Add-Ins panel and command search (**S**, search `Place Phone`).
5. Click the **top face** of the transparent tabletop at the desired phone centre. The command fills Phone X and Phone Y from the actual selected 3D point. You may enter exact X/Y values and an in-plane rotation instead.
6. Read the placement check and click **Move phone**. The phone moves, the original slider joints animate the transmitter into alignment, and the status panel displays measured alignment, gap, and simulated power after settling.

To choose a different point before committing, clear the existing tabletop selection using its selection-input clear control, then select again. **Cancel** and Escape leave the assembly unchanged because no geometry changes are made while collecting inputs. Keep the desktop idle during the short motion animation.

The selected point is the **phone body centre**. The receiver offset is rotated with the phone before calculating the carriage target. The current configuration has a centred receiver. The complete rotated phone footprint must be supported; both configured travel and the actual Fusion joint limits are enforced.

An alternative startup method, already tested on this installation, is to open Fusion **Text Commands** with **Ctrl+Alt+C**, select **Txt**, and enter:

```text
Python.RunScript "C:/Users/tejar/OneDrive/Desktop/AIrdesk/fusion/AirDeskNative/AirDeskNative.py"
```

Use the Add-Ins tab to stop the add-in. Stopping it removes its command and status panel; the mechanical assembly remains intact. Do not run the module with external Python: `adsk` is provided by Fusion.

## Status and electrical evidence

- **POSITIONING / SETTLING:** zero transmitter power is shown.
- **SIMULATED CHARGING:** the measured Tx/Rx centres match the aligned operating point, the nominal gap matches, settling has completed, and `VerifiedPower` has checked the operating-point and solver artifact hashes.
- **UNVERIFIED:** no applicable evidence, another model command, a changed viewport selection, or a different active document. Run Place Phone again to perform a fresh check.
- **PLACEMENT REJECTED:** the command disables Move phone for an unsupported footprint or unreachable target.

The status is the last completed placement check, with its timestamp and a collapsible **Result source** showing the operating-point path and SHA256. Evidence is reloaded on every placement. It is not a background electromagnetic solver or a monitor for arbitrary external API edits. Changes outside the add-in should be followed by another placement check.

The 2 mm alignment requirement does not authorize extrapolation of the centred electrical model. The native command requires a CAD alignment residual no greater than 0.01 mm and a nominal-gap residual no greater than 0.001 mm before showing watts. The demonstrated nominal result is approximately 5.03 W into a 5 ohm equivalent load. It does not establish real-phone/Qi charging.

## Why ordinary dragging is not enabled

The official API exposes mouse/drag events on an add-in's own **Command**. These are not a general occurrence-transform-changed event for Fusion's ordinary Move or Select tools. The installed API's Occurrence interface does not expose a documented continuous transform-change event. The existing Phone is grounded, and persistent placement uses a timeline-aware `initialTransform` edit. Ungrounding it and polling or altering the timeline while Fusion's own drag tool solves the assembly would need a separate reliability study.

This implementation therefore uses the requested fallback: a native placement command with a bounded joint animation. It does not claim continuous tracking during ordinary viewport occurrence dragging.

Official API references checked for this implementation:

- [Command and mouse events](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Command.htm)
- [Command.select and its selection point](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Command_select.htm)
- [Selection.point](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Selection_point.htm)
- [Occurrence.initialTransform](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Occurrence_initialTransform.htm)
- [Occurrence API interface](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Occurrence.htm)
- [Native Fusion palettes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Palettes_add.htm)

## Preservation and replay fallback

The add-in changes only the Phone's persistent placement/visibility and drives the existing sliders. It checks component/body inventory, body volumes, joint connections/types/suppression, motor-link inventory, and slider limits before and after a move. A failed motion restores the captured phone pose and joint values. No appearance/material changes are required.

Fusion's driven slider positions can be transient until captured. If Fusion displays **Capture Position** when saving or after other modelling operations, use its normal Capture Position control to retain the current joint pose; re-run Place Phone after other edits to verify alignment again. Original `.f3d` and `.step` deliverables are not overwritten by this add-in.

The existing `config/fusion_stage.txt` and the `frame`, `gantry`, `joints`, and **replay** workflows remain unchanged. To use replay, cancel Place Phone, stop AirDeskNative, and run the existing AirDeskRunner with `replay` selected. Replay still reads the original generated trajectory. Native placement does not require any CSV or external GUI.

## Executed tests and reproduction

On Fusion **2706.1.17**, the native API self-test executed six valid poses (centre, four travel corners, and a rotated interior pose), rejected three invalid placements, rejected missing operating-point evidence, and restored the original assembly pose and structure. Actual viewport clicks were also exercised through the command and produced `interaction_source: tabletop_selection` in the saved command result. See `results/fusion/native/selftest.json` and `last_command.json` for measured coordinates.

The final viewport test placed the phone at **X -58.3515 mm, Y -79.6133 mm**. Measured alignment error was **4.04 × 10⁻⁸ mm**, with a **9.1 mm** gap and **5.0297 W** from the existing validated model. The status panel remained available after execution. The [acceptance record](../results/fusion/native/acceptance.json) binds source/result hashes; the [actual Fusion screenshot](../results/fusion/native/acceptance.png) shows the completed placement and status.

The independent Python suite passed **29 tests**, including rotated receiver offsets, actual joint-limit restrictions, and refusal to display charging for motion, insufficient dwell, lateral misalignment, wrong gap, absent phone, non-finite geometry, or missing evidence. Its record is `results/native_tests.xml`.

Run the Python checks from the workspace:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --junitxml=results/native_tests.xml
```

To repeat the CAD self-test, stop the add-in, keep the existing AirDesk design active, add `fusion/05_NativeTest` as a **Script**, and run it. It first exports a timestamped backup under `results/fusion/native/`, then restores the original pose after testing. A failed test writes its exception into `selftest.json`; it does not report success without passing the measurements.

Native implementation files are deliberately separate: `airdesk/native_tracking.py` contains testable calculations, `fusion/native_motion.py` drives/measures the existing CAD, and `fusion/native_command.py` implements the command and retained event handlers. The add-in entry point and status HTML are in `fusion/AirDeskNative`.
