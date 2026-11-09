import csv
from .common import RESULTS, artifact, stamp, write_json
from .motion import Controller, PhonePose
from .evidence import VerifiedPower

EVENTS = [(1.,PhonePose(-120,50)),(8.,PhonePose(160,-60,90)),
          (10.,PhonePose(-160,-90)),(19.,PhonePose(240,0)),(22.,None),(24.,PhonePose(0,0))]


def record(cfg, seconds=28., dt=.05):
    power = VerifiedPower(cfg)
    controller = Controller(cfg,power)
    rows, cursor = [], 0
    for _ in range(round(seconds/dt)):
        while cursor < len(EVENTS) and controller.time + 1e-8 >= EVENTS[cursor][0]:
            controller.place(EVENTS[cursor][1])
            cursor += 1
        rows.append(controller.step(dt))
    folder = RESULTS/"demo"
    folder.mkdir(parents=True,exist_ok=True)
    path = folder/"trajectory.csv"
    with path.open("w",newline="",encoding="utf-8") as stream:
        writer = csv.DictWriter(stream,rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    data = stamp(cfg,"demonstration_trajectory") | {"frames":len(rows),"duration_s":seconds,"dt_s":dt,
        "electrical_verified":power.available,"electrical_status":power.reason,
        "source_model":power.model,"trajectory":artifact(path),
        "operating_point":artifact(RESULTS/"operating_point.json") if power.available else None,
        "events":[{"at_s":at,"phone":pose.__dict__ if pose else None} for at,pose in EVENTS],
        "states":sorted({row["state"] for row in rows}),
        "maximum_observed_speed_mm_s":max((row["vx_mm_s"]**2+row["vy_mm_s"]**2)**.5 for row in rows)}
    write_json(folder/"trajectory.json",data)
    return rows,data
