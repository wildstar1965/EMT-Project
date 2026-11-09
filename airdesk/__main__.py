import argparse
import json
from .common import load_config


def main():
    parser = argparse.ArgumentParser(description="AirDesk reproducible engineering workflow")
    parser.add_argument("stage", choices=["environment", "mechanics", "femm", "offset", "spice-smoke", "spice", "demo", "plots", "cad-gif", "report"])
    parser.add_argument("--full", action="store_true", help="Run the complete FEMM gap/frequency sweep")
    parser.add_argument("--ac-only", action="store_true", help="Isolate the FEMM nominal harmonic case")
    parser.add_argument("--fields-only", action="store_true", help="Export field samples from the solved nominal FEMM case")
    parser.add_argument("--export", action="store_true", help="Export the deterministic demonstration instead of opening its UI")
    parser.add_argument("--gif", action="store_true", help="Also render the demonstration GIF")
    args = parser.parse_args()
    cfg = load_config()
    if args.stage == "environment":
        from .environment import report
        result = report(cfg)
    elif args.stage == "mechanics":
        from .mechanics import report
        result = report(cfg)
    elif args.stage == "femm":
        if args.fields_only:
            from .fields import export
            result=export(cfg)
        else:
            from .femm_study import run
            result = run(cfg, args.full, args.ac_only)
    elif args.stage == "offset":
        from .femm_study import offset_study
        result = offset_study(cfg)
    elif args.stage == "demo":
        from . import demo
        result = demo.export(cfg,args.gif) if args.export else demo.interactive(cfg)
    elif args.stage in ("plots","cad-gif"):
        from . import plots
        result=plots.report_plots(cfg) if args.stage=="plots" else plots.cad_gif(cfg)
    elif args.stage=="report":
        from .validation import report
        result=report(cfg)
    else:
        from . import spice
        result = spice.smoke(cfg) if args.stage == "spice-smoke" else spice.run(cfg, args.full)
    print(json.dumps({k: v for k, v in result.items() if k not in ("cases", "rows")}, indent=2))
    if result.get("passed") is False or result.get("numerical_checks_passed") is False:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
