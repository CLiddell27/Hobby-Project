"""
Retro Game Picker Wheel
A spinning wheel app that picks a random retro console then a random game,
with persistent history and editable libraries.
"""

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, simpledialog, filedialog
import json
import math
import random
import time
import os
import sys

# ---
def data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~")
    d = os.path.join(base, "RetroPickerWheel")
    os.makedirs(d, exist_ok=True)
    return d

HISTORY_FILE = os.path.join(data_dir(), "history.json")
CONSOLES_FILE = os.path.join(data_dir(), "consoles.json")

# ---
DEFAULT_DB = []

# ---
def load_consoles():
    if os.path.exists(CONSOLES_FILE):
        try:
            with open(CONSOLES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return [dict(c) for c in DEFAULT_DB]

def save_consoles(db):
    with open(CONSOLES_FILE, "w") as f:
        json.dump(db, f, indent=2)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def dedupe_keep_order(items):
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out

# ---
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
    )

def blend_color(base_hex, i, n):
    r, g, b = hex_to_rgb(base_hex)
    # alternate lighter/darker bands
    shift = 35 if i % 2 == 0 else -20
    return rgb_to_hex(r + shift, g + shift, b + shift)

def contrasting_text(bg_hex):
    r, g, b = hex_to_rgb(bg_hex)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.5 else "#ffffff"

# ---
class RetroPickerApp(tk.Tk):
    PALETTE = [
        "#b71c1c","#880e4f","#4a148c","#283593","#01579b","#006064",
        "#1b5e20","#33691e","#e65100","#bf360c","#3e2723","#546e7a",
        "#4527a0","#1565c0","#00695c","#2e7d32",
    ]

    def __init__(self):
        super().__init__()
        self.title("Retro Game Picker Wheel")
        self.resizable(True, True)
        self.configure(bg="#1a1a2e")

        # State
        self.db = load_consoles()
        self.history = load_history()
        self.phase = 1
        self.chosen_console = None
        self.wheel_items = []   # list of (label, color)
        self.console_pickable_indices = []
        self.wheel_size = 520
        self.angle = 0.0
        self.spinning = False
        self._spin_job = None
        self._anim_start = 0.0
        self._anim_delta = 0.0
        self._anim_angle0 = 0.0
        self._anim_dur = 5.0

        self._build_ui()
        self._set_console_phase()

    # ---
    def _build_ui(self):
        # ---
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background="#1a1a2e", borderwidth=0)
        style.configure("TNotebook.Tab", background="#16213e", foreground="#aaaacc",
                        padding=[12, 5], font=("Segoe UI", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", "#0f3460")],
                  foreground=[("selected", "#e0e0ff")])
        style.configure("TFrame", background="#1a1a2e")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.tab_wheel   = ttk.Frame(self.nb)
        self.tab_history = ttk.Frame(self.nb)
        self.tab_manage  = ttk.Frame(self.nb)

        self.nb.add(self.tab_wheel,   text=" Wheel ")
        self.nb.add(self.tab_history, text=" History ")
        self.nb.add(self.tab_manage,  text=" Manage ")

        self._build_wheel_tab()
        self._build_history_tab()
        self._build_manage_tab()

    # ---
    def _build_wheel_tab(self):
        f = self.tab_wheel
        f.configure(style="TFrame")

        self.phase_label = tk.Label(f, text="", bg="#1a1a2e", fg="#7777aa",
                                    font=("Segoe UI", 9), pady=6)
        self.phase_label.pack()

        # canvas + pointer row
        row = tk.Frame(f, bg="#1a1a2e")
        row.pack()

        self.canvas = tk.Canvas(row, width=self.wheel_size, height=self.wheel_size,
                                bg="#1a1a2e", highlightthickness=0)
        self.canvas.pack(side="left")

        ptr = tk.Frame(row, bg="#1a1a2e")
        ptr.pack(side="left")
        self.ptr_canvas = tk.Canvas(ptr, width=28, height=30,
                                    bg="#1a1a2e", highlightthickness=0)
        self.ptr_canvas.pack()
        self.ptr_canvas.create_polygon(0, 0, 0, 30, 26, 15, fill="#ef5350", outline="")

        # live indicator
        self.live_label = tk.Label(f, text="", bg="#1a1a2e", fg="#aaaacc",
                                   font=("Segoe UI", 10, "italic"), pady=4)
        self.live_label.pack()

        # buttons
        btn_row = tk.Frame(f, bg="#1a1a2e", pady=6)
        btn_row.pack()

        self.spin_btn = tk.Button(btn_row, text="SPIN", font=("Segoe UI", 11, "bold"),
                                  bg="#0f3460", fg="#e0e0ff", activebackground="#1a5276",
                                  relief="flat", padx=20, pady=8, cursor="hand2",
                                  command=self.spin)
        self.spin_btn.pack(side="left", padx=6)

        self.manual_btn = tk.Button(btn_row, text="PICK CONSOLE", font=("Segoe UI", 10, "bold"),
                        bg="#1f5a42", fg="#e0ffe0", activebackground="#2b7658",
                        relief="flat", padx=14, pady=8, cursor="hand2",
                        command=self._manual_pick)
        self.manual_btn.pack(side="left", padx=6)

        self.reset_btn = tk.Button(btn_row, text="RESET", font=("Segoe UI", 10),
                                   bg="#2c2c4a", fg="#aaaacc", activebackground="#3a3a5a",
                                   relief="flat", padx=14, pady=8, cursor="hand2",
                                   command=self.reset)
        self.reset_btn.pack(side="left", padx=6)
        self.reset_btn.pack_forget()

        # result box
        self.result_frame = tk.Frame(f, bg="#16213e", padx=16, pady=12)
        self.result_lbl   = tk.Label(self.result_frame, text="", bg="#16213e",
                                     fg="#7777aa", font=("Segoe UI", 8))
        self.result_lbl.pack()
        self.result_text  = tk.Label(self.result_frame, text="", bg="#16213e",
                                     fg="#e0e0ff", font=("Segoe UI", 16, "bold"),
                                     wraplength=440)
        self.result_text.pack()
        self.result_btn_frame = tk.Frame(self.result_frame, bg="#16213e", pady=8)
        self.result_btn_frame.pack()

    # ---
    def _build_history_tab(self):
        f = self.tab_history
        f.configure(style="TFrame")

        top = tk.Frame(f, bg="#1a1a2e")
        top.pack(fill="x", padx=12, pady=10)
        tk.Label(top, text="Roll History", bg="#1a1a2e", fg="#e0e0ff",
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Button(top, text="Clear History", bg="#3a1a1a", fg="#ff7777",
                  font=("Segoe UI", 9), relief="flat", padx=10, pady=4,
                  cursor="hand2", command=self._clear_history).pack(side="right")

        style = ttk.Style()
        style.configure("Treeview", background="#16213e", foreground="#ccccee",
                        fieldbackground="#16213e", rowheight=26,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#0f3460", foreground="#e0e0ff",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#1a5276")])

        self.history_nb = ttk.Notebook(f)
        self.history_nb.pack(fill="both", expand=True, padx=12, pady=4)
        self.history_all_tree = None
        self.history_console_trees = {}

        self._rebuild_history_tabs()

        self._refresh_history_tree()

    # ---
    def _build_manage_tab(self):
        f = self.tab_manage
        f.configure(style="TFrame")

        panes = tk.PanedWindow(f, orient="horizontal", bg="#1a1a2e",
                               sashrelief="flat", sashwidth=6)
        panes.pack(fill="both", expand=True, padx=8, pady=8)

        # ---
        left = tk.Frame(panes, bg="#1a1a2e", width=200)
        panes.add(left, minsize=180)

        tk.Label(left, text="Consoles", bg="#1a1a2e", fg="#e0e0ff",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 4))

        self.console_lb = tk.Listbox(left, bg="#16213e", fg="#ccccee",
                                     selectbackground="#0f3460", selectforeground="#e0e0ff",
                                     font=("Segoe UI", 10), relief="flat",
                                     activestyle="none", cursor="hand2")
        self.console_lb.pack(fill="both", expand=True, padx=8)
        self.console_lb.bind("<<ListboxSelect>>", self._on_console_select)

        lb_btns = tk.Frame(left, bg="#1a1a2e")
        lb_btns.pack(fill="x", padx=8, pady=6)
        tk.Button(lb_btns, text="+ Add", bg="#0f3460", fg="#e0e0ff",
                  font=("Segoe UI", 9), relief="flat", padx=8, pady=4,
                  cursor="hand2", command=self._new_console).pack(side="left", padx=(0, 4))
        tk.Button(lb_btns, text="Delete", bg="#3a1a1a", fg="#ff7777",
                  font=("Segoe UI", 9), relief="flat", padx=8, pady=4,
                  cursor="hand2", command=self._delete_console).pack(side="left")
        tk.Button(lb_btns, text="^", bg="#2c2c4a", fg="#aaaacc",
                  font=("Segoe UI", 9), relief="flat", padx=6, pady=4,
                  cursor="hand2", command=lambda: self._move_console(-1)).pack(side="right")
        tk.Button(lb_btns, text="v", bg="#2c2c4a", fg="#aaaacc",
                  font=("Segoe UI", 9), relief="flat", padx=6, pady=4,
                  cursor="hand2", command=lambda: self._move_console(1)).pack(side="right", padx=(0, 4))

        import_row = tk.Frame(left, bg="#1a1a2e")
        import_row.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(import_row, text="Import Consoles", bg="#2c2c4a", fg="#ccccee",
              font=("Segoe UI", 9), relief="flat", padx=8, pady=4,
              cursor="hand2", command=self._import_consoles_list).pack(fill="x")

        # ---
        right = tk.Frame(panes, bg="#1a1a2e")
        panes.add(right, minsize=300)

        tk.Label(right, text="Console Editor", bg="#1a1a2e", fg="#e0e0ff",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 6))

        form = tk.Frame(right, bg="#1a1a2e")
        form.pack(fill="x", padx=8)

        # Name + color row
        name_row = tk.Frame(form, bg="#1a1a2e")
        name_row.pack(fill="x", pady=(0, 6))
        tk.Label(name_row, text="Name:", bg="#1a1a2e", fg="#7777aa",
                 font=("Segoe UI", 9)).pack(side="left")
        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(name_row, textvariable=self.name_var,
                                   bg="#16213e", fg="#e0e0ff", insertbackground="#e0e0ff",
                                   font=("Segoe UI", 10), relief="flat", width=22)
        self.name_entry.pack(side="left", padx=6)

        self.color_preview = tk.Canvas(name_row, width=28, height=28,
                                       bg="#1a1a2e", highlightthickness=1,
                                       highlightbackground="#444466", cursor="hand2")
        self.color_preview.pack(side="left", padx=2)
        self._selected_color = "#1565c0"
        self._draw_color_preview()
        self.color_preview.bind("<Button-1>", self._pick_color)
        tk.Label(name_row, text="Color", bg="#1a1a2e", fg="#7777aa",
                 font=("Segoe UI", 8)).pack(side="left", padx=2)

        # Games text box
        games_hdr = tk.Frame(form, bg="#1a1a2e")
        games_hdr.pack(fill="x")
        tk.Label(games_hdr, text="Games (one per line):", bg="#1a1a2e", fg="#7777aa",
             font=("Segoe UI", 9)).pack(side="left")
        tk.Button(games_hdr, text="Import Games", bg="#2c2c4a", fg="#ccccee",
              font=("Segoe UI", 8), relief="flat", padx=8, pady=3,
              cursor="hand2", command=self._import_games_list).pack(side="right")
        games_frame = tk.Frame(form, bg="#1a1a2e")
        games_frame.pack(fill="both", expand=True, pady=(4, 6))
        self.games_text = tk.Text(games_frame, bg="#16213e", fg="#ccccee",
                                  insertbackground="#ccccee", font=("Segoe UI", 9),
                                  relief="flat", wrap="word", height=18)
        gscroll = ttk.Scrollbar(games_frame, command=self.games_text.yview)
        self.games_text.configure(yscrollcommand=gscroll.set)
        self.games_text.pack(side="left", fill="both", expand=True)
        gscroll.pack(side="left", fill="y")

        self.game_count_lbl = tk.Label(form, text="", bg="#1a1a2e", fg="#7777aa",
                                       font=("Segoe UI", 8))
        self.game_count_lbl.pack(anchor="e")
        self.games_text.bind("<KeyRelease>", self._update_game_count)

        # Save / Reset defaults
        save_row = tk.Frame(form, bg="#1a1a2e")
        save_row.pack(fill="x", pady=4)
        tk.Button(save_row, text="Save Console", bg="#0f3460", fg="#e0e0ff",
                  font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=6,
                  cursor="hand2", command=self._save_console).pack(side="left", padx=(0, 6))
        tk.Button(save_row, text="Clear Consoles", bg="#2c2c4a", fg="#aaaacc",
                  font=("Segoe UI", 9), relief="flat", padx=10, pady=6,
                  cursor="hand2", command=self._reset_defaults).pack(side="left")

        self._editing_idx = -1
        self._refresh_console_list()

    # ---
    def _draw_wheel(self, highlight_idx=-1):
        c = self.canvas
        c.delete("all")
        n = len(self.wheel_items)
        w = int(c.cget("width"))
        h = int(c.cget("height"))
        cx, cy = w // 2, h // 2
        r = min(w, h) // 2 - 12
        if n == 0:
            c.create_text(cx, cy, text="No items", fill="#555577",
                          font=("Segoe UI", 14))
            return

        arc = 2 * math.pi / n
        show_labels = n <= 40

        for i, (label, color) in enumerate(self.wheel_items):
            start = math.degrees(self.angle + i * arc)
            extent = math.degrees(arc)
            # segment
            c.create_arc(cx - r, cy - r, cx + r, cy + r,
                         start=start, extent=extent,
                         fill=color, outline="#ffffff", width=1, style="pieslice")
            if show_labels:
                mid_angle = self.angle + i * arc + arc / 2
                tr = r * 0.7
                tx = cx + tr * math.cos(mid_angle)
                ty = cy - tr * math.sin(mid_angle)
                fs = max(7, min(13, int(220 / n)))
                txt = label if len(label) <= 18 else label[:17] + "..."
                c.create_text(tx, ty, text=txt, fill=contrasting_text(color),
                              font=("Segoe UI", fs, "bold"),
                              width=max(40, int(r * 0.8)))

        # highlight ring
        if highlight_idx >= 0:
            i = highlight_idx
            start = math.degrees(self.angle + i * arc)
            c.create_arc(cx - r, cy - r, cx + r, cy + r,
                         start=start, extent=math.degrees(arc),
                         fill="", outline="#ffffff", width=3, style="pieslice")

        # rim
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      outline="#333355", width=5)
        # hub
        c.create_oval(cx - 18, cy - 18, cx + 18, cy + 18,
                      fill="#ffffff", outline="#cccccc", width=1)
        c.create_text(cx, cy, text=">", fill="#555577",
                      font=("Segoe UI", 11, "bold"))

    def _get_pointed_idx(self):
        n = len(self.wheel_items)
        if n == 0:
            return 0
        arc = 2 * math.pi / n
        # pointer is at the right (0 deg). We want segment at angle=0
        norm = (-self.angle % (2 * math.pi) + 2 * math.pi) % (2 * math.pi)
        return int(norm / arc) % n

    # ---
    def spin(self):
        if self.spinning:
            return
        n = len(self.wheel_items)
        if n == 0:
            return

        selectable = self._selectable_indices()
        if not selectable:
            messagebox.showinfo(
                "No selectable consoles",
                "All consoles are out of available games. Clear history or add games to continue.",
            )
            return

        self.spinning = True
        self.spin_btn.configure(state="disabled")
        self.manual_btn.configure(state="disabled")
        self.result_frame.pack_forget()

        arc = 2 * math.pi / n
        target_idx = random.choice(selectable)
        # land in middle of target segment
        extra_rotations = (7 + random.random() * 6) * 2 * math.pi
        current_norm = (-self.angle % (2 * math.pi) + 2 * math.pi) % (2 * math.pi)
        target_angle = target_idx * arc + arc / 2
        # how much to add to angle to make target_angle land at 0
        needed = target_angle - current_norm
        if needed < 0:
            needed += 2 * math.pi
        self._anim_delta  = extra_rotations + needed
        self._anim_angle0 = self.angle
        self._anim_dur    = 4.5 + random.random() * 2.0
        self._anim_start  = time.perf_counter()
        self._last_seg    = -1
        self._animate()

    def _ease(self, t):
        return 1 - (1 - t) ** 3.5

    def _animate(self):
        t = (time.perf_counter() - self._anim_start) / self._anim_dur
        t = min(t, 1.0)
        self.angle = self._anim_angle0 + self._anim_delta * self._ease(t)

        pi = self._get_pointed_idx()
        self._draw_wheel(pi)
        name = self.wheel_items[pi][0] if self.wheel_items else ""
        self.live_label.configure(text=name)

        # tick sound via Tk bell if segment changes
        if pi != self._last_seg:
            self._last_seg = pi

        if t < 1.0:
            self._spin_job = self.after(16, self._animate)
        else:
            self.spinning = False
            self.spin_btn.configure(state="normal")
            self.manual_btn.configure(state="normal")
            self.live_label.configure(text="")
            final = self._get_pointed_idx()

            if self.phase == 1:
                selectable = self._selectable_indices()
                if selectable and final not in selectable:
                    final = random.choice(selectable)
                    self._draw_wheel(final)

            label, _ = self.wheel_items[final]
            self._show_result(label)

    def _manual_pick(self):
        if self.spinning:
            return

        if self.phase == 1:
            options = [self.db[i]["name"] for i in self.console_pickable_indices]
            if not options:
                messagebox.showinfo(
                    "No selectable consoles",
                    "All consoles are out of available games. Clear history or add games to continue.",
                )
                return
            picked = self._choose_from_list(
                "Manual Console Pick",
                "Choose a console:",
                options,
            )
        else:
            options = [label for label, _ in self.wheel_items]
            if not options:
                messagebox.showinfo("No games", "No games are available to pick.")
                return
            picked = self._choose_from_list(
                "Manual Game Pick",
                f"Choose a game for {self.chosen_console}:",
                options,
            )

        if picked:
            self.result_frame.pack_forget()
            self._show_result(picked)

    def _choose_from_list(self, title, prompt, items):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.configure(bg="#1a1a2e")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text=prompt, bg="#1a1a2e", fg="#e0e0ff",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        holder = tk.Frame(dialog, bg="#1a1a2e")
        holder.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        lb = tk.Listbox(holder, width=52, height=14,
                        bg="#16213e", fg="#ccccee", font=("Segoe UI", 10),
                        selectbackground="#0f3460", selectforeground="#e0e0ff",
                        relief="flat", activestyle="none")
        sb = ttk.Scrollbar(holder, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

        for item in items:
            lb.insert("end", item)
        if items:
            lb.selection_set(0)

        result = {"value": None}

        def accept(_=None):
            sel = lb.curselection()
            if not sel:
                return
            result["value"] = lb.get(sel[0])
            dialog.destroy()

        def cancel(_=None):
            dialog.destroy()

        btns = tk.Frame(dialog, bg="#1a1a2e")
        btns.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(btns, text="Cancel", bg="#2c2c4a", fg="#aaaacc",
                  font=("Segoe UI", 9), relief="flat", padx=10, pady=4,
                  cursor="hand2", command=cancel).pack(side="right")
        tk.Button(btns, text="Pick", bg="#0f3460", fg="#e0e0ff",
                  font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=4,
                  cursor="hand2", command=accept).pack(side="right", padx=(0, 6))

        lb.bind("<Double-Button-1>", accept)
        dialog.bind("<Return>", accept)
        dialog.bind("<Escape>", cancel)

        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

        lb.focus_set()
        self.wait_window(dialog)
        return result["value"]

    # ---
    def _set_console_phase(self):
        self.phase = 1
        self.console_pickable_indices = []
        self.wheel_items = []
        for idx, con in enumerate(self.db):
            is_pickable = len(self._available_games_for_console(con["name"])) > 0
            color = con["color"] if is_pickable else "#7a7a86"
            self.wheel_items.append((con["name"], color))
            if is_pickable:
                self.console_pickable_indices.append(idx)

        self.angle = 0.0
        available = len(self.console_pickable_indices)
        self.phase_label.configure(
            text=f"STEP 1 - PICK A CONSOLE   ({available}/{len(self.db)} available)")
        self.reset_btn.pack_forget()
        self.result_frame.pack_forget()
        self.live_label.configure(text="")
        self.spin_btn.configure(state="normal" if available else "disabled")
        self.manual_btn.configure(text="PICK CONSOLE",
                      state="normal" if available else "disabled")
        self._rebuild_history_tabs()
        self._refresh_history_tree()
        self._draw_wheel()

    def _set_game_phase(self):
        self.phase = 2
        con = next((c for c in self.db if c["name"] == self.chosen_console), None)
        if not con or not con["games"]:
            messagebox.showinfo("No games", f"No games found for {self.chosen_console}.")
            self.reset()
            return

        games = self._available_games_for_console(self.chosen_console)
        if not games:
            messagebox.showinfo(
                "No games left",
                f"All games for {self.chosen_console} have already been picked.\n"
                "Clear history to make them available again.",
            )
            self.reset()
            return

        base  = con["color"]
        self.wheel_items = [(g, blend_color(base, i, len(games)))
                            for i, g in enumerate(games)]
        self.angle = 0.0
        self.phase_label.configure(
            text=f"STEP 2 - PICK A {self.chosen_console.upper()} GAME   ({len(games)} games)")
        self.reset_btn.pack(side="left", padx=6)
        self.result_frame.pack_forget()
        self.live_label.configure(text="")
        self.manual_btn.configure(text="PICK GAME", state="normal")
        self._draw_wheel()

    def _show_result(self, name):
        for w in self.result_btn_frame.winfo_children():
            w.destroy()
        self.result_text.configure(text=name)
        if self.phase == 1:
            if not self._available_games_for_console(name):
                messagebox.showinfo(
                    "No games left",
                    f"{name} has no games left to pick. Add games or clear history.",
                )
                self._set_console_phase()
                return
            self.chosen_console = name
            self.result_lbl.configure(text="CONSOLE SELECTED")
            tk.Button(self.result_btn_frame,
                      text=f"Pick a {name} game  ->",
                      bg="#0f3460", fg="#e0e0ff",
                      font=("Segoe UI", 10, "bold"),
                      relief="flat", padx=14, pady=6, cursor="hand2",
                      command=self._set_game_phase).pack()
        else:
            self.result_lbl.configure(text="YOUR GAME IS")
            entry = {
                "console": self.chosen_console,
                "game":    name,
                "time":    time.strftime("%Y-%m-%d %H:%M"),
            }
            self.history.insert(0, entry)
            save_history(self.history)
            self._refresh_history_tree()

            # Remove the picked game from the current wheel immediately.
            self.wheel_items = [(label, color) for (label, color) in self.wheel_items
                                if label != name]
            self._draw_wheel()

            # Lock further picks until user starts over.
            self.spin_btn.configure(state="disabled")
            self.manual_btn.configure(state="disabled")

            tk.Button(self.result_btn_frame,
                      text="Start over",
                      bg="#2c2c4a", fg="#aaaacc",
                      font=("Segoe UI", 10),
                      relief="flat", padx=14, pady=6, cursor="hand2",
                      command=self.reset).pack()

        self.result_frame.pack(padx=16, pady=(0, 10), fill="x")

    def reset(self):
        self._set_console_phase()

    # ---
    def _refresh_history_tree(self):
        if not hasattr(self, "history_all_tree") or self.history_all_tree is None:
            return

        for row in self.history_all_tree.get_children():
            self.history_all_tree.delete(row)
        for tree in self.history_console_trees.values():
            for row in tree.get_children():
                tree.delete(row)

        sorted_history = sorted(
            self.history,
            key=lambda e: (
                (e.get("console") or "").lower(),
                e.get("time") or "",
            ),
        )
        for entry in sorted_history:
            console = entry.get("console", "")
            self.history_all_tree.insert("", "end",
                                         values=(console,
                                                 entry.get("game", ""),
                                                 entry.get("time", "")))

            tree = self.history_console_trees.get(console)
            if tree is not None:
                tree.insert("", "end",
                            values=(entry.get("game", ""),
                                    entry.get("time", "")))

    def _rebuild_history_tabs(self):
        if not hasattr(self, "history_nb"):
            return

        selected_text = None
        current = self.history_nb.select()
        if current:
            selected_text = self.history_nb.tab(current, "text")

        for tab_id in self.history_nb.tabs():
            self.history_nb.forget(tab_id)

        self.history_console_trees = {}
        self.history_all_tree = self._add_history_tab("All", include_console=True)

        for con in self.db:
            self.history_console_trees[con["name"]] = self._add_history_tab(
                con["name"], include_console=False
            )

        if selected_text:
            for tab_id in self.history_nb.tabs():
                if self.history_nb.tab(tab_id, "text") == selected_text:
                    self.history_nb.select(tab_id)
                    break

    def _add_history_tab(self, title, include_console):
        frame = ttk.Frame(self.history_nb)
        self.history_nb.add(frame, text=title)
        cols = ("console", "game", "time") if include_console else ("game", "time")
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")

        if include_console:
            tree.heading("console", text="Console")
            tree.column("console", width=130, anchor="center")
        tree.heading("game", text="Game")
        tree.heading("time", text="Time")
        tree.column("game", width=340)
        tree.column("time", width=150, anchor="center")

        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)

        tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb.pack(side="left", fill="y", padx=(0, 4), pady=4)
        return tree

    def _selectable_indices(self):
        if self.phase == 1:
            return list(self.console_pickable_indices)
        return list(range(len(self.wheel_items)))

    def _available_games_for_console(self, console_name):
        con = next((c for c in self.db if c["name"] == console_name), None)
        if not con:
            return []
        picked = {
            e.get("game", "")
            for e in self.history
            if (e.get("console") or "").lower() == console_name.lower()
        }
        return [g for g in con["games"] if g not in picked]

    def _clear_history(self):
        if messagebox.askyesno("Clear History", "Delete all roll history?"):
            self.history = []
            save_history(self.history)
            self._refresh_history_tree()
            if self.phase == 1:
                self._set_console_phase()

    # ---
    def _refresh_console_list(self):
        self.console_lb.delete(0, "end")
        for c in self.db:
            self.console_lb.insert("end", f"  {c['name']}  ({len(c['games'])} games)")

    def _on_console_select(self, _=None):
        sel = self.console_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        self._editing_idx = idx
        con = self.db[idx]
        self.name_var.set(con["name"])
        self._selected_color = con["color"]
        self._draw_color_preview()
        self.games_text.delete("1.0", "end")
        self.games_text.insert("end", "\n".join(con["games"]))
        self._update_game_count()

    def _new_console(self):
        self._editing_idx = -1
        self.console_lb.selection_clear(0, "end")
        self.name_var.set("")
        self._selected_color = self.PALETTE[len(self.db) % len(self.PALETTE)]
        self._draw_color_preview()
        self.games_text.delete("1.0", "end")
        self._update_game_count()
        self.name_entry.focus()

    def _save_console(self):
        name  = self.name_var.get().strip()
        color = self._selected_color
        raw   = self.games_text.get("1.0", "end")
        games = [g.strip() for g in raw.splitlines() if g.strip()]

        if not name:
            messagebox.showerror("Error", "Console name cannot be empty.")
            return
        if not games:
            messagebox.showerror("Error", "Add at least one game.")
            return

        if self._editing_idx >= 0:
            self.db[self._editing_idx] = {"name": name, "color": color, "games": games}
        else:
            # check duplicate name
            if any(c["name"].lower() == name.lower() for c in self.db):
                messagebox.showerror("Error", f'A console named "{name}" already exists.')
                return
            self.db.append({"name": name, "color": color, "games": games})
            self._editing_idx = len(self.db) - 1

        save_consoles(self.db)
        self._refresh_console_list()
        self.console_lb.selection_set(self._editing_idx)
        self._set_console_phase()

    def _delete_console(self):
        sel = self.console_lb.curselection()
        if not sel:
            messagebox.showinfo("Select one", "Select a console to delete.")
            return
        idx = sel[0]
        name = self.db[idx]["name"]
        if messagebox.askyesno("Delete", f"Delete {name}?"):
            self.db.pop(idx)
            save_consoles(self.db)
            self._refresh_console_list()
            self._new_console()
            self._set_console_phase()

    def _move_console(self, direction):
        sel = self.console_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.db):
            return
        self.db[idx], self.db[new_idx] = self.db[new_idx], self.db[idx]
        save_consoles(self.db)
        self._refresh_console_list()
        self.console_lb.selection_set(new_idx)
        self._editing_idx = new_idx
        self._set_console_phase()

    def _pick_color(self, _=None):
        result = colorchooser.askcolor(color=self._selected_color,
                                       title="Pick console color")
        if result and result[1]:
            self._selected_color = result[1]
            self._draw_color_preview()

    def _draw_color_preview(self):
        self.color_preview.delete("all")
        self.color_preview.create_rectangle(2, 2, 26, 26,
                                            fill=self._selected_color, outline="")

    def _update_game_count(self, _=None):
        raw   = self.games_text.get("1.0", "end")
        count = len([g for g in raw.splitlines() if g.strip()])
        self.game_count_lbl.configure(text=f"{count} games")

    def _import_consoles_list(self):
        path = filedialog.askopenfilename(
            title="Import consoles",
            filetypes=[("Supported", "*.txt *.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            ext = os.path.splitext(path)[1].lower()
            if ext == ".txt":
                names = self._read_lines_file(path)
                imported = self._consoles_from_names(names)
            else:
                with open(path) as f:
                    payload = json.load(f)
                imported = self._parse_consoles_payload(payload)
        except Exception as ex:
            messagebox.showerror("Import failed", f"Could not import consoles.\n{ex}")
            return

        if not imported:
            messagebox.showinfo("No consoles", "No valid consoles were found in that file.")
            return

        replace = messagebox.askyesnocancel(
            "Import consoles",
            "Replace your existing console list?\n\n"
            "Yes = replace all\n"
            "No = append and merge by console name\n"
            "Cancel = do nothing",
        )
        if replace is None:
            return

        if replace:
            self.db = imported
        else:
            by_name = {(c["name"]).lower(): dict(c) for c in self.db}
            order = [c["name"].lower() for c in self.db]
            for con in imported:
                key = con["name"].lower()
                if key in by_name:
                    merged_games = dedupe_keep_order(by_name[key]["games"] + con["games"])
                    by_name[key]["games"] = merged_games
                    by_name[key]["color"] = con["color"]
                else:
                    by_name[key] = con
                    order.append(key)
            self.db = [by_name[k] for k in order]

        save_consoles(self.db)
        self._refresh_console_list()
        self._new_console()
        self._set_console_phase()
        messagebox.showinfo("Import complete", f"Imported {len(imported)} console(s).")

    def _parse_consoles_payload(self, payload):
        if isinstance(payload, dict):
            if "consoles" in payload and isinstance(payload["consoles"], list):
                raw_consoles = payload["consoles"]
            else:
                raw_consoles = [
                    {"name": name, "games": games}
                    for name, games in payload.items()
                ]
        elif isinstance(payload, list):
            raw_consoles = payload
        else:
            return []

        cleaned = []
        for i, item in enumerate(raw_consoles):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            raw_games = item.get("games", [])
            if isinstance(raw_games, str):
                games = [g.strip() for g in raw_games.splitlines() if g.strip()]
            elif isinstance(raw_games, list):
                games = [str(g).strip() for g in raw_games if str(g).strip()]
            else:
                games = []

            games = dedupe_keep_order(games)

            color = str(item.get("color", self.PALETTE[i % len(self.PALETTE)])).strip()
            if not color.startswith("#") or len(color) != 7:
                color = self.PALETTE[i % len(self.PALETTE)]

            cleaned.append({"name": name, "color": color, "games": games})
        return cleaned

    def _consoles_from_names(self, names):
        existing_by_name = {c["name"].lower(): c for c in self.db}
        consoles = []
        for i, name in enumerate(names):
            key = name.lower()
            existing = existing_by_name.get(key)
            color = existing["color"] if existing else self.PALETTE[i % len(self.PALETTE)]
            games = list(existing.get("games", [])) if existing else []
            consoles.append({"name": name, "color": color, "games": games})
        return consoles

    def _import_games_list(self):
        path = filedialog.askopenfilename(
            title="Import games",
            filetypes=[("Supported", "*.txt *.json *.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            imported_games = self._read_games_file(path)
        except Exception as ex:
            messagebox.showerror("Import failed", f"Could not import games.\n{ex}")
            return

        if not imported_games:
            messagebox.showinfo("No games", "No valid games were found in that file.")
            return

        replace = messagebox.askyesno(
            "Import games",
            "Replace the current games list?\n\nYes = replace\nNo = append",
        )
        existing = [g.strip() for g in self.games_text.get("1.0", "end").splitlines() if g.strip()]
        merged = imported_games if replace else dedupe_keep_order(existing + imported_games)

        self.games_text.delete("1.0", "end")
        self.games_text.insert("end", "\n".join(merged))
        self._update_game_count()

    def _read_games_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":
            with open(path) as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                payload = payload.get("games", [])
            if isinstance(payload, list):
                games = [str(g).strip() for g in payload if str(g).strip()]
            else:
                games = []
        elif ext == ".txt":
            games = self._read_lines_file(path)
        else:
            with open(path) as f:
                text = f.read()
            rows = []
            for line in text.splitlines():
                rows.extend(part.strip() for part in line.split(","))
            games = [g for g in rows if g]

        return dedupe_keep_order(games)

    def _read_lines_file(self, path):
        with open(path) as f:
            lines = [line.strip() for line in f.read().splitlines()]
        return dedupe_keep_order([line for line in lines if line])

    def _reset_defaults(self):
        if messagebox.askyesno("Clear Consoles", "Remove all consoles and games from your library?"):
            self.db = []
            save_consoles(self.db)
            self._refresh_console_list()
            self._new_console()
            self._set_console_phase()


# ---
if __name__ == "__main__":
    app = RetroPickerApp()
    app.mainloop()

