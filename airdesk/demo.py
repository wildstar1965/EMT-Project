"""Interactive phone placement and a reproducible visualization of solver-backed power."""
import math
import time
from .common import RESULTS
from .motion import Controller, PhonePose, phone_corners, receiver_position
from .evidence import VerifiedPower


class View:
    def __init__(self,cfg):
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle, Circle, Polygon
        self.cfg = cfg
        self.fig = plt.figure(figsize=(12,7),facecolor="#101820")
        self.fig.canvas.manager.set_window_title("AirDesk - Wireless Charging Simulation")
        self.ax = self.fig.add_axes([.06,.33,.62,.54],facecolor="#15232e")
        self.side = self.fig.add_axes([.06,.13,.62,.14],facecolor="#15232e")
        for axes in (self.ax,self.side):
            axes.tick_params(colors="#9aafbc",labelsize=8)
            for spine in axes.spines.values(): spine.set_color("#334650")
            axes.set_aspect("equal")
        t,m=cfg["table"],cfg["mechanical"]
        w,d=t["width_mm"],t["depth_mm"]
        self.ax.set(xlim=(-w/2-15,w/2+15),ylim=(-d/2-15,d/2+15))
        self.ax.set_xlabel("X (mm)",color="#9aafbc")
        self.ax.set_ylabel("Y (mm)",color="#9aafbc")
        self.ax.add_patch(Rectangle((-w/2,-d/2),w,d,facecolor="#aacfe2",alpha=.08,edgecolor="#c8dfeb",lw=2))
        self.ax.add_patch(Rectangle((-m["x_travel_mm"]/2,-m["y_travel_mm"]/2),m["x_travel_mm"],m["y_travel_mm"],
                                   facecolor="#287e78",alpha=.13,edgecolor="#55ddc6",linestyle="--"))
        for x in (-m["y_rail_spacing_mm"]/2,m["y_rail_spacing_mm"]/2):
            self.ax.plot([x,x],[-175,175],color="#637683",lw=4)
        self.bridge,=self.ax.plot([-255,255],[0,0],color="#607d90",lw=5)
        self.carriage=Rectangle((-37.5,-37.5),75,75,facecolor="#6e8190",edgecolor="#d4e5ed",alpha=.55)
        self.ax.add_patch(self.carriage)
        self.rings=[]
        for radius in (10.5,14,17.5,21,24.5):
            ring=Circle((0,0),radius,fill=False,color="#f5aa63",lw=1.6)
            self.ax.add_patch(ring);self.rings.append(ring)
        self.phone=Polygon([[0,0]]*4,closed=True,facecolor="#344b61",edgecolor="#d6e3ee",lw=2,alpha=.8)
        self.ax.add_patch(self.phone)
        self.rx=Circle((0,0),20,fill=False,color="#76cfff",lw=1.8,linestyle="--")
        self.ax.add_patch(self.rx)
        self.ax.text(-290,184,"600 × 400 mm tabletop",color="#9aafbc",fontsize=8)
        self.side.set(xlim=(-315,315),ylim=(-45,40))
        self.side.set_yticks([])
        self.side.add_patch(Rectangle((-300,-5),600,5,color="#97bfcf",alpha=.35))
        self.side_tx=Rectangle((-25,-8.2),50,1.2,color="#f5aa63")
        self.side.add_patch(self.side_tx)
        self.side_phone=Rectangle((-40,0),80,9,edgecolor="#d6e3ee",facecolor="#344b61")
        self.side.add_patch(self.side_phone)
        self.side.text(-290,25,"SIDE VIEW · nominal winding-plane gap 9.1 mm",color="#9aafbc",fontsize=8)
        self.fig.text(.06,.94,"AirDesk",fontsize=28,color="#edf6fc",weight="bold")
        self.fig.text(.24,.948,"Intelligent wireless charging desk · simulation",fontsize=12,color="#a7bdcb")
        self.state=self.fig.text(.73,.80,"HOME",fontsize=20,color="#f5aa63",weight="bold")
        self.power=self.fig.text(.73,.69,"0.00 W",fontsize=30,color="#edf6fc",weight="bold")
        self.metrics=self.fig.text(.73,.61,"",fontsize=10,color="#bfd1de",linespacing=1.8,va="top")
        self.reason=self.fig.text(.73,.34,"",fontsize=9,color="#a7bdcb",wrap=True)
        self.fig.text(.73,.18,"POWER MODEL\nAligned FEMM + LTspice\n5 Ω equivalent receiver load\nNo Qi or battery simulation",fontsize=9,color="#8ba7b9",linespacing=1.6)
        self.fig.text(.06,.035,"Click or drag to place the phone  ·  Scroll to rotate  ·  R to remove  ·  S to save a trace",fontsize=9,color="#8ba7b9")
        from matplotlib.text import Text
        self._base_fonts=[(artist,artist.get_fontsize()) for artist in self.fig.findobj(Text)]
        self.fig.canvas.mpl_connect("resize_event",self._fit_text)
        self.rows=[]

    def _fit_text(self,event=None):
        # Tk scales the canvas DPI on high-density displays. Keep text proportional
        # to the available figure area when the user resizes its window.
        width,height=self.fig.get_size_inches()
        scale=min(width/12,height/7)
        for artist,size in self._base_fonts:
            artist.set_fontsize(size*scale)

    def draw(self,row):
        import textwrap
        x,y=row["x_mm"],row["y_mm"]
        charging=row["state"]=="CHARGING"
        color="#69e2b4" if charging else "#f5aa63"
        self.bridge.set_ydata([y,y])
        self.carriage.set_xy((x-37.5,y-37.5))
        for ring in self.rings:
            ring.center=(x,y);ring.set_color(color)
        self.phone.set_visible(row["phone_present"])
        self.rx.set_visible(row["phone_present"])
        self.side_phone.set_visible(row["phone_present"])
        if row["phone_present"]:
            pose=PhonePose(row["phone_x_mm"],row["phone_y_mm"],row["phone_yaw_deg"])
            corners=phone_corners(self.cfg,pose)
            self.phone.set_xy(corners)
            self.rx.center=receiver_position(self.cfg,pose)
            lo,hi=min(p[0] for p in corners),max(p[0] for p in corners)
            self.side_phone.set_x(lo);self.side_phone.set_width(hi-lo)
        self.side_tx.set_x(x-25);self.side_tx.set_color(color)
        self.state.set_text(row["state"]);self.state.set_color(color)
        self.power.set_text(f"{row['power_w']:.2f} W")
        error="—" if row["alignment_error_mm"] is None else f"{row['alignment_error_mm']:.2f} mm"
        self.metrics.set_text(f"TIME      {row['time_s']:6.2f} s\nX / Y     {x:6.1f} / {y:6.1f} mm\nERROR     {error}\nENERGY    {row['energy_wh']*1000:.2f} mWh")
        self.reason.set_text(textwrap.fill(row["reason"],36))
        return []


def export(cfg, gif=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter
    from .scenario import record
    rows,data=record(cfg)
    view=View(cfg)
    view.draw(rows[-1])
    view.fig.savefig(RESULTS/"demo"/"preview.png",dpi=140)
    if gif:
        sampled=rows[::2]
        animation=FuncAnimation(view.fig,lambda index:view.draw(sampled[index]),frames=len(sampled),interval=100,blit=False)
        animation.save(RESULTS/"demo"/"tracking.gif",writer=PillowWriter(fps=10),dpi=70)
    plt.close(view.fig)
    return data


def interactive(cfg):
    import csv
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    power=VerifiedPower(cfg)
    controller=Controller(cfg,power)
    view=View(cfg)
    held=[False]
    rows=[]

    def place(event):
        if event.inaxes==view.ax and event.xdata is not None:
            yaw=controller.phone.yaw_deg if controller.phone else 0.
            controller.place(PhonePose(event.xdata,event.ydata,yaw))

    def press(event):
        if event.button==1:
            held[0]=True;place(event)

    def release(event): held[0]=False
    def drag(event):
        if held[0]: place(event)
    def scroll(event):
        if controller.phone and event.inaxes==view.ax:
            p=controller.phone
            controller.place(PhonePose(p.x_mm,p.y_mm,p.yaw_deg+15*event.step))
    def key(event):
        if event.key=="r": controller.place(None)
        if event.key=="s" and rows:
            path=RESULTS/"demo"/"interactive_trajectory.csv"
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open("w",newline="",encoding="utf-8") as stream:
                writer=csv.DictWriter(stream,rows[0].keys());writer.writeheader();writer.writerows(rows)
            print("Saved",path)
    for name,handler in (("button_press_event",press),("button_release_event",release),("motion_notify_event",drag),("scroll_event",scroll),("key_press_event",key)):
        view.fig.canvas.mpl_connect(name,handler)
    def tick(index):
        row=controller.step(.05);rows.append(row);return view.draw(row)
    animation=FuncAnimation(view.fig,tick,interval=50,cache_frame_data=False)
    plt.show()
    return {"interactive_session_frames":len(rows),"electrical_verified":power.available}
