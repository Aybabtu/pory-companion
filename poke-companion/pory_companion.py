import tkinter as tk
from PIL import Image, ImageTk
import os, socket, sys, math, threading, json, random, subprocess, time
import urllib.request
import ctypes, ctypes.wintypes
import psutil
from datetime import datetime

SCRIPT_DIR  = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
GIF_FRONT   = os.path.join(SCRIPT_DIR, "pory.gif")
GIF_BACK    = os.path.join(SCRIPT_DIR, "pory B.gif")
BUDEW_FRONT = os.path.join(SCRIPT_DIR, "budew.gif")
BUDEW_BACK  = os.path.join(SCRIPT_DIR, "budew B.gif")
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

# Bubble geometry
BW, BH  = 230, 165   # body width / height
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
            text="Enter card name & number:",
            font=FONT_LABEL, fill=BUBBLE_FG,
        )
        self.canvas.create_text(
            PAD + BW // 2, PAD + 38,
            text='e.g. "Snorunt 046/217"',
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


# ── Chat bubble with option buttons ───────────────────────────────────────────

class ChatBubble:
    def __init__(self, parent_root, actions):
        """actions: list of (label, callback)"""
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
            text="What would we like to do today?",
            font=FONT_LABEL, fill=BUBBLE_FG,
        )

        btn_frame = tk.Frame(self.win, bg=BUBBLE_BG)
        self.canvas.create_window(PAD + BW // 2, PAD + 100, window=btn_frame)

        for label, cb in actions:
            btn = tk.Button(
                btn_frame, text=label, font=FONT_BTN,
                fg="#ffffff", bg="#5b7fa6",
                activebackground="#3d5a80", activeforeground="#ffffff",
                relief="flat", padx=10, pady=3, cursor="hand2",
                width=22,
                command=lambda c=cb: (self.close(), c()),
            )
            btn.pack(pady=2)

        self.win.bind("<Escape>", lambda e: self.close())
        self.win.bind("<FocusOut>", self._on_focus_out)

    def position_near(self, px, py):
        bx = px - (PAD + TAIL_X + 20)
        by = py - (PAD * 2 + BH + TAIL_H + 2)
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
        self.frames_front      = load_frames(GIF_FRONT)
        self.frames_front_flip = load_frames(GIF_FRONT, flip=True)
        self.frames_back       = load_frames(GIF_BACK)
        self.frames_back_flip  = load_frames(GIF_BACK,  flip=True)
        self.frame_index       = 0
        self._bubble           = None
        self._weather_win      = None

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"+{sw - 130}+{sh // 2}")

        self.label.bind("<ButtonPress-1>",   self._drag_start)
        self.label.bind("<B1-Motion>",       self._drag_motion)
        self.label.bind("<ButtonRelease-1>", self._on_release)
        self.label.bind("<Button-3>",        self._on_right_click)

        self._drag_x = self._drag_y = 0
        self._dragging = False
        self._glancing = False
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


    @property
    def _frames(self):
        if self._roaming:
            if self._roam_dir == "right":
                return self.frames_front_flip
            else:
                return self.frames_back_flip
        return self.frames_front if self.facing_front else self.frames_back

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
            if self._dragging:
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
                ("🌤 Weather",        self._show_weather),
                ("❓ Who's That?",   self._show_pokemon),
                ("💰 Card Prices",   self._show_tcg_search),
            ]
            self._bubble = ChatBubble(self.root, actions)
            self._bubble.position_near(self.root.winfo_x(), self.root.winfo_y())
            self._bubble.win.bind("<Destroy>", lambda e: self._clear_bubble())

    def _clear_bubble(self):
        self._bubble = None

    def _on_right_click(self, event):
        menu = tk.Menu(self.root, tearoff=0, font=("Comic Sans MS", 10))
        menu.add_command(label="Quit", command=self.root.destroy)
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
        subprocess.Popen([sys.executable, __file__, "--pokemon"],
                         creationflags=subprocess.CREATE_NO_WINDOW
                         if sys.platform == "win32" else 0)

    # ── TCG Card Prices ───────────────────────────────────────────────────────

    def _show_tcg_search(self):
        TCGSearchBubble(self.root, on_submit=self._launch_tcg_lookup,
                        companion_xy=(self.root.winfo_x(), self.root.winfo_y()))

    def _launch_tcg_lookup(self, query):
        subprocess.Popen(
            [sys.executable, __file__, "--tcg", query],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )


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

    lock = acquire_lock()
    root = tk.Tk()
    root.after(0, lambda: root.bind("<Destroy>", lambda e: lock.close()))
    PoryCompanion(root)
    root.mainloop()


if __name__ == "__main__":
    main()
