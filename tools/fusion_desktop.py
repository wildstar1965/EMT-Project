"""Local Fusion UI helper: inspect/capture, or open Scripts and Add-Ins.

Geometry is only created by official adsk scripts, never by screen coordinates.
"""
import argparse
import json
from pathlib import Path
import time
import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(2)
import win32gui
import win32con
import win32api
import win32clipboard
from PIL import ImageGrab


def windows():
    found = []
    def visit(handle, unused):
        title = win32gui.GetWindowText(handle)
        if "Fusion" in title and win32gui.IsWindowVisible(handle):
            found.append((handle, title, win32gui.GetWindowRect(handle)))
    win32gui.EnumWindows(visit, None)
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["inspect", "capture", "scripts", "console", "click", "run-smoke", "run-stage", "run-script"])
    parser.add_argument("--xy", nargs=2, type=float)
    parser.add_argument("--script", help="Python script path relative to this workspace")
    args = parser.parse_args()
    found = windows()
    print(json.dumps(found))
    if args.action == "inspect" or not found:
        return
    handle, title, rect = max(found, key=lambda w: ("Autodesk Fusion" in w[1], (w[2][2]-w[2][0])*(w[2][3]-w[2][1])))
    win32gui.ShowWindow(handle, win32con.SW_MAXIMIZE)
    win32gui.SetForegroundWindow(handle)
    time.sleep(.5)
    if args.action == "scripts":
        win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
        win32api.keybd_event(ord("S"), 0, 0, 0)
        win32api.keybd_event(ord("S"), 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
    if args.action == "console":
        win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
        win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(.3)
        for key in (win32con.VK_CONTROL, win32con.VK_MENU, ord("C")):
            win32api.keybd_event(key, 0, 0, 0)
        for key in (ord("C"), win32con.VK_MENU, win32con.VK_CONTROL):
            win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
    if args.action == "click":
        if not args.xy or any(not 0 <= v <= 1 for v in args.xy):
            raise ValueError("Click must be a normalized point inside Fusion's window")
        left, top, right, bottom = win32gui.GetWindowRect(handle)
        win32api.SetCursorPos((round(left + (right-left)*args.xy[0]), round(top+(bottom-top)*args.xy[1])))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    if args.action in ("run-smoke", "run-stage", "run-script"):
        run_started = time.time()
        win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
        win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(.3)
        left, top, right, bottom = win32gui.GetWindowRect(handle)
        win32api.SetCursorPos((round(left+.30*(right-left)), round(top+.974*(bottom-top))))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        root = Path(__file__).resolve().parents[1]
        relative = "fusion/00_Smoke/00_Smoke.py" if args.action == "run-smoke" else "fusion/AirDeskRunner/AirDeskRunner.py"
        if args.action == "run-script":
            if not args.script:
                raise ValueError("--script is required")
            script = (root / args.script).resolve()
            if not script.is_relative_to(root.resolve()) or script.suffix != ".py" or not script.is_file():
                raise ValueError("Script must be an existing Python file inside the AirDesk workspace")
            relative = str(script.relative_to(root))
        command = 'Python.RunScript "' + str(root / relative).replace("\\", "/") + '"'
        win32clipboard.OpenClipboard()
        try:
            previous = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else None
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(command, win32con.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        time.sleep(.4)
        for key in (win32con.VK_CONTROL, ord("A")):
            win32api.keybd_event(key, 0, 0, 0)
        for key in (ord("A"), win32con.VK_CONTROL):
            win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
        for key in (win32con.VK_CONTROL, ord("V")):
            win32api.keybd_event(key, 0, 0, 0)
        for key in (ord("V"), win32con.VK_CONTROL):
            win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(1.5)
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(2)
        if previous is not None:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(previous, win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        if args.action == "run-stage":
            status_file = root / "results" / "fusion" / "last_run.json"
            for _ in range(200):
                if status_file.exists() and status_file.stat().st_mtime >= run_started:
                    status = json.loads(status_file.read_text(encoding="utf-8"))
                    if status["status"] != "running":
                        print("Fusion stage result:", status)
                        break
                time.sleep(.2)
    time.sleep(7 if args.action == "capture" else 2)
    rect = win32gui.GetWindowRect(handle)
    output = Path(__file__).resolve().parents[1] / "results" / "fusion" / "desktop.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    ImageGrab.grab(bbox=rect).save(output)
    print(str(output))


if __name__ == "__main__":
    main()
