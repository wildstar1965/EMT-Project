# Tool installation and authoritative references

Tools were installed and tested on this machine during implementation. The Python virtual environment is local to this project; `requirements-lock.txt` records its exact packages.

| Tool | Verification |
|---|---|
| Autodesk Fusion | Installed build 2706.1.17; official API executed in the desktop application; 10 mm cube measured as 1 cm³ |
| FEMM | Official 4.2 x64 22-Oct-2023 installer; COM driven by pyFEMM; actual `.fem` / `.ans` files retained |
| LTspice | Official x64 MSI, installed version 26.1.1; valid Analog Devices International UC signature; RC reference measured 0.632120370509 at one time constant |
| Python | 3.14.5; NumPy, SciPy, Matplotlib, Pillow, pytest, pyFEMM and pywin32 installed in `.venv` |

Downloaded FEMM installer SHA-256, matched to the publisher's checksum:

`fdc5047d2fccc4d759df2a82c4627e46408250c57967773fb5bd59cd9eb17253`

Downloaded LTspice MSI SHA-256:

`f22163f15420e43a2d5c66440e038ef031a9f019a181f396b95edcef5eebc357`

The installer hashes are also recorded in `results/installer_hashes.json`.

Primary references:

- [Autodesk Fusion API manual](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/UserManualIndex_UM.htm)
- [Fusion internal units](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Units_UM.htm)
- [Slider joint drive property](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_SliderJointMotion_slideValue.htm)
- [FEMM 4.2 download and checksum links](https://www.femm.info/doku/doku.php?id=download)
- [pyFEMM COM interface](https://www.femm.info/doku/doku.php?id=pyfemm)
- [FEMM inductance methodology](https://www.femm.info/doku/doku.php?id=inductanceexample)
- [LTspice download](https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html)
- [Analog Devices LTspice batch and file formats](https://analogdevicesinc.github.io/ltspice-reference/ai_ref/LTSPICE-QUICKSTART.html)

FEMM's bitmap export proved unstable in this Windows session. The project instead samples the solved field through the official postprocessor interface and plots that data in Python. No field image is synthesized independently of the solution.
