import json
import re
from pathlib import Path
import numpy as np
from .common import RESULTS, stamp, write_json


def read_raw(path):
    raw=Path(path).read_bytes()
    encoding="utf-16-le" if raw[:2]==b"T\x00" else "utf-8"
    marker="Binary:\n".encode(encoding)
    at=raw.find(marker)
    if at<0: raise ValueError("Expected LTspice transient binary .raw format")
    header=raw[:at].decode(encoding)
    nvar=int(re.search(r"No. Variables:\s*(\d+)",header).group(1))
    npoint=int(re.search(r"No. Points:\s*(\d+)",header).group(1))
    names=re.findall(r"^\s*\d+\s+(\S+)\s+\S+\s*$",header,re.M)
    if len(names)!=nvar or "complex" in header or "FastAccess" in header:
        raise ValueError("Unsupported raw layout (requires ordinary real transient data)")
    data=raw[at+len(marker):]
    dtype=np.dtype([("time","<f8"),("values","<f4",(nvar-1,))])
    if len(data)!=npoint*dtype.itemsize:
        dtype=np.dtype([("time","<f8"),("values","<f8",(nvar-1,))])
    if len(data)!=npoint*dtype.itemsize: raise ValueError("Unexpected raw byte count")
    rows=np.frombuffer(data,dtype=dtype,count=npoint)
    return {names[0].lower():rows["time"],**{name.lower():rows["values"][:,i] for i,name in enumerate(names[1:])}}


def report_plots(cfg):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    folder=RESULTS/"plots";folder.mkdir(parents=True,exist_ok=True)
    em=json.loads((RESULTS/"femm"/"study.json").read_text(encoding="utf-8"))
    cases=[r for r in em["cases"] if r["frequency_hz"]==150000 and (r["name"].startswith("gap_") or r["name"]=="nominal_ac")]
    cases.sort(key=lambda r:r["gap_mm"])
    fig,ax=plt.subplots(figsize=(8,4))
    ax.plot([r["gap_mm"] for r in cases],[r["k"] for r in cases],"o-")
    ax.set(xlabel="Winding-plane separation (mm)",ylabel="Coupling coefficient k",title="FEMM aligned ferrite-backed coils · assumed material")
    ax.grid(alpha=.25);fig.tight_layout();fig.savefig(folder/"coupling_gap.png",dpi=160);plt.close(fig)
    raw=read_raw(RESULTS/"ltspice"/"nominal.raw")
    t=raw["time"];vout=raw["v(outp)"]-raw["v(outn)"]
    op=json.loads((RESULTS/"operating_point.json").read_text(encoding="utf-8"))
    m=op["nominal"]["measurements"]
    fig,axes=plt.subplots(2,2,figsize=(11,7))
    axes[0,0].plot(t*1000,vout)
    axes[0,0].set(xlabel="Time (ms)",ylabel="Receiver output (V)",title="Startup into 5 Ω load")
    mask=(t>=.00794)&(t<=.008)
    axes[0,1].plot((t[mask]-.00794)*1e6,raw["i(ltx)"][mask],label="Transmitter")
    axes[0,1].plot((t[mask]-.00794)*1e6,raw["i(lrx)"][mask],label="Receiver")
    axes[0,1].set(xlabel="Time within settled window (µs)",ylabel="Winding current (A)",title="Actual LTspice waveforms")
    axes[0,1].legend()
    labels=["Winding/core","Capacitors","Switch conduction","Rectifier","Body diodes","Driver load"]
    keys=["copper_core_loss","capacitor_loss","switch_loss","rectifier_loss","body_loss","driver_loss"]
    axes[1,0].barh(labels,[m[k] for k in keys]);axes[1,0].set(xlabel="Average modeled loss (W)")
    study=json.loads((RESULTS/"ltspice"/"study.json").read_text(encoding="utf-8"))
    loads=[r for r in study["cases"] if r["name"].startswith("load_") or r["name"]=="nominal"]
    loads.sort(key=lambda r:r["load_ohm"])
    axes[1,1].semilogx([r["load_ohm"] for r in loads],[r["measurements"]["vout"] for r in loads],"o-")
    axes[1,1].set(xlabel="Equivalent DC load (Ω)",ylabel="Output voltage (V)",title="Open-loop behavior: regulation is required")
    for ax in axes.flat: ax.grid(alpha=.2)
    fig.suptitle(f"Nominal: {m['pout']:.3f} W output / {m['pin']:.3f} W input · model efficiency {100*op['nominal']['efficiency']:.1f}%")
    fig.tight_layout();fig.savefig(folder/"electrical.png",dpi=160);plt.close(fig)
    selection=(t>=.006)&(t<=.008)
    raw_power=float(np.trapezoid(vout[selection]**2/cfg["electrical"]["load_ohm"],t[selection])/(t[selection][-1]-t[selection][0]))
    comparison=abs(raw_power/m["pout"]-1)
    report=stamp(cfg,"waveform_crosscheck")|{"raw_output_power_w":raw_power,"log_output_power_w":m["pout"],
        "relative_error":comparison,"passed":comparison<.001}
    write_json(folder/"waveform_check.json",report)
    return report


def cad_gif(cfg):
    from PIL import Image,ImageDraw
    report=json.loads((RESULTS/"fusion"/"replay.json").read_text(encoding="utf-8"))
    if not report["passed"]: raise ValueError("Fusion replay has not passed")
    frames=[]
    for row in report["frames"]:
        image=Image.open(RESULTS/"fusion"/"replay_frames"/row["frame"]).convert("RGB")
        draw=ImageDraw.Draw(image)
        draw.rectangle((0,555,960,600),fill="#101820")
        text=f"AirDesk SIMULATION | {row['time_s']:.1f} s | {row['state']} | Receiver load: {row['power_w']:.2f} W"
        draw.text((20,568),text,fill="#68dfb5" if row["state"]=="CHARGING" else "white",font_size=19)
        frames.append(image)
    path=RESULTS/"fusion"/"tracking_3d.gif"
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=200,loop=0,optimize=False)
    return {"gif":str(path),"frames":len(frames),"source":"actual Fusion viewport captures"}
