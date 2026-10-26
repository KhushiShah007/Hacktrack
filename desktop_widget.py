"""HackTrack desktop widget (Tkinter).

A compact, always-on-top pixel-themed window that shows your next 5 deadlines with urgency
colours and a live countdown, read from the HackTrack REST API.

    python desktop_widget.py            (server must be running: python run.py)

Settings come from widget_config.json (written by seed.py):
    {"server": "http://127.0.0.1:5000", "token": "<your API token>", "refresh_seconds": 60}
Get your own token from Settings -> API token in the web app.
"""
import json
import logging
import os
import tkinter as tk
import tkinter.font as tkfont
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "widget_config.json")
log = logging.getLogger("hacktrack.widget")

THEME = {
    "bg": "#0b0b2b", "panel": "#ffd1ea", "ink": "#2a0a3a", "title": "#ff3fa4", "text": "#e9e6ff",
    "green": "#3df58a", "border": "#12061f",
    "overdue": "#ff3b5c", "urgent": "#ff8a3d", "week": "#ffd23f", "later": "#3df58a",
}
# 12x8 heart and pin drawn as pixel rectangles on a Canvas, same art style as the web app
HEART = [".RR.RR.", "RWRRRRR", "RRRRRRR", ".RRRRR.", "..RRR..", "...R..."]


def load_config(path=CONFIG_PATH):
    """Read the widget config; fall back to defaults with a clear message. # CO2"""
    defaults = {"server": "http://127.0.0.1:5000", "token": "", "refresh_seconds": 60}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return {**defaults, **data}
    except FileNotFoundError:
        log.warning("config %s not found, using defaults", path)
    except json.JSONDecodeError as exc:
        log.warning("config %s is not valid JSON: %s", path, exc)
    return defaults


def fetch_deadlines(server, token, limit=5, timeout=4):
    """GET /api/opportunities?upcoming=1. Raises ConnectionError with a friendly message. # CO2"""
    url = f"{server.rstrip('/')}/api/opportunities?upcoming=1&limit={limit}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))["opportunities"]
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise ConnectionError("Token rejected. Copy it from Settings > API token.") from exc
        raise ConnectionError(f"Server error {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError("Server offline. Start it with: python run.py") from exc
    except (ValueError, KeyError) as exc:
        raise ConnectionError("Unexpected reply from server.") from exc


def countdown_text(deadline, now=None):
    now = now or datetime.now()
    try:
        dl = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return "?", "later"
    secs = (dl - now).total_seconds()
    if secs < 0:
        return "OVERDUE", "overdue"
    days, rem = divmod(int(secs), 86400)
    hours, rem = divmod(rem, 3600)
    mins, s = divmod(rem, 60)
    text = f"{days}d {hours:02d}h {mins:02d}m" if days else f"{hours:02d}:{mins:02d}:{s:02d}"
    bucket = "urgent" if secs < 2 * 86400 else ("week" if secs < 7 * 86400 else "later")
    return text, bucket


class PixelButton(tk.Label):
    """A chunky label that behaves like a pixel button with a pressed state."""

    def __init__(self, master, text, command, bg, fg, font):
        super().__init__(master, text=text, bg=bg, fg=fg, font=font, padx=8, pady=3, relief="raised", bd=3,
                         cursor="hand2", takefocus=1)
        self.command = command
        self.bind("<Button-1>", lambda e: self.config(relief="sunken"))
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", lambda e: self.command())
        self.bind("<space>", lambda e: self.command())

    def _release(self, _event):
        self.config(relief="raised")
        self.command()


class Widget(tk.Tk):
    """Always-on-top deadline window. # CO1 (class) # CO2 (exceptions) # CO3 (Tkinter GUI)"""

    def __init__(self, config):
        super().__init__()
        self.cfg = config
        self.items = []
        self.title("HackTrack")
        self.configure(bg=THEME["border"])
        self.attributes("-topmost", True)
        self.resizable(False, False)
        families = set(tkfont.families())
        display = "Press Start 2P" if "Press Start 2P" in families else "Courier"
        body = "VT323" if "VT323" in families else "Consolas" if "Consolas" in families else "Courier"
        self.f_title = (display, 9 if display != "Courier" else 11, "bold")
        self.f_body = (body, 14 if body == "VT323" else 10)
        self.f_small = (body, 12 if body == "VT323" else 9)

        frame = tk.Frame(self, bg=THEME["panel"], bd=0, highlightthickness=3, highlightbackground=THEME["border"])
        frame.pack(padx=3, pady=3)
        bar = tk.Frame(frame, bg=THEME["title"])
        bar.pack(fill="x")
        heart = tk.Canvas(bar, width=7 * 3, height=6 * 3, bg=THEME["title"], highlightthickness=0)
        for y, row in enumerate(HEART):
            for x, ch in enumerate(row):
                if ch != ".":
                    heart.create_rectangle(x * 3, y * 3, x * 3 + 3, y * 3 + 3, width=0,
                                           fill="#ffffff" if ch == "W" else "#ff3b5c")
        heart.pack(side="left", padx=(6, 2), pady=4)
        tk.Label(bar, text="NEXT DEADLINES", bg=THEME["title"], fg="white", font=self.f_title).pack(side="left", padx=4)

        self.rows = tk.Frame(frame, bg=THEME["panel"])
        self.rows.pack(fill="both", padx=8, pady=6)
        self.status = tk.Label(frame, text="Loading...", bg=THEME["panel"], fg=THEME["ink"], font=self.f_small, anchor="w")
        self.status.pack(fill="x", padx=8)

        buttons = tk.Frame(frame, bg=THEME["panel"])
        buttons.pack(fill="x", padx=8, pady=(4, 8))
        PixelButton(buttons, "REFRESH", self.refresh, THEME["green"], THEME["bg"], self.f_title).pack(side="left")
        PixelButton(buttons, "OPEN", self.open_browser, THEME["title"], "white", self.f_title).pack(side="left", padx=6)
        self.bind("<F5>", lambda e: self.refresh())
        self.bind("<Escape>", lambda e: self.destroy())

        self.refresh()
        self.tick()

    def open_browser(self):
        webbrowser.open(self.cfg["server"].rstrip("/") + "/dashboard")

    def refresh(self):
        self.status.config(text="Refreshing...")
        self.update_idletasks()
        try:
            self.items = fetch_deadlines(self.cfg["server"], self.cfg["token"])
            self.status.config(text=f"Updated {datetime.now():%H:%M}. F5 refresh, Esc close.")
        except ConnectionError as exc:
            self.items = []
            self.status.config(text=str(exc))
        self.render()
        if getattr(self, "_job", None):
            self.after_cancel(self._job)  # a manual refresh restarts the auto-refresh timer
        self._job = self.after(int(self.cfg.get("refresh_seconds", 60)) * 1000, self.refresh)

    def render(self):
        for child in self.rows.winfo_children():
            child.destroy()
        if not self.items:
            tk.Label(self.rows, text="No upcoming deadlines.\nTime for a Side Quest?", bg=THEME["panel"],
                     fg=THEME["ink"], font=self.f_body, justify="left").pack(anchor="w")
            return
        self.labels = []
        for item in self.items:
            row = tk.Frame(self.rows, bg=THEME["panel"])
            row.pack(fill="x", pady=2)
            text, bucket = countdown_text(item["deadline"])
            swatch = tk.Frame(row, bg=THEME[bucket], width=12, height=28, highlightthickness=2,
                              highlightbackground=THEME["border"])
            swatch.pack(side="left", padx=(0, 6))
            swatch.pack_propagate(False)
            title = item["title"] if len(item["title"]) <= 30 else item["title"][:28] + ".."
            tk.Label(row, text=title, bg=THEME["panel"], fg=THEME["ink"], font=self.f_body, anchor="w",
                     width=30).pack(side="left")
            cd = tk.Label(row, text=text, bg=THEME["bg"], fg=THEME[bucket], font=self.f_small, width=12)
            cd.pack(side="right")
            self.labels.append((cd, swatch, item["deadline"]))

    def tick(self):
        """Update countdowns every second without hitting the server."""
        for cd, swatch, deadline in getattr(self, "labels", []):
            text, bucket = countdown_text(deadline)
            cd.config(text=text, fg=THEME[bucket])
            swatch.config(bg=THEME[bucket])
        self.after(1000, self.tick)


def main():
    logging.basicConfig(level=logging.INFO)
    Widget(load_config()).mainloop()


if __name__ == "__main__":
    main()
