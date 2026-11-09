"""Export actual FEMM postprocessor samples without its unstable bitmap exporter."""
import csv
import math
import numpy as np
from .common import RESULTS, artifact, nominal_gap, stamp, write_json


def export(cfg):
    import femm
    path=(RESULTS/"femm"/"nominal_ac_tx.ans").resolve()
    radial=np.linspace(.05,36,60)
    vertical=np.linspace(-4,nominal_gap(cfg)+4,44)
    magnitude=np.zeros((len(vertical),len(radial)))
    rows=[]
    femm.openfemm(1)
    try:
        femm.opendocument(str(path))
        for iy,z in enumerate(vertical):
            for ix,r in enumerate(radial):
                br,bz=map(complex,femm.mo_getb(float(r),float(z)))
                value=math.sqrt(abs(br)**2+abs(bz)**2)
                if not math.isfinite(value): raise RuntimeError("Non-finite FEMM field sample")
                magnitude[iy,ix]=value
                rows.append({"r_mm":float(r),"z_mm":float(z),"br_real_t":br.real,"br_imag_t":br.imag,
                             "bz_real_t":bz.real,"bz_imag_t":bz.imag,"phasor_norm_t":value})
        femm.mo_close()
    finally:
        femm.closefemm()
    folder=RESULTS/"femm"
    with (folder/"field_samples.csv").open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,rows[0].keys());writer.writeheader();writer.writerows(rows)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.patches import Rectangle
    fig,ax=plt.subplots(figsize=(10,5))
    plot=ax.pcolormesh(radial,vertical,magnitude,norm=LogNorm(vmin=max(magnitude.min(),1e-6),vmax=magnitude.max()),cmap="magma",shading="auto")
    fig.colorbar(plot,ax=ax,label="Magnetic flux density phasor norm (T)")
    gap=nominal_gap(cfg)
    for label,z in (("tx",0),("rx",gap)):
        coil=cfg[label]
        ax.add_patch(Rectangle((coil["inner_radius_mm"],z-coil["thickness_mm"]/2),coil["outer_radius_mm"]-coil["inner_radius_mm"],coil["thickness_mm"],fill=False,edgecolor="white",lw=1.2))
        bottom=(-coil["thickness_mm"]/2-cfg["em"]["ferrite_insulation_mm"]-coil["ferrite_thickness_mm"] if label=="tx" else z+coil["thickness_mm"]/2+cfg["em"]["ferrite_insulation_mm"])
        ax.add_patch(Rectangle((0,bottom),coil["ferrite_radius_mm"],coil["ferrite_thickness_mm"],fill=False,edgecolor="cyan",lw=1.2))
    ax.set(xlabel="Radius r (mm)",ylabel="Axial coordinate z (mm)",title="Actual FEMM field · 150 kHz · 1 A Tx excitation · Rx open circuit")
    ax.set_aspect("equal");fig.tight_layout();fig.savefig(folder/"field.png",dpi=160);plt.close(fig)
    report=stamp(cfg,"femm_field_export")|{"passed":True,"samples":len(rows),"excitation_current_a":1.,"source":artifact(path),
        "field_data":artifact(folder/"field_samples.csv"),"maximum_sampled_phasor_norm_t":float(magnitude.max())}
    write_json(folder/"field_report.json",report)
    return report
