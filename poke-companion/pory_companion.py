import tkinter as tk
from PIL import Image, ImageTk
import os, socket, sys, math, threading, json, random, subprocess, time
import re, tempfile, urllib.request, urllib.parse
import html as _html_unescape
import ctypes, ctypes.wintypes
import psutil
from datetime import datetime

SCRIPT_DIR  = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
GIF_FRONT        = os.path.join(SCRIPT_DIR, "pory.gif")
GIF_BACK         = os.path.join(SCRIPT_DIR, "pory B.gif")
GIF_SHINY_FRONT  = os.path.join(SCRIPT_DIR, "S_pory.gif")
GIF_SHINY_BACK   = os.path.join(SCRIPT_DIR, "S_pory B.gif")
BUDEW_FRONT = os.path.join(SCRIPT_DIR, "budew.gif")
BUDEW_BACK  = os.path.join(SCRIPT_DIR, "budew B.gif")
TIMER_BG        = os.path.join(SCRIPT_DIR, "timerBG.png")
TIMER_END_SFX   = os.path.join(SCRIPT_DIR, "timer_end.mp3")

# ── Music album catalogue (khinsider slugs) ────────────────────────────────────
# Each entry maps the display name to one or more album slugs on khinsider.
# Slugs with accented characters use the actual unicode; urllib.parse.quote
# handles the percent-encoding when building URLs.
MUSIC_ALBUMS = {
    "Fire Red & Leaf Green": [
        "pokemon-firered-leafgreen-music-super-complete",
    ],
    "Heart Gold & Soul Silver": [
        "pokemon-heartgold-and-soulsilver",
    ],
    "Omega Ruby & Alpha Sapphire": [
        "pokemon-omega-ruby-and-alpha-sapphire-super-music-complete-nintendo-3ds",
    ],
    "Platinum": [
        "pok-mon-diamond-pok-mon-pearl-super-music-collection-2006",
    ],
    "Black & White": [
        "pokemon-black-and-white-super-music-collection",
    ],
    "X & Y": [
        "pokemon-x-y",
    ],
    "Ultra Sun & Ultra Moon": [
        "pokemon-ultra-sun-and-moon-2017",
    ],
    "Sword & Shield": [
        "pokemon-sword-shield-ost",
    ],
    "Legends: Arceus": [
        "pokemon-legends-arceus-complete-soundtrack",
    ],
    "Scarlet & Violet + Area Zero": [
        "pok-mon-scarlet-pok-mon-violet-2022",
        "pok-mon-scarlet-and-violet-the-hidden-treasure-of-area-zero-part-1-the-teal-mask-switch-gamerip-2023",
        "pok-mon-scarlet-and-violet-the-hidden-treasure-of-area-zero-part-2-the-indigo-disk-switch-gamerip-2023",
    ],
    "Legends: Z-A": [
        "pokémon-legends-za-switch-switch-2-gamerip-2025",
    ],
    "Legends: Z-A Mega Dimension DLC": [
        "pokémon-legends-za-mega-dimension-dlc-switch-switch-2-gamerip-2025",
    ],
}
SIZE        = (100, 100)
LOCK_PORT   = 47291

BG            = "black"
BUBBLE_BG     = "#fffef0"
BUBBLE_FG     = "#222222"
BUBBLE_BORDER = "#222222"
FONT_LABEL    = ("Comic Sans MS", 10, "bold")
FONT_BTN      = ("Comic Sans MS", 9, "bold")
FONT_ENTRY    = ("Comic Sans MS", 10)
FONT_WEATHER  = ("Comic Sans MS", 9)

# ── Version / update ───────────────────────────────────────────────────────────
VERSION     = "1.0.5"
GITHUB_REPO = "Aybabtu/pory-companion"

# Bubble geometry
BW, BH  = 230, 115   # body width / height (used by input bubbles; ChatBubble sizes itself)
TAIL_H  = 18
TAIL_X  = 185
PAD     = 3
R       = 14

# WMO weather code mappings
WMO_DESC = {
    0:"Clear sky", 1:"Mainly clear", 2:"Partly cloudy", 3:"Overcast",
    45:"Foggy", 48:"Icy fog",
    51:"Light drizzle", 53:"Drizzle", 55:"Heavy drizzle",
    61:"Light rain", 63:"Rain", 65:"Heavy rain",
    71:"Light snow", 73:"Snow", 75:"Heavy snow",
    77:"Snow grains",
    80:"Light showers", 81:"Showers", 82:"Heavy showers",
    85:"Snow showers", 86:"Heavy snow showers",
    95:"Thunderstorm", 96:"Thunderstorm + hail", 99:"Thunderstorm + heavy hail",
}
WMO_ICON = {
    0:"☀", 1:"🌤", 2:"⛅", 3:"☁",
    45:"🌫", 48:"🌫",
    51:"🌦", 53:"🌦", 55:"🌧",
    61:"🌧", 63:"🌧", 65:"🌧",
    71:"🌨", 73:"❄", 75:"❄", 77:"❄",
    80:"🌦", 81:"🌧", 82:"⛈",
    85:"🌨", 86:"🌨",
    95:"⛈", 96:"⛈", 99:"⛈",
}


# ── Single-instance lock ───────────────────────────────────────────────────────

def acquire_lock():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        sock.bind(("127.0.0.1", LOCK_PORT))
        return sock
    except OSError:
        sys.exit(0)


# ── GIF loader ─────────────────────────────────────────────────────────────────

def load_frames(path, flip=False):
    img = Image.open(path)
    frames = []
    try:
        while True:
            frame = img.copy().convert("RGBA").resize(SIZE, Image.LANCZOS)
            if flip:
                frame = frame.transpose(Image.FLIP_LEFT_RIGHT)
            frames.append((ImageTk.PhotoImage(frame), img.info.get("duration", 100)))
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    return frames


# ── Bubble drawing ─────────────────────────────────────────────────────────────

def _bubble_polygon(bw, bh, tail_h, tail_x, pad, r):
    x1, y1, x2, y2 = pad, pad, pad + bw, pad + bh
    steps = 8
    corners = [
        (180, x1 + r, y1 + r),
        (270, x2 - r, y1 + r),
        (0,   x2 - r, y2 - r),
        (90,  x1 + r, y2 - r),
    ]
    pts = []
    for idx, (a0, cx, cy) in enumerate(corners):
        for i in range(steps + 1):
            a = math.radians(a0 + i * 90 / steps)
            pts.extend([cx + r * math.cos(a), cy + r * math.sin(a)])
        if idx == 2:   # after bottom-right corner — insert tail
            pts.extend([tail_x + 6, y2, tail_x + 20, y2 + tail_h, tail_x - 10, y2])
    return pts


def draw_bubble(canvas, bw, bh, tail_h, tail_x, pad, r):
    pts = _bubble_polygon(bw, bh, tail_h, tail_x, pad, r)
    canvas.create_polygon(pts, fill=BUBBLE_BG, outline=BUBBLE_BORDER,
                          width=2, smooth=False, tags="bubble")


def clamp_window_pos(win, x, y):
    """Clamp (x, y) so the window stays fully on-screen across all monitors."""
    win.update_idletasks()
    w = win.winfo_reqwidth()
    h = win.winfo_reqheight()
    vx = ctypes.windll.user32.GetSystemMetrics(76)
    vy = ctypes.windll.user32.GetSystemMetrics(77)
    vw = ctypes.windll.user32.GetSystemMetrics(78)
    vh = ctypes.windll.user32.GetSystemMetrics(79)
    x  = max(vx, min(x, vx + vw - w))
    y  = max(vy, min(y, vy + vh - h))
    return x, y


def _ver_tuple(v):
    """Convert '1.2.3' or 'v1.2.3' to (1, 2, 3) for numeric comparison."""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except ValueError:
        return (0,)


def draw_bubble_down(canvas, bw, bh, tail_h, pad, r):
    """Speech bubble with tail pointing downward from the center-bottom."""
    x1, y1, x2, y2 = pad, pad, pad + bw, pad + bh
    cx = pad + bw // 2
    steps = 8
    corners = [
        (180, x1 + r, y1 + r),
        (270, x2 - r, y1 + r),
        (0,   x2 - r, y2 - r),
        (90,  x1 + r, y2 - r),
    ]
    pts = []
    for idx, (a0, ex, ey) in enumerate(corners):
        for i in range(steps + 1):
            a = math.radians(a0 + i * 90 / steps)
            pts.extend([ex + r * math.cos(a), ey + r * math.sin(a)])
        if idx == 2:
            pts.extend([cx + 12, y2, cx, y2 + tail_h, cx - 12, y2])
    canvas.create_polygon(pts, fill=BUBBLE_BG, outline=BUBBLE_BORDER,
                          width=2, smooth=False)


# ── Budew scream popup ─────────────────────────────────────────────────────────

class BudewPopup:
    BB_W, BB_H, BB_TAIL = 230, 65, 16

    def __init__(self, root, mx, my):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", BG)
        self.win.configure(bg=BG)

        total_w = self.BB_W + PAD * 2 + 2
        total_h = self.BB_H + self.BB_TAIL + SIZE[1] + PAD * 2 + 4

        canvas = tk.Canvas(self.win, width=total_w, height=total_h,
                           bg=BG, highlightthickness=0)
        canvas.pack()

        draw_bubble_down(canvas, self.BB_W, self.BB_H, self.BB_TAIL, PAD, 14)

        canvas.create_text(
            PAD + self.BB_W // 2, PAD + self.BB_H // 2 - 8,
            text="ITCHY POLLEN!!!",
            font=("Comic Sans MS", 16, "bold"), fill="#cc0000",
        )
        canvas.create_text(
            PAD + self.BB_W // 2, PAD + self.BB_H // 2 + 16,
            text="*WHEEZE*  *SNEEZE*",
            font=("Comic Sans MS", 9, "italic"), fill="#884400",
        )

        gif_y = PAD + self.BB_H + self.BB_TAIL + SIZE[1] // 2 + 2
        self._lbl = tk.Label(self.win, bg=BG, bd=0)
        canvas.create_window(total_w // 2, gif_y, window=self._lbl)

        self._frames = load_frames(BUDEW_BACK)
        self._fidx   = 0
        self._animate()

        # Position so Budew gif appears at (mx, my) — where user clicked End Task
        wx = mx - total_w // 2
        wy = my - total_h
        sw = ctypes.windll.user32.GetSystemMetrics(78)  # virtual width
        wx = max(0, min(wx, sw - total_w))
        self.win.geometry(f"+{wx}+{max(0, wy)}")

        self.win.after(2500, self._dismiss)

    def _animate(self):
        photo, delay = self._frames[self._fidx % len(self._frames)]
        self._lbl.configure(image=photo)
        self._lbl.image = photo
        self._fidx += 1
        try:
            self.win.after(delay, self._animate)
        except Exception:
            pass

    def _dismiss(self):
        try:
            self.win.destroy()
        except Exception:
            pass


# ── Process monitor (watches for Task Manager killing a process) ───────────────

def _foreground_title():
    u32 = ctypes.windll.user32
    hwnd = u32.GetForegroundWindow()
    n = u32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


class MouseClickMonitor(threading.Thread):
    """Tracks the last time the user clicked while Task Manager was focused."""

    CLICK_WINDOW = 3.0   # seconds: how long after a click a termination counts

    def __init__(self):
        super().__init__(daemon=True)
        self.last_taskmgr_click = 0.0
        self._btn_down = False

    def clicked_recently(self):
        return time.time() - self.last_taskmgr_click <= self.CLICK_WINDOW

    def run(self):
        u32 = ctypes.windll.user32
        VK_LBUTTON = 0x01
        while True:
            time.sleep(0.05)
            try:
                is_down = bool(u32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
                # Rising edge: button just pressed
                if is_down and not self._btn_down:
                    if "Task Manager" in _foreground_title():
                        self.last_taskmgr_click = time.time()
                self._btn_down = is_down
            except Exception:
                pass


class ProcessMonitor(threading.Thread):
    COOLDOWN = 1.5

    def __init__(self, callback, click_monitor):
        super().__init__(daemon=True)
        self.callback      = callback
        self.click_monitor = click_monitor
        self._last_trigger = 0.0

    def _cursor_pos(self):
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def run(self):
        known = set(psutil.pids())
        while True:
            time.sleep(0.3)
            try:
                current = set(psutil.pids())
                ended   = known - current
                if ended and "Task Manager" in _foreground_title():
                    now = time.time()
                    if (self.click_monitor.clicked_recently()
                            and now - self._last_trigger >= self.COOLDOWN):
                        self._last_trigger = now
                        mx, my = self._cursor_pos()
                        self.callback(mx, my)
                known = current
            except Exception:
                try:
                    known = set(psutil.pids())
                except Exception:
                    pass


# ── Weather service ────────────────────────────────────────────────────────────

def _http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "PoryCompanion/1.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode())


def fetch_weather():
    """Returns (city, current_dict, forecast_list) or raises."""
    loc  = _http_json("http://ip-api.com/json/")
    lat, lon, city = loc["lat"], loc["lon"], loc.get("city", "your area")

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,weathercode,windspeed_10m,apparent_temperature"
        f"&hourly=temperature_2m,weathercode"
        f"&temperature_unit=fahrenheit&windspeed_unit=mph"
        f"&forecast_days=2&timezone=auto"
    )
    data = _http_json(url)

    current = data["current"]
    hourly  = data["hourly"]

    now_str = datetime.now().strftime("%Y-%m-%dT%H:00")
    # find the index of the current hour, fall back to 0
    try:
        start = hourly["time"].index(now_str)
    except ValueError:
        start = 0

    forecast = []
    for iso, t, code in zip(
        hourly["time"][start:start+12],
        hourly["temperature_2m"][start:start+12],
        hourly["weathercode"][start:start+12],
    ):
        label = datetime.strptime(iso, "%Y-%m-%dT%H:%M").strftime("%I%p").lstrip("0")
        forecast.append((label, round(t), code))

    return city, current, forecast


# ── Weather result window ──────────────────────────────────────────────────────

class WeatherWindow:
    def __init__(self, parent_root, city, current, forecast, companion_xy):
        self.win = tk.Toplevel(parent_root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#1a1a2e")
        self.win.resizable(False, False)

        # Header
        code = current["weathercode"]
        icon = WMO_ICON.get(code, "?")
        desc = WMO_DESC.get(code, "Unknown")
        temp = round(current["temperature_2m"])
        feel = round(current["apparent_temperature"])
        wind = round(current["windspeed_10m"])

        header_frame = tk.Frame(self.win, bg="#16213e", pady=6, padx=10)
        header_frame.pack(fill="x")

        tk.Label(header_frame, text=f"{icon}  {city}", font=("Comic Sans MS", 11, "bold"),
                 fg="#e0e0ff", bg="#16213e").pack(side="left")
        tk.Button(header_frame, text="✕", font=("Comic Sans MS", 9),
                  fg="#aaaaaa", bg="#16213e", activebackground="#16213e",
                  relief="flat", bd=0, command=self.win.destroy).pack(side="right")

        # Current weather
        cur_frame = tk.Frame(self.win, bg="#1a1a2e", pady=4, padx=10)
        cur_frame.pack(fill="x")
        tk.Label(cur_frame,
                 text=f"{temp}°F  •  {desc}\nFeels like {feel}°F  •  Wind {wind} mph",
                 font=FONT_WEATHER, fg="#ccccee", bg="#1a1a2e", justify="left").pack(anchor="w")

        # Divider
        tk.Frame(self.win, bg="#333355", height=1).pack(fill="x", padx=8, pady=2)

        # 12-hour forecast grid (4 columns × 3 rows)
        grid = tk.Frame(self.win, bg="#1a1a2e", padx=6, pady=4)
        grid.pack(fill="x")
        for i, (label, t, fc) in enumerate(forecast):
            col = i % 4
            row = (i // 4) * 3
            fc_icon = WMO_ICON.get(fc, "?")
            tk.Label(grid, text=label, font=("Comic Sans MS", 7, "bold"),
                     fg="#8888aa", bg="#1a1a2e").grid(row=row,   column=col, padx=6)
            tk.Label(grid, text=fc_icon, font=("Comic Sans MS", 11),
                     fg="#ffffff", bg="#1a1a2e").grid(row=row+1, column=col, padx=6)
            tk.Label(grid, text=f"{t}°", font=("Comic Sans MS", 8),
                     fg="#ddddff", bg="#1a1a2e").grid(row=row+2, column=col, padx=6, pady=(0,4))

        # Position near companion
        self.win.update_idletasks()
        wx = companion_xy[0] - self.win.winfo_width() - 10
        wy = companion_xy[1]
        self.win.geometry(f"+{max(0,wx)}+{wy}")


# ── TCG card search bubble ─────────────────────────────────────────────────────

class TCGSearchBubble:
    def __init__(self, parent_root, on_submit, companion_xy):
        self.on_submit = on_submit
        total_h = PAD * 2 + BH + TAIL_H + 2

        self.win = tk.Toplevel(parent_root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", BG)
        self.win.configure(bg=BG)
        self.win.resizable(False, False)

        self.canvas = tk.Canvas(self.win, width=PAD * 2 + BW + 2,
                                height=total_h, bg=BG, highlightthickness=0)
        self.canvas.pack()
        draw_bubble(self.canvas, BW, BH, TAIL_H, TAIL_X, PAD, R)

        self.canvas.create_text(
            PAD + BW // 2, PAD + 18,
            text="Enter card name:",
            font=FONT_LABEL, fill=BUBBLE_FG,
        )
        self.canvas.create_text(
            PAD + BW // 2, PAD + 38,
            text='ex. Snorunt',
            font=("Comic Sans MS", 8), fill="#777755",
        )

        self.entry = tk.Entry(self.win, font=FONT_ENTRY, relief="flat",
                              bg="#ffffff", fg=BUBBLE_FG, insertbackground=BUBBLE_FG,
                              width=24, highlightthickness=1,
                              highlightbackground="#aaaaaa",
                              highlightcolor="#666666")
        self.canvas.create_window(PAD + BW // 2, PAD + 75, window=self.entry)
        self.entry.focus_set()

        self.entry.bind("<Return>", self._submit)
        self.entry.bind("<Escape>", lambda e: self.close())
        self.win.bind("<FocusOut>", self._on_focus_out)

        bx = companion_xy[0] - (PAD + TAIL_X + 20)
        by = companion_xy[1] - total_h
        bx, by = clamp_window_pos(self.win, bx, by)
        self.win.geometry(f"+{bx}+{by}")

    def _on_focus_out(self, event):
        self.win.after(150, self._check_focus)

    def _check_focus(self):
        try:
            focused = self.win.focus_get()
        except Exception:
            focused = None
        if focused is None:
            self.close()

    def _submit(self, event=None):
        query = self.entry.get().strip()
        self.close()
        if query and self.on_submit:
            self.on_submit(query)

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass


# ── Timer input bubble ────────────────────────────────────────────────────────

class TimerInputBubble:
    def __init__(self, parent_root, on_submit, companion_xy):
        self.on_submit = on_submit
        total_h = PAD * 2 + BH + TAIL_H + 2

        self.win = tk.Toplevel(parent_root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", BG)
        self.win.configure(bg=BG)
        self.win.resizable(False, False)

        self.canvas = tk.Canvas(self.win, width=PAD * 2 + BW + 2,
                                height=total_h, bg=BG, highlightthickness=0)
        self.canvas.pack()
        draw_bubble(self.canvas, BW, BH, TAIL_H, TAIL_X, PAD, R)

        self.canvas.create_text(
            PAD + BW // 2, PAD + 18,
            text="How many minutes?",
            font=FONT_LABEL, fill=BUBBLE_FG,
        )
        self.canvas.create_text(
            PAD + BW // 2, PAD + 38,
            text='ex. 50',
            font=("Comic Sans MS", 8), fill="#777755",
        )

        vcmd = (parent_root.register(lambda s: s.isdigit() or s == ""), "%P")
        self.entry = tk.Entry(self.win, font=FONT_ENTRY, relief="flat",
                              bg="#ffffff", fg=BUBBLE_FG, insertbackground=BUBBLE_FG,
                              width=10, highlightthickness=1,
                              highlightbackground="#aaaaaa",
                              highlightcolor="#666666",
                              validate="key", validatecommand=vcmd)
        self.canvas.create_window(PAD + BW // 2, PAD + 75, window=self.entry)
        self.entry.focus_set()

        self.entry.bind("<Return>", self._submit)
        self.entry.bind("<Escape>", lambda e: self.close())
        self.win.bind("<FocusOut>", self._on_focus_out)

        bx = companion_xy[0] - (PAD + TAIL_X + 20)
        by = companion_xy[1] - total_h
        bx, by = clamp_window_pos(self.win, bx, by)
        self.win.geometry(f"+{bx}+{by}")

    def _on_focus_out(self, event):
        self.win.after(150, self._check_focus)

    def _check_focus(self):
        try:
            focused = self.win.focus_get()
        except Exception:
            focused = None
        if focused is None:
            self.close()

    def _submit(self, event=None):
        minutes = self.entry.get().strip()
        self.close()
        if minutes and self.on_submit:
            self.on_submit(minutes)

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass


# ── Pokédex input bubble ──────────────────────────────────────────────────────

class PokedexInputBubble:
    def __init__(self, parent_root, on_submit, companion_xy):
        self.on_submit = on_submit
        total_h = PAD * 2 + BH + TAIL_H + 2

        self.win = tk.Toplevel(parent_root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", BG)
        self.win.configure(bg=BG)
        self.win.resizable(False, False)

        self.canvas = tk.Canvas(self.win, width=PAD * 2 + BW + 2,
                                height=total_h, bg=BG, highlightthickness=0)
        self.canvas.pack()
        draw_bubble(self.canvas, BW, BH, TAIL_H, TAIL_X, PAD, R)

        self.canvas.create_text(
            PAD + BW // 2, PAD + 18,
            text="Which Pokémon?",
            font=FONT_LABEL, fill=BUBBLE_FG,
        )
        self.canvas.create_text(
            PAD + BW // 2, PAD + 38,
            text='ex. Snorunt',
            font=("Comic Sans MS", 8), fill="#777755",
        )

        self.entry = tk.Entry(self.win, font=FONT_ENTRY, relief="flat",
                              bg="#ffffff", fg=BUBBLE_FG, insertbackground=BUBBLE_FG,
                              width=24, highlightthickness=1,
                              highlightbackground="#aaaaaa",
                              highlightcolor="#666666")
        self.canvas.create_window(PAD + BW // 2, PAD + 75, window=self.entry)
        self.entry.focus_set()

        self.entry.bind("<Return>", self._submit)
        self.entry.bind("<Escape>", lambda e: self.close())
        self.win.bind("<FocusOut>", self._on_focus_out)

        bx = companion_xy[0] - (PAD + TAIL_X + 20)
        by = companion_xy[1] - total_h
        bx, by = clamp_window_pos(self.win, bx, by)
        self.win.geometry(f"+{bx}+{by}")

    def _on_focus_out(self, event):
        self.win.after(150, self._check_focus)

    def _check_focus(self):
        try:
            focused = self.win.focus_get()
        except Exception:
            focused = None
        if focused is None:
            self.close()

    def _submit(self, event=None):
        name = self.entry.get().strip()
        self.close()
        if name and self.on_submit:
            self.on_submit(name)

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass


# ── Chat bubble with option buttons ───────────────────────────────────────────

class ChatBubble:
    LABEL_H  = 40   # px reserved for the prompt text at top
    BTN_H    = 34   # px per button (height + padding)
    BTN_TOP  = 12   # gap between label bottom and first button
    BODY_PAD = 14   # padding below last button
    MAX_BTNS = 5    # bubble height is capped at this many buttons; extras scroll

    def __init__(self, parent_root, actions):
        """actions: list of (label, callback). Capped at MAX_BTNS height; scrolls if more."""
        n          = len(actions)
        visible_n  = min(n, self.MAX_BTNS)
        body_h     = self.LABEL_H + self.BTN_TOP + visible_n * self.BTN_H + self.BODY_PAD
        total_h    = PAD * 2 + body_h + TAIL_H + 2
        self._body_h = body_h

        # vertical centre of the button area inside the bubble
        scroll_area_h = visible_n * self.BTN_H
        scroll_area_cy = PAD + self.LABEL_H + self.BTN_TOP + scroll_area_h // 2

        self.win = tk.Toplevel(parent_root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", BG)
        self.win.configure(bg=BG)
        self.win.resizable(False, False)

        self.canvas = tk.Canvas(self.win, width=PAD * 2 + BW + 2,
                                height=total_h, bg=BG, highlightthickness=0)
        self.canvas.pack()
        draw_bubble(self.canvas, BW, body_h, TAIL_H, TAIL_X, PAD, R)

        self.canvas.create_text(
            PAD + BW // 2, PAD + 18,
            text="What would we like to do today?",
            font=FONT_LABEL, fill=BUBBLE_FG,
        )

        if n <= self.MAX_BTNS:
            # ── plain frame, no scroll needed ─────────────────────────────────
            btn_frame = tk.Frame(self.win, bg=BUBBLE_BG)
            self.canvas.create_window(PAD + BW // 2, scroll_area_cy, window=btn_frame)
            for label, cb in actions:
                tk.Button(
                    btn_frame, text=label, font=FONT_BTN,
                    fg="#ffffff", bg="#5b7fa6",
                    activebackground="#3d5a80", activeforeground="#ffffff",
                    relief="flat", padx=10, pady=3, cursor="hand2",
                    width=22,
                    command=lambda c=cb: (self.close(), c()),
                ).pack(pady=2)
        else:
            # ── scrollable button area ─────────────────────────────────────────
            SB_W = 10   # scrollbar width
            sc_w = BW - PAD * 2 - SB_W - 4   # canvas width inside the bubble

            container = tk.Frame(self.win, bg=BUBBLE_BG)
            sc = tk.Canvas(container, width=sc_w, height=scroll_area_h,
                           bg=BUBBLE_BG, highlightthickness=0)
            sb = tk.Scrollbar(container, orient="vertical", command=sc.yview, width=SB_W)
            sc.configure(yscrollcommand=sb.set)
            sc.pack(side="left")
            sb.pack(side="right", fill="y")

            inner = tk.Frame(sc, bg=BUBBLE_BG)
            inner_id = sc.create_window(0, 0, anchor="nw", window=inner)

            def _on_wheel(e):
                sc.yview_scroll(int(-1 * (e.delta / 120)), "units")

            for label, cb in actions:
                b = tk.Button(
                    inner, text=label, font=FONT_BTN,
                    fg="#ffffff", bg="#5b7fa6",
                    activebackground="#3d5a80", activeforeground="#ffffff",
                    relief="flat", padx=10, pady=3, cursor="hand2",
                    width=20,
                    command=lambda c=cb: (self.close(), c()),
                )
                b.pack(pady=2)
                b.bind("<MouseWheel>", _on_wheel)

            def _update_scrollregion(e=None):
                sc.configure(scrollregion=sc.bbox("all"))
                sc.itemconfig(inner_id, width=sc_w)
            inner.bind("<Configure>", _update_scrollregion)

            sc.bind("<MouseWheel>", _on_wheel)
            inner.bind("<MouseWheel>", _on_wheel)

            self.canvas.create_window(PAD + BW // 2, scroll_area_cy, window=container)

        self.win.bind("<Escape>", lambda e: self.close())
        self.win.bind("<FocusOut>", self._on_focus_out)

    def position_near(self, px, py):
        total_h = PAD * 2 + self._body_h + TAIL_H + 2
        bx = px - (PAD + TAIL_X + 20)
        by = py - total_h
        bx, by = clamp_window_pos(self.win, bx, by)
        self.win.geometry(f"+{bx}+{by}")

    def _on_focus_out(self, event):
        self.win.after(150, self._check_focus)

    def _check_focus(self):
        try:
            focused = self.win.focus_get()
        except Exception:
            focused = None
        if focused is None:
            self.close()

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass


# ── Main companion ─────────────────────────────────────────────────────────────

class PoryCompanion:
    def __init__(self, root):
        self.root = root
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", BG)
        root.configure(bg=BG)

        self.label = tk.Label(root, bg=BG, bd=0)
        self.label.pack()

        self.facing_front      = True
        self._shiny            = False
        self.frames_front      = load_frames(GIF_FRONT)
        self.frames_front_flip = load_frames(GIF_FRONT,       flip=True)
        self.frames_back       = load_frames(GIF_BACK)
        self.frames_back_flip  = load_frames(GIF_BACK,        flip=True)
        self.frames_shiny_front      = load_frames(GIF_SHINY_FRONT)
        self.frames_shiny_front_flip = load_frames(GIF_SHINY_FRONT, flip=True)
        self.frames_shiny_back       = load_frames(GIF_SHINY_BACK)
        self.frames_shiny_back_flip  = load_frames(GIF_SHINY_BACK,  flip=True)
        self.frame_index       = 0
        self._bubble           = None
        self._weather_win      = None
        self._child_procs      = []

        # Position just above the taskbar in the lower-right of the primary monitor
        work = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(work), 0)
        root.geometry(f"+{work.right - SIZE[0]}+{work.bottom - SIZE[1]}")

        self.label.bind("<ButtonPress-1>",   self._drag_start)
        self.label.bind("<B1-Motion>",       self._drag_motion)
        self.label.bind("<ButtonRelease-1>", self._on_release)
        self.label.bind("<Button-3>",        self._on_right_click)

        self._drag_x = self._drag_y = 0
        self._dragging = False
        self._glancing = False
        self._pinned   = False
        self._roaming  = False
        self._roam_tx  = 0
        self._roam_ty  = 0
        self._roam_dir = None   # "left" or "right"

        self._animate()
        self._schedule_glance()
        self._schedule_roam()

        click_mon = MouseClickMonitor()
        click_mon.start()
        proc_mon = ProcessMonitor(callback=self._on_task_ended, click_monitor=click_mon)
        proc_mon.start()

        # Check for updates 8 seconds after launch (non-blocking)
        self.root.after(8000, self._check_for_update)


    @property
    def _frames(self):
        if self._roaming:
            if self._roam_dir == "right":
                return self.frames_shiny_front_flip if self._shiny else self.frames_front_flip
            else:
                return self.frames_shiny_back_flip  if self._shiny else self.frames_back_flip
        if self.facing_front:
            return self.frames_shiny_front if self._shiny else self.frames_front
        return self.frames_shiny_back if self._shiny else self.frames_back

    def _animate(self):
        frames = self._frames
        photo, delay = frames[self.frame_index % len(frames)]
        self.label.configure(image=photo)
        self.label.image = photo
        self.frame_index += 1
        self.root.after(delay, self._animate)

    def _schedule_glance(self):
        delay = random.randint(20_000, 60_000)   # glance every 20-60 seconds
        self.root.after(delay, self._start_glance)

    def _start_glance(self):
        if not self.facing_front:
            self._schedule_glance()
            return
        self._glancing = True
        self.facing_front = False
        self.frame_index = 0
        duration = random.randint(3_000, 8_000)  # stare for 3-8 seconds
        self.root.after(duration, self._end_glance)

    def _end_glance(self):
        self._glancing = False
        self.facing_front = True
        self.frame_index = 0
        self._schedule_glance()

    def _schedule_roam(self):
        delay = random.randint(30_000, 90_000)
        self.root.after(delay, self._start_roam)

    @staticmethod
    def _virtual_screen():
        """Return (x, y, w, h) of the bounding rect across all monitors."""
        try:
            import ctypes
            u32 = ctypes.windll.user32
            x = u32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
            y = u32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
            w = u32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
            h = u32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
            return x, y, w, h
        except Exception:
            return 0, 0, 1920, 1080

    def _start_roam(self):
        try:
            if self._dragging or self._pinned:
                self._schedule_roam()
                return
            vx, vy, vw, vh = self._virtual_screen()
            margin = 20
            self._roam_tx = random.randint(vx + margin, vx + vw - SIZE[0] - margin)
            self._roam_ty = random.randint(vy + margin, vy + vh - SIZE[1] - margin)
            self._roaming = True
            self._roam_step()
        except Exception:
            self._roaming = False
            self._schedule_roam()

    def _roam_step(self):
        try:
            if not self._roaming or self._dragging:
                self._roaming  = False
                self._roam_dir = None
                self._schedule_roam()
                return
            cx = self.root.winfo_x()
            cy = self.root.winfo_y()
            dx = self._roam_tx - cx
            dy = self._roam_ty - cy
            dist = (dx**2 + dy**2) ** 0.5
            if dist < 3:
                self._roaming  = False
                self._roam_dir = None
                self._schedule_roam()
                return
            self._roam_dir = "right" if dx > 0 else "left"
            speed = 2
            nx = cx + int(dx / dist * speed)
            ny = cy + int(dy / dist * speed)
            self.root.geometry(f"+{nx}+{ny}")
            self.root.after(30, self._roam_step)
        except Exception:
            self._roaming  = False
            self._roam_dir = None
            self._schedule_roam()

    def _drag_start(self, event):
        self._roaming = False
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()
        self._dragging = False

    def _drag_motion(self, event):
        self._dragging = True
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")
        if self._bubble:
            self._bubble.position_near(self.root.winfo_x(), self.root.winfo_y())

    def _on_release(self, event):
        if not self._dragging:
            self._toggle_bubble()
        self._dragging = False

    def _toggle_bubble(self):
        if self._bubble:
            self._bubble.close()
            self._bubble = None
        else:
            actions = [
                ("🌤 Weather",          self._show_weather),
                ("❓ Who's That?",     self._show_pokemon),
                ("💰 Card Prices",     self._show_tcg_search),
                ("⏱ Tournament Timer", self._show_timer),
                ("📖 Pokédex",          self._show_pokedex),
                ("🎵 Music Player",    self._show_music),
            ]
            self._bubble = ChatBubble(self.root, actions)
            self._bubble.position_near(self.root.winfo_x(), self.root.winfo_y())
            self._bubble.win.bind("<Destroy>", lambda e: self._clear_bubble())

    def _clear_bubble(self):
        self._bubble = None

    def _toggle_shiny(self):
        self._shiny = not self._shiny
        self.frame_index = 0

    def _toggle_pin(self):
        self._pinned = not self._pinned
        if self._pinned:
            self._roaming = False   # stop any active roam immediately

    # ── Auto-update ───────────────────────────────────────────────────────────

    def _check_for_update(self):
        """Silently check GitHub Releases for a newer version (background thread)."""
        def _bg():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Pory-Companion"}
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode())
                tag = data.get("tag_name", "").strip()
                if not tag:
                    return
                if _ver_tuple(tag) > _ver_tuple(VERSION):
                    asset_url = None
                    for asset in data.get("assets", []):
                        if asset["name"].lower().endswith(".exe"):
                            asset_url = asset["browser_download_url"]
                            break
                    self.root.after(0, lambda: self._show_update_dialog(tag, asset_url))
            except Exception:
                pass   # update check is non-critical; never crash the companion

        threading.Thread(target=_bg, daemon=True).start()

    def _show_update_dialog(self, new_tag, asset_url):
        """Styled popup informing the user a new version is available."""
        win = tk.Toplevel(self.root)
        win.title("Pory — Update Available")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.configure(bg="#1a1a2e")
        win.grab_set()

        W, H = 360, 190
        win.update_idletasks()
        sx = win.winfo_screenwidth()
        sy = win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sx - W)//2}+{(sy - H)//2}")

        DARK = "#1a1a2e"
        ACCT = "#e94560"
        LT   = "#eaeaea"
        DIM  = "#aaaacc"
        is_exe = getattr(sys, "frozen", False)

        tk.Label(win, text="✨  Update Available!",
                 font=("Comic Sans MS", 13, "bold"),
                 bg=DARK, fg=ACCT).pack(pady=(20, 4))

        tk.Label(win,
                 text=(f"A new version of Pory is ready!\n"
                       f"You have  v{VERSION}   →   New: {new_tag}"),
                 font=("Comic Sans MS", 10), bg=DARK, fg=LT,
                 justify="center").pack(pady=4)

        if not is_exe:
            tk.Label(win,
                     text="(Running from source — GitHub will open to download.)",
                     font=("Comic Sans MS", 8), bg=DARK, fg=DIM).pack()

        btn_frame = tk.Frame(win, bg=DARK)
        btn_frame.pack(pady=16)

        def on_update():
            win.destroy()
            if asset_url and is_exe:
                self._do_update(asset_url)
            else:
                import webbrowser
                webbrowser.open(
                    f"https://github.com/{GITHUB_REPO}/releases/latest"
                )

        lbl = "Update Now" if (asset_url and is_exe) else "Open GitHub"
        tk.Button(btn_frame, text=lbl,
                  font=("Comic Sans MS", 10, "bold"),
                  bg="#0f3460", fg="#ffffff",
                  activebackground=ACCT, activeforeground="#ffffff",
                  relief="flat", padx=16, pady=5, cursor="hand2",
                  command=on_update).pack(side="left", padx=8)

        tk.Button(btn_frame, text="Not Now",
                  font=("Comic Sans MS", 10),
                  bg="#333355", fg="#cccccc",
                  activebackground="#444466", activeforeground="#ffffff",
                  relief="flat", padx=16, pady=5, cursor="hand2",
                  command=win.destroy).pack(side="left", padx=8)

    def _do_update(self, asset_url):
        """Download the new exe and schedule a swap via batch script, then quit."""
        exe_path = sys.executable
        new_path = exe_path + ".new"

        # ── Progress window ──────────────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title("Downloading Update…")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.configure(bg="#1a1a2e")
        W, H = 340, 130
        win.update_idletasks()
        sx = win.winfo_screenwidth()
        sy = win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sx - W)//2}+{(sy - H)//2}")

        DARK = "#1a1a2e"
        ACCT = "#e94560"
        LT   = "#eaeaea"

        lbl = tk.Label(win, text="Downloading update…",
                       font=("Comic Sans MS", 10), bg=DARK, fg=LT)
        lbl.pack(pady=(22, 6))

        pc = tk.Canvas(win, height=12, bg="#16213e",
                       highlightthickness=0, relief="flat")
        pc.pack(fill="x", padx=24, pady=4)
        bar = pc.create_rectangle(0, 0, 0, 12, fill=ACCT, outline="")

        def _update_bar(frac):
            w = pc.winfo_width()
            pc.coords(bar, 0, 0, int(w * frac), 12)
            lbl.config(text=f"Downloading update… {int(frac * 100)}%")

        def _apply(total, done):
            # Verify the download is complete before touching anything
            if total and done != total:
                lbl.config(
                    text=f"Download incomplete ({done}/{total} bytes). Please try again.",
                    fg="#ff6666"
                )
                try:
                    os.remove(new_path)
                except OSError:
                    pass
                return

            # Swap the file after Pory exits — do NOT auto-launch.
            # Launching via batch script bypasses the Explorer/Defender pre-clearance
            # that a normal double-click gets, causing python313.dll to fail mid-extraction.
            # The user relaunching manually works exactly like a fresh install.
            exe_dir = os.path.dirname(exe_path)
            bat = tempfile.NamedTemporaryFile(
                suffix=".bat", delete=False, mode="w",
                encoding="utf-8", dir=exe_dir
            )
            bat.write(
                "@echo off\n"
                "ping 127.0.0.1 -n 6 > NUL\n"
                f'move /y "{new_path}" "{exe_path}"\n'
                'del "%~f0"\n'
            )
            bat.close()
            subprocess.Popen(
                ["cmd.exe", "/c", bat.name],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            # Show confirmation then quit — user reopens Pory themselves
            lbl.config(
                text="✅  Update applied!\nReopen Pory to start the new version.",
                fg="#88ff88"
            )
            win.geometry(f"{W}x{H + 20}+{(win.winfo_screenwidth()-W)//2}+{(win.winfo_screenheight()-H)//2}")
            win.after(4000, lambda: (win.destroy(), self._quit()))

        def _download():
            try:
                req = urllib.request.Request(
                    asset_url, headers={"User-Agent": "Pory-Companion"}
                )
                with urllib.request.urlopen(req, timeout=120) as r:
                    total = int(r.headers.get("Content-Length", 0))
                    done  = 0
                    with open(new_path, "wb") as f:
                        while True:
                            chunk = r.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            done += len(chunk)
                            if total:
                                self.root.after(0, lambda fr=done/total: _update_bar(fr))
                self.root.after(0, lambda: _apply(total, done))
            except Exception as e:
                self.root.after(0, lambda: lbl.config(
                    text=f"Download failed: {e}", fg="#ff6666"
                ))

        threading.Thread(target=_download, daemon=True).start()

    def _quit(self):
        for p in self._child_procs:
            try:
                p.terminate()
            except Exception:
                pass
        self.root.destroy()

    def _on_right_click(self, event):
        menu = tk.Menu(self.root, tearoff=0, font=("Comic Sans MS", 10))
        menu.add_command(label=f"Pory  v{VERSION}", state="disabled")
        menu.add_separator()
        shiny_label = "✨ Normal Form" if self._shiny else "✨ Shiny Form"
        menu.add_command(label=shiny_label, command=self._toggle_shiny)
        menu.add_separator()
        pin_label = "Unpin" if self._pinned else "Pin"
        menu.add_command(label=pin_label, command=self._toggle_pin)
        menu.add_separator()
        menu.add_command(label="Quit", command=self._quit)
        menu.tk_popup(event.x_root, event.y_root)

    # ── Weather ──────────────────────────────────────────────────────────────

    def _show_weather(self):
        if self._weather_win:
            try:
                self._weather_win.win.destroy()
            except Exception:
                pass
            self._weather_win = None

        def worker():
            try:
                city, current, forecast = fetch_weather()
                self.root.after(0, lambda: self._display_weather(city, current, forecast))
            except Exception as e:
                self.root.after(0, lambda: self._weather_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _display_weather(self, city, current, forecast):
        xy = (self.root.winfo_x(), self.root.winfo_y())
        self._weather_win = WeatherWindow(self.root, city, current, forecast, xy)
        self._weather_win.win.bind("<Destroy>", lambda e: setattr(self, "_weather_win", None))

    def _weather_error(self, msg):
        err = tk.Toplevel(self.root)
        err.overrideredirect(True)
        err.attributes("-topmost", True)
        err.configure(bg="#2e1a1a")
        tk.Label(err, text=f"Couldn't fetch weather:\n{msg}",
                 font=FONT_WEATHER, fg="#ffaaaa", bg="#2e1a1a", padx=10, pady=8).pack()
        tk.Button(err, text="OK", command=err.destroy,
                  font=FONT_BTN, relief="flat", bg="#5a2a2a", fg="white").pack(pady=(0,6))
        err.geometry(f"+{self.root.winfo_x()-150}+{self.root.winfo_y()-80}")

    def _open_bubble(self):
        if not self._bubble:
            self._toggle_bubble()

    def _on_task_ended(self, mx, my):
        self.root.after(0, lambda: BudewPopup(self.root, mx, my))

    # ── Who's That Pokémon ────────────────────────────────────────────────────

    def _show_pokemon(self):
        p = subprocess.Popen([sys.executable, __file__, "--pokemon"],
                             creationflags=subprocess.CREATE_NO_WINDOW
                             if sys.platform == "win32" else 0)
        self._child_procs.append(p)

    # ── TCG Card Prices ───────────────────────────────────────────────────────

    def _show_tcg_search(self):
        TCGSearchBubble(self.root, on_submit=self._launch_tcg_lookup,
                        companion_xy=(self.root.winfo_x(), self.root.winfo_y()))

    def _launch_tcg_lookup(self, query):
        p = subprocess.Popen(
            [sys.executable, __file__, "--tcg", query],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self._child_procs.append(p)

    # ── Tournament Timer ──────────────────────────────────────────────────────

    def _show_timer(self):
        TimerInputBubble(self.root, on_submit=self._launch_timer,
                         companion_xy=(self.root.winfo_x(), self.root.winfo_y()))

    def _launch_timer(self, minutes):
        p = subprocess.Popen(
            [sys.executable, __file__, "--timer", minutes],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self._child_procs.append(p)

    # ── Music Player ──────────────────────────────────────────────────────────

    def _show_music(self):
        p = subprocess.Popen(
            [sys.executable, __file__, "--music"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self._child_procs.append(p)

    # ── Pokédex ───────────────────────────────────────────────────────────────

    def _show_pokedex(self):
        PokedexInputBubble(self.root, on_submit=self._launch_pokedex,
                           companion_xy=(self.root.winfo_x(), self.root.winfo_y()))

    def _launch_pokedex(self, name):
        p = subprocess.Popen(
            [sys.executable, __file__, "--pokedex", name],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self._child_procs.append(p)


# ── Pokémon game window (runs as subprocess) ───────────────────────────────────

def run_pokemon_game():
    import webview

    # Injected after a short delay so Vue has time to mount the app-inner div.
    # Hides only the page chrome (header/footer/nav) and centres the game.
    INJECT_JS = """
    (function() {
        var s = document.createElement('style');
        s.textContent = `
            header, footer, nav, .navbar, .site-header, .site-footer,
            .header, .footer { display: none !important; }
            body { margin: 0 !important; }
            .app-inner { margin: 0 auto; }
        `;
        document.head.appendChild(s);

        // Scroll game div into view if present
        var el = document.querySelector('.app-inner');
        if (el) el.scrollIntoView();
    })();
    """

    w = webview.create_window(
        "Who's That Pokémon?",
        "https://gearoid.me/pokemon/",
        width=749,
        height=669,
        resizable=True,
    )

    def on_loaded():
        import time; time.sleep(1)
        try:
            w.evaluate_js(INJECT_JS)
        except Exception:
            pass

    w.events.loaded += on_loaded
    webview.start()


# ── TCG price lookup window (runs as subprocess) ───────────────────────────────

def run_tcg_lookup(query):
    import webview
    import urllib.parse

    encoded = urllib.parse.quote(query)
    url = (
        f"https://www.tcgplayer.com/search/pokemon/product"
        f"?q={encoded}&view=grid&productLineName=pokemon"
    )

    INJECT_JS = """
    (function() {
        // Hide page chrome
        var s = document.createElement('style');
        s.textContent = `
            #header, .site-header, .header-wrapper,
            .site-footer, footer,
            .spotlight-carousel, .homepage-hero,
            .cookie-consent, .ad-unit { display: none !important; }
            body { padding-top: 0 !important; }
        `;
        document.head.appendChild(s);

        // Click the Pokemon product line filter if not already checked.
        // Retries up to 10 times (500 ms apart) waiting for React to render.
        var attempts = 0;
        function clickPokemonFilter() {
            var labels = document.querySelectorAll(
                '.search-filter label, .filter-panel label, ' +
                '.tcg-checkbox label, fieldset label, li label, label'
            );
            for (var i = 0; i < labels.length; i++) {
                var txt = labels[i].textContent.trim();
                if (/^pok[eé]mon$/i.test(txt)) {
                    var cb = labels[i].querySelector('input[type="checkbox"]')
                             || labels[i].previousElementSibling;
                    if (cb && cb.type === 'checkbox' && !cb.checked) {
                        cb.click();
                    } else if (!cb) {
                        labels[i].click();
                    }
                    return true;
                }
            }
            return false;
        }

        function retry() {
            if (clickPokemonFilter()) return;
            if (++attempts < 10) setTimeout(retry, 500);
        }
        retry();
    })();
    """

    w = webview.create_window(
        f"TCG Prices — {query}",
        url,
        width=1060,
        height=780,
        resizable=True,
    )

    def on_loaded():
        import time; time.sleep(1.5)
        try:
            w.evaluate_js(INJECT_JS)
        except Exception:
            pass

    w.events.loaded += on_loaded
    webview.start()


# ── Tournament timer window (runs as subprocess) ───────────────────────────────

def run_timer(minutes):
    total_secs = int(minutes) * 60

    work = ctypes.wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(work), 0)
    WW = (work.right  - work.left) // 2
    WH = (work.bottom - work.top)  // 2

    root = tk.Tk()
    root.title(f"Tournament Timer — {minutes} min")
    root.geometry(f"{WW}x{WH}")
    root.resizable(True, True)

    # ── Background ────────────────────────────────────────────────────────────
    src_img  = Image.open(TIMER_BG).convert("RGBA")
    src_w, src_h = src_img.size

    def make_bg(w, h):
        """Fit src_img into (w, h) keeping aspect ratio; centre on black canvas at 80% opacity."""
        scale   = min(w / src_w, h / src_h)
        new_w   = int(src_w * scale)
        new_h   = int(src_h * scale)
        resized = src_img.resize((new_w, new_h), Image.LANCZOS)
        # Fade to 80% by scaling the alpha channel
        r, g, b, a = resized.split()
        a = a.point(lambda p: int(p * 0.80))
        resized = Image.merge("RGBA", (r, g, b, a))
        canvas_img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
        ox = (w - new_w) // 2
        oy = (h - new_h) // 2
        canvas_img.paste(resized, (ox, oy), resized)
        return ImageTk.PhotoImage(canvas_img)

    bg_photo = make_bg(WW, WH)

    canvas = tk.Canvas(root, width=WW, height=WH, highlightthickness=0, bd=0,
                       bg="black")
    canvas.pack(fill="both", expand=True)
    bg_item = canvas.create_image(0, 0, anchor="nw", image=bg_photo)
    canvas.bg_photo = bg_photo

    # ── State ─────────────────────────────────────────────────────────────────
    state = {
        "remaining":  total_secs,
        "running":    False,
        "paused":     False,
        "after_id":   None,
        "ended":      False,
        "shake_dx":   0,
        "shake_dy":   0,
        "fullscreen": False,
    }

    # ── Timer display ─────────────────────────────────────────────────────────
    font_size  = WH // 5
    timer_font = ("Arial Black", font_size, "bold")
    cx, cy     = WW // 2, int(WH * 0.75)
    outline    = max(3, font_size // 18)

    def fmt():
        m, s = divmod(state["remaining"], 60)
        return f"{m:02d}:{s:02d}"

    def draw_timer():
        canvas.delete("timer")
        t = fmt()
        fill  = "#dd0000" if state["ended"] else "black"
        sdx   = state["shake_dx"]
        sdy   = state["shake_dy"]
        for dx in range(-outline, outline + 1):
            for dy in range(-outline, outline + 1):
                if dx == 0 and dy == 0:
                    continue
                canvas.create_text(cx + sdx + dx, cy + sdy + dy, text=t,
                                   font=timer_font, fill="white", tags="timer")
        canvas.create_text(cx + sdx, cy + sdy, text=t,
                           font=timer_font, fill=fill, tags="timer")

    draw_timer()

    # ── Timer-end: sound × 2 + shake ─────────────────────────────────────────
    def on_timer_end():
        state["running"] = False
        state["ended"]   = True
        update_buttons()

        # Play timer_end.mp3 twice in a background thread
        def _play():
            try:
                import pygame
                pygame.mixer.init()
                snd = pygame.mixer.Sound(TIMER_END_SFX)
                snd.play()
                time.sleep(snd.get_length() + 0.15)
                snd.play()
            except Exception:
                pass
        threading.Thread(target=_play, daemon=True).start()

        # Shake animation — 60 frames × 50 ms ≈ 3 seconds
        def shake(n):
            if n > 0:
                state["shake_dx"] = random.randint(-9, 9)
                state["shake_dy"] = random.randint(-6, 6)
                draw_timer()
                root.after(50, lambda: shake(n - 1))
            else:
                state["shake_dx"] = 0
                state["shake_dy"] = 0
                draw_timer()   # settle at rest — stays red
        shake(60)

    # ── Tick ──────────────────────────────────────────────────────────────────
    def tick():
        if state["running"] and not state["paused"]:
            if state["remaining"] > 0:
                state["remaining"] -= 1
                draw_timer()
                state["after_id"] = root.after(1000, tick)
            else:
                on_timer_end()

    # ── Controls ──────────────────────────────────────────────────────────────
    def start_stop():
        if state["running"]:
            state["running"] = False
            state["paused"]  = False
            if state["after_id"]:
                root.after_cancel(state["after_id"])
        else:
            if state["remaining"] > 0:
                state["running"]  = True
                state["paused"]   = False
                state["after_id"] = root.after(1000, tick)
        update_buttons()

    def pause():
        if not state["running"]:
            return
        state["paused"] = not state["paused"]
        if state["paused"]:
            if state["after_id"]:
                root.after_cancel(state["after_id"])
        else:
            state["after_id"] = root.after(1000, tick)
        update_buttons()

    def reset():
        state["running"]   = False
        state["paused"]    = False
        state["ended"]     = False
        state["shake_dx"]  = 0
        state["shake_dy"]  = 0
        if state["after_id"]:
            root.after_cancel(state["after_id"])
        state["remaining"] = total_secs
        draw_timer()
        update_buttons()

    # ── Fullscreen ────────────────────────────────────────────────────────────
    def exit_fullscreen():
        if state["fullscreen"]:
            state["fullscreen"] = False
            root.attributes("-fullscreen", False)
            fs_btn.config(text="⛶  Full Screen")

    def toggle_fullscreen():
        state["fullscreen"] = not state["fullscreen"]
        root.attributes("-fullscreen", state["fullscreen"])
        fs_btn.config(
            text="✕  Exit Full Screen" if state["fullscreen"] else "⛶  Full Screen"
        )

    def _on_focus_out(event):
        # Only react when the root window itself loses focus to another app
        if state["fullscreen"]:
            root.after(150, _check_fs_focus)

    def _check_fs_focus():
        try:
            focused = root.focus_get()
        except Exception:
            focused = None
        if focused is None:
            exit_fullscreen()

    root.bind("<Escape>",   lambda e: exit_fullscreen())
    root.bind("<FocusOut>", _on_focus_out)

    # ── Buttons ───────────────────────────────────────────────────────────────
    btn_font = ("Arial Black", max(10, WH // 22), "bold")

    btn_frame = tk.Frame(canvas, bg="#1a1a1a", padx=6, pady=6)
    canvas.create_window(WW // 2, int(WH * 0.18), window=btn_frame, tags="buttons")

    start_btn = tk.Button(btn_frame, text="▶  Start", font=btn_font,
                          fg="white", bg="#2a7a40", activeforeground="white",
                          activebackground="#1f5c30", relief="flat",
                          padx=18, pady=8, command=start_stop)
    start_btn.grid(row=0, column=0, padx=8)

    pause_btn = tk.Button(btn_frame, text="⏸  Pause", font=btn_font,
                          fg="white", bg="#a07010", activeforeground="white",
                          activebackground="#7a5510", relief="flat",
                          padx=18, pady=8, command=pause)
    pause_btn.grid(row=0, column=1, padx=8)

    reset_btn = tk.Button(btn_frame, text="↺  Reset", font=btn_font,
                          fg="white", bg="#3a3a6a", activeforeground="white",
                          activebackground="#2a2a50", relief="flat",
                          padx=18, pady=8, command=reset)
    reset_btn.grid(row=0, column=2, padx=8)

    fs_btn = tk.Button(btn_frame, text="⛶  Full Screen", font=btn_font,
                       fg="white", bg="#4a2a6a", activeforeground="white",
                       activebackground="#361e50", relief="flat",
                       padx=18, pady=8, command=toggle_fullscreen)
    fs_btn.grid(row=1, column=0, columnspan=3, pady=(6, 0))

    def update_buttons():
        if state["running"]:
            start_btn.config(text="⏹  Stop",  bg="#8a2020", activebackground="#6a1818")
            pause_btn.config(bg="#a07010" if not state["paused"] else "#606010",
                             activebackground="#7a5510")
        else:
            start_btn.config(text="▶  Start", bg="#2a7a40", activebackground="#1f5c30")
            pause_btn.config(bg="#555555", activebackground="#444444")

    update_buttons()

    # Redraw background + timer on resize
    def on_resize(event):
        nonlocal bg_photo, WW, WH, cx, cy, font_size, timer_font, outline, btn_font
        WW, WH   = event.width, event.height
        cx, cy   = WW // 2, int(WH * 0.75)
        font_size  = WH // 5
        timer_font = ("Arial Black", font_size, "bold")
        outline    = max(3, font_size // 18)
        bg_photo = make_bg(WW, WH)
        canvas.itemconfig(bg_item, image=bg_photo)
        canvas.bg_photo = bg_photo
        canvas.coords(bg_item, 0, 0)
        canvas.coords("buttons", WW // 2, int(WH * 0.18))
        btn_font = ("Arial Black", max(10, WH // 22), "bold")
        for b in (start_btn, pause_btn, reset_btn, fs_btn):
            b.config(font=btn_font)
        draw_timer()

    canvas.bind("<Configure>", on_resize)
    root.mainloop()


# ── Pokédex window (runs as subprocess) ───────────────────────────────────────

def run_pokedex(name):
    import webview, urllib.parse

    slug = name.strip().lower().replace(" ", "-")
    url  = f"https://pokemondb.net/pokedex/{urllib.parse.quote(slug)}"

    work = ctypes.wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(work), 0)
    w_width  = (work.right  - work.left) // 2
    w_height = (work.bottom - work.top)  // 2

    INJECT_JS = """
    (function() {
        var s = document.createElement('style');
        s.textContent = `
            #site-header, .site-footer, .ad-unit,
            .foobar-banner, #js-donation-banner { display: none !important; }
            body { padding-top: 0 !important; }
        `;
        document.head.appendChild(s);
    })();
    """

    w = webview.create_window(
        f"Pokédex — {name.title()}",
        url,
        width=w_width,
        height=w_height,
        resizable=True,
    )

    def on_loaded():
        import time; time.sleep(1)
        try:
            w.evaluate_js(INJECT_JS)
        except Exception:
            pass

    w.events.loaded += on_loaded
    webview.start()


# ── Music player window (runs as subprocess) ──────────────────────────────────

def run_music_player():
    try:
        import pygame
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
    except Exception as e:
        root = tk.Tk(); root.withdraw()
        from tkinter import messagebox
        messagebox.showerror("Music Player", f"pygame unavailable:\n{e}")
        return

    KHI = "https://downloads.khinsider.com"
    UA  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # ── Scraping helpers ───────────────────────────────────────────────────────

    def fetch(url):
        # urllib requires ASCII-only URLs.  Percent-encode any stray unicode
        # (e.g. é in pokémon slugs) without double-encoding existing % sequences.
        try:
            url.encode("ascii")
        except UnicodeEncodeError:
            url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%")
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", errors="replace")

    def parse_dur(s):
        p = s.strip().split(":")
        try:
            return int(p[0]) * 60 + int(p[1]) if len(p) == 2 else 0
        except ValueError:
            return 0

    def fmt_dur(secs):
        return f"{secs // 60}:{secs % 60:02d}"

    def scrape_album(slug):
        """Return list of (name, dur_str, dur_secs, detail_url) for tracks >= 60 s."""
        url  = KHI + "/game-soundtracks/album/" + urllib.parse.quote(slug, safe="-_.")
        page = fetch(url)
        tracks = []
        # Split into <tr> blocks; each track row contains a .mp3 detail-page link
        for row in re.split(r'(?=<tr[\s>])', page, flags=re.IGNORECASE):
            m = re.search(
                r'href="(/game-soundtracks/album/[^"]+\.mp3)"[^>]*>(.*?)</a>',
                row, re.IGNORECASE | re.DOTALL,
            )
            if not m:
                continue
            path = m.group(1)
            name = _html_unescape.unescape(
                re.sub(r'<[^>]+>', '', m.group(2)).strip()
            )
            if not name:
                continue
            # Duration (M:SS or MM:SS) appears in the cells after the track link
            dm = re.search(r'\b(\d{1,3}:\d{2})\b', row[m.end(): m.end() + 500])
            if not dm:
                continue
            dur_str  = dm.group(1)
            dur_secs = parse_dur(dur_str)
            if dur_secs < 60:
                continue
            tracks.append((name, dur_str, dur_secs, KHI + path))
        return tracks

    def get_audio_url(detail_url):
        """Fetch the track detail page and return the direct CDN MP3 URL."""
        page = fetch(detail_url)
        m = re.search(r'href="(https://[^"]+\.mp3)"', page, re.IGNORECASE)
        return m.group(1) if m else None

    def dl_track(audio_url, dest):
        try:
            audio_url.encode("ascii")
        except UnicodeEncodeError:
            audio_url = urllib.parse.quote(audio_url, safe=":/?#[]@!$&'()*+,;=%")
        req = urllib.request.Request(audio_url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)

    # ── Colours & fonts ────────────────────────────────────────────────────────

    C_BG    = "#1a1a2e"
    C_MID   = "#16213e"
    C_PANEL = "#0f3460"
    C_ACC   = "#e94560"
    C_TEXT  = "#eaeaea"
    C_DIM   = "#7777aa"
    C_BTN   = "#1f305e"
    F_HDR   = ("Comic Sans MS", 12, "bold")
    F_NORM  = ("Comic Sans MS", 9)
    F_MONO  = ("Consolas", 9)
    F_NOW   = ("Comic Sans MS", 10, "bold")
    F_CTRL  = ("Segoe UI Symbol", 14)

    # ── Window ─────────────────────────────────────────────────────────────────

    root = tk.Tk()
    root.title("♫ Pokémon Music Player")
    root.geometry("500x580")
    root.configure(bg=C_BG)
    root.resizable(False, False)

    # Header
    tk.Label(root, text="♫  Pokémon Music Player", font=F_HDR,
             bg=C_MID, fg=C_TEXT, pady=9).pack(fill="x")

    # Soundtrack selector
    sel_row = tk.Frame(root, bg=C_BG, pady=6)
    sel_row.pack(fill="x", padx=10)
    tk.Label(sel_row, text="Soundtrack:", font=F_NORM, bg=C_BG, fg=C_DIM).pack(side="left")
    game_var = tk.StringVar(value=list(MUSIC_ALBUMS)[0])
    om = tk.OptionMenu(sel_row, game_var, *list(MUSIC_ALBUMS))
    om.config(bg=C_BTN, fg=C_TEXT, font=F_NORM,
              activebackground=C_ACC, activeforeground=C_TEXT,
              relief="flat", width=30, anchor="w", highlightthickness=0)
    om["menu"].config(bg=C_BTN, fg=C_TEXT, font=F_NORM,
                      activebackground=C_ACC, activeforeground=C_TEXT)
    om.pack(side="left", padx=6)

    # Status bar
    sv_status = tk.StringVar(value="Select a soundtrack above to load tracks.")
    tk.Label(root, textvariable=sv_status, font=F_NORM, bg=C_BG, fg=C_DIM,
             anchor="w").pack(fill="x", padx=12)

    # Track list
    lb_frame = tk.Frame(root, bg=C_BG)
    lb_frame.pack(fill="both", expand=True, padx=10, pady=(2, 4))
    lb_sb = tk.Scrollbar(lb_frame, orient="vertical",
                         bg=C_PANEL, troughcolor=C_MID, activebackground=C_ACC)
    lb = tk.Listbox(lb_frame, bg=C_MID, fg=C_TEXT,
                    selectbackground=C_PANEL, selectforeground=C_ACC,
                    font=F_MONO, relief="flat", highlightthickness=0,
                    borderwidth=0, yscrollcommand=lb_sb.set, activestyle="none")
    lb_sb.config(command=lb.yview)
    lb_sb.pack(side="right", fill="y")
    lb.pack(side="left", fill="both", expand=True)

    # Now-playing label
    np_frame = tk.Frame(root, bg=C_MID, pady=5)
    np_frame.pack(fill="x")
    sv_np = tk.StringVar(value="♫  No track selected")
    tk.Label(np_frame, textvariable=sv_np, font=F_NOW, bg=C_MID, fg=C_ACC,
             wraplength=470, anchor="w").pack(padx=12, fill="x")

    # Progress bar
    pb_outer = tk.Frame(root, bg=C_MID, pady=3)
    pb_outer.pack(fill="x", padx=12)
    pb_cv = tk.Canvas(pb_outer, height=8, bg=C_PANEL, highlightthickness=0)
    pb_cv.pack(fill="x")
    pb_bar = pb_cv.create_rectangle(0, 0, 0, 8, fill=C_ACC, outline="")

    sv_time = tk.StringVar(value="0:00 / 0:00")
    tk.Label(root, textvariable=sv_time, font=F_NORM,
             bg=C_MID, fg=C_DIM, anchor="e").pack(fill="x", padx=14)

    # Control buttons + volume
    ctrl = tk.Frame(root, bg=C_BG, pady=7)
    ctrl.pack(fill="x")

    def cbtn(txt, cmd):
        b = tk.Button(ctrl, text=txt, font=F_CTRL, bg=C_BTN, fg=C_TEXT,
                      activebackground=C_ACC, activeforeground=C_TEXT,
                      relief="flat", width=3, cursor="hand2", command=cmd)
        b.pack(side="left", padx=3)
        return b

    btn_prev = cbtn("⏮", lambda: do_prev())
    btn_stop = cbtn("⏹", lambda: do_stop())
    btn_play = cbtn("▶", lambda: do_toggle())
    btn_next = cbtn("⏭", lambda: do_next())
    btn_shuf = cbtn("🔀", lambda: do_shuffle())

    tk.Label(ctrl, text="Vol", font=F_NORM, bg=C_BG, fg=C_DIM).pack(side="left", padx=(12, 2))
    vol_var = tk.DoubleVar(value=70.0)
    tk.Scale(ctrl, from_=0, to=100, orient="horizontal", variable=vol_var,
             bg=C_BG, fg=C_TEXT, troughcolor=C_PANEL, activebackground=C_ACC,
             highlightthickness=0, relief="flat", length=150, sliderlength=14,
             showvalue=False,
             command=lambda v: pygame.mixer.music.set_volume(float(v) / 100)
             ).pack(side="left")
    pygame.mixer.music.set_volume(0.70)

    # ── Player state ───────────────────────────────────────────────────────────

    st = dict(
        tracks=[], idx=-1,
        playing=False, paused=False, shuffle=False,
        shuf_order=[], shuf_pos=0,
        t_start=0.0, t_offset=0.0, dur_secs=0,
        tmp=None, loading=False,
    )

    # ── Load album ─────────────────────────────────────────────────────────────

    def load_game(game):
        if st["loading"]:
            return
        do_stop()
        lb.delete(0, "end")
        st.update(tracks=[], idx=-1, loading=True)
        sv_status.set(f"Loading {game}…")

        def _worker():
            slugs = MUSIC_ALBUMS[game]
            all_tracks = []
            for slug in slugs:
                try:
                    t = scrape_album(slug)
                    all_tracks.extend(t)
                    root.after(0, lambda n=len(all_tracks):
                               sv_status.set(f"Loading…  {n} tracks found so far"))
                except Exception as ex:
                    root.after(0, lambda e=str(ex):
                               sv_status.set(f"Error loading album: {e}"))
            root.after(0, lambda: _finish(game, all_tracks))

        threading.Thread(target=_worker, daemon=True).start()

    def _finish(game, tracks):
        st["loading"] = False
        st["tracks"]  = tracks
        st["shuf_order"] = list(range(len(tracks)))
        random.shuffle(st["shuf_order"])
        lb.delete(0, "end")
        for name, dur_str, _, _ in tracks:
            lb.insert("end", f"  {name[:46]:<46}  {dur_str:>5}")
        sv_status.set(f"{game}  —  {len(tracks)} tracks (≥ 1 min)  •  double-click to play")

    # ── Playback ───────────────────────────────────────────────────────────────

    def play_idx(idx):
        if idx < 0 or idx >= len(st["tracks"]):
            return
        st["idx"] = idx
        name, dur_str, dur_secs, detail_url = st["tracks"][idx]
        sv_np.set(f"⏳  Loading: {name}")
        lb.selection_clear(0, "end")
        lb.selection_set(idx)
        lb.see(idx)
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        st["playing"] = False

        def _worker():
            try:
                audio_url = get_audio_url(detail_url)
                if not audio_url:
                    root.after(0, lambda: sv_np.set(f"✗  Could not resolve audio for: {name}"))
                    return
                tf = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tf.close()
                dl_track(audio_url, tf.name)
                root.after(0, lambda: _start(idx, tf.name, name, dur_str, dur_secs))
            except Exception as ex:
                root.after(0, lambda e=str(ex): sv_np.set(f"✗  {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _start(idx, path, name, dur_str, dur_secs):
        # Guard: user may have changed track while we were downloading
        if st["idx"] != idx:
            try: os.unlink(path)
            except Exception: pass
            return
        old = st["tmp"]
        st["tmp"] = path
        if old:
            try: os.unlink(old)
            except Exception: pass
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(vol_var.get() / 100)
            pygame.mixer.music.play()
            st.update(playing=True, paused=False,
                      t_start=time.time(), t_offset=0.0, dur_secs=dur_secs)
            sv_np.set(f"♫  {name}  [{dur_str}]")
            btn_play.config(text="⏸")
        except Exception as ex:
            sv_np.set(f"✗  Playback error: {ex}")

    def do_toggle():
        if not st["playing"] and st["idx"] < 0:
            if st["tracks"]:
                play_idx(0)
            return
        if not st["playing"]:
            return
        if st["paused"]:
            pygame.mixer.music.unpause()
            st["paused"]  = False
            st["t_start"] = time.time() - st["t_offset"]
            btn_play.config(text="⏸")
        else:
            pygame.mixer.music.pause()
            st["paused"]   = True
            st["t_offset"] = time.time() - st["t_start"]
            btn_play.config(text="▶")

    def do_stop():
        try: pygame.mixer.music.stop()
        except Exception: pass
        st.update(playing=False, paused=False, t_start=0.0, t_offset=0.0)
        btn_play.config(text="▶")
        sv_np.set("♫  Stopped")
        sv_time.set("0:00 / 0:00")
        pb_cv.coords(pb_bar, 0, 0, 0, 8)

    def do_next():
        if not st["tracks"]: return
        if st["shuffle"]:
            st["shuf_pos"] = (st["shuf_pos"] + 1) % len(st["shuf_order"])
            play_idx(st["shuf_order"][st["shuf_pos"]])
        else:
            play_idx((st["idx"] + 1) % len(st["tracks"]))

    def do_prev():
        if not st["tracks"]: return
        if st["shuffle"]:
            st["shuf_pos"] = (st["shuf_pos"] - 1) % len(st["shuf_order"])
            play_idx(st["shuf_order"][st["shuf_pos"]])
        else:
            play_idx((st["idx"] - 1) % len(st["tracks"]))

    def do_shuffle():
        st["shuffle"] = not st["shuffle"]
        if st["shuffle"]:
            st["shuf_order"] = list(range(len(st["tracks"])))
            random.shuffle(st["shuf_order"])
            btn_shuf.config(fg=C_ACC)
        else:
            btn_shuf.config(fg=C_TEXT)

    # ── Progress ticker (runs every 500 ms) ────────────────────────────────────

    def tick():
        if st["playing"] and not st["paused"]:
            if not pygame.mixer.music.get_busy():
                # Track finished — auto-advance
                st["playing"] = False
                btn_play.config(text="▶")
                root.after(600, do_next)
            else:
                elapsed = time.time() - st["t_start"]
                total   = st["dur_secs"]
                if total > 0:
                    frac = min(elapsed / total, 1.0)
                    w = pb_cv.winfo_width()
                    pb_cv.coords(pb_bar, 0, 0, int(w * frac), 8)
                    sv_time.set(f"{fmt_dur(int(elapsed))} / {fmt_dur(total)}")
        root.after(500, tick)

    # ── Wire events ────────────────────────────────────────────────────────────

    def _on_dbl(event):
        sel = lb.curselection()
        if sel:
            play_idx(sel[0])

    lb.bind("<Double-Button-1>", _on_dbl)
    game_var.trace_add("write", lambda *_: load_game(game_var.get()))

    def on_close():
        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except Exception:
            pass
        if st["tmp"]:
            try: os.unlink(st["tmp"])
            except Exception: pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(200, tick)
    root.after(500, lambda: load_game(game_var.get()))
    root.mainloop()


def main():
    if "--pokemon" in sys.argv:
        run_pokemon_game()
        return

    if "--tcg" in sys.argv:
        idx = sys.argv.index("--tcg")
        query = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if query:
            run_tcg_lookup(query)
        return

    if "--timer" in sys.argv:
        idx = sys.argv.index("--timer")
        minutes = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "50"
        run_timer(minutes)
        return

    if "--pokedex" in sys.argv:
        idx = sys.argv.index("--pokedex")
        name = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if name:
            run_pokedex(name)
        return

    if "--music" in sys.argv:
        run_music_player()
        return

    lock = acquire_lock()
    root = tk.Tk()
    root.after(0, lambda: root.bind("<Destroy>", lambda e: lock.close()))
    PoryCompanion(root)
    root.mainloop()


if __name__ == "__main__":
    main()
