"""
Core game picker engine.
Handles spinning logic, phase transitions, and result display.
"""

import time
import random
import math
from tkinter import messagebox, simpledialog
import tkinter as tk
from tkinter import ttk
from data_manager import save_history
from color_utils import blend_color
from history_manager import available_games_for_console, rebuild_history_tabs, refresh_history_tree
from wheel_engine import draw_wheel, get_pointed_idx


def spin(app):
    """Start spinning the wheel."""
    if app.spinning:
        return
    n = len(app.wheel_items)
    if n == 0:
        return

    selectable = selectable_indices(app)
    if not selectable:
        messagebox.showinfo(
            "No selectable consoles",
            "All consoles are out of available games. Clear history or add games to continue.",
        )
        return

    app.spinning = True
    app.spin_btn.configure(state="disabled")
    app.manual_btn.configure(state="disabled")
    app.result_frame.pack_forget()

    arc = 2 * math.pi / n
    target_idx = random.choice(selectable)
    # land in middle of target segment
    extra_rotations = (7 + random.random() * 6) * 2 * math.pi
    current_norm = (-app.angle % (2 * math.pi) + 2 * math.pi) % (2 * math.pi)
    target_angle = target_idx * arc + arc / 2
    # how much to add to angle to make target_angle land at 0
    needed = target_angle - current_norm
    if needed < 0:
        needed += 2 * math.pi
    app._anim_delta = extra_rotations + needed
    app._anim_angle0 = app.angle
    app._anim_dur = 4.5 + random.random() * 2.0
    app._anim_start = time.perf_counter()
    app._last_seg = -1
    from wheel_engine import animate_spin
    animate_spin(app)


def manual_pick(app):
    """Handle manual picking from list."""
    if app.spinning:
        return

    if app.phase == 1:
        options = [app.db[i]["name"] for i in app.console_pickable_indices]
        if not options:
            messagebox.showinfo(
                "No selectable consoles",
                "All consoles are out of available games. Clear history or add games to continue.",
            )
            return
        picked = choose_from_list(
            app,
            "Manual Console Pick",
            "Choose a console:",
            options,
        )
    else:
        options = [label for label, _ in app.wheel_items]
        if not options:
            messagebox.showinfo("No games", "No games are available to pick.")
            return
        picked = choose_from_list(
            app,
            "Manual Game Pick",
            f"Choose a game for {app.chosen_console}:",
            options,
        )

    if picked:
        app.result_frame.pack_forget()
        show_result(app, picked)


def choose_from_list(app, title, prompt, items):
    """Open a searchable list picker dialog."""
    dialog = tk.Toplevel(app)
    dialog.title(title)
    dialog.configure(bg="#1a1a2e")
    dialog.transient(app)
    dialog.grab_set()
    dialog.resizable(False, False)

    tk.Label(dialog, text=prompt, bg="#1a1a2e", fg="#e0e0ff",
             font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

    search_row = tk.Frame(dialog, bg="#1a1a2e")
    search_row.pack(fill="x", padx=12, pady=(0, 8))
    tk.Label(search_row, text="Search:", bg="#1a1a2e", fg="#7777aa",
         font=("Segoe UI", 9)).pack(side="left")
    search_var = tk.StringVar()
    search_entry = tk.Entry(search_row, textvariable=search_var,
                bg="#16213e", fg="#e0e0ff", insertbackground="#e0e0ff",
                font=("Segoe UI", 9), relief="flat")
    search_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

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
    filtered_items = list(items)

    def rebuild_listbox():
        nonlocal filtered_items
        query = search_var.get().strip().lower()
        if query:
            filtered_items = [item for item in items if query in item.lower()]
        else:
            filtered_items = list(items)

        lb.delete(0, "end")
        for item in filtered_items:
            lb.insert("end", item)
        if filtered_items:
            lb.selection_set(0)
            lb.activate(0)

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
    search_var.trace_add("write", lambda *_: rebuild_listbox())
    search_entry.bind("<Down>", lambda _e: (lb.focus_set(), "break")[1])

    rebuild_listbox()

    dialog.update_idletasks()
    x = app.winfo_rootx() + (app.winfo_width() - dialog.winfo_width()) // 2
    y = app.winfo_rooty() + (app.winfo_height() - dialog.winfo_height()) // 2
    dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

    search_entry.focus_set()
    app.wait_window(dialog)
    return result["value"]


def set_console_phase(app):
    """Transition to console selection phase."""
    app.phase = 1
    app.console_pickable_indices = []
    app.wheel_items = []
    for idx, con in enumerate(app.db):
        is_pickable = len(available_games_for_console(app, con["name"])) > 0
        color = con["color"] if is_pickable else "#7a7a86"
        app.wheel_items.append((con["name"], color))
        if is_pickable:
            app.console_pickable_indices.append(idx)

    app.angle = 0.0
    available = len(app.console_pickable_indices)
    app.phase_label.configure(
        text=f"STEP 1 - PICK A CONSOLE   ({available}/{len(app.db)} available)")
    app._label_layout_cache.clear()
    app.reset_btn.pack_forget()
    app.result_frame.pack_forget()
    app.live_label.configure(text="")
    app.spin_btn.configure(state="normal" if available else "disabled")
    app.manual_btn.configure(text="PICK CONSOLE",
                  state="normal" if available else "disabled")
    rebuild_history_tabs(app)
    refresh_history_tree(app)
    draw_wheel(app)


def set_game_phase(app):
    """Transition to game selection phase."""
    app.phase = 2
    con = next((c for c in app.db if c["name"] == app.chosen_console), None)
    if not con or not con["games"]:
        messagebox.showinfo("No games", f"No games found for {app.chosen_console}.")
        reset(app)
        return

    games = available_games_for_console(app, app.chosen_console)
    if not games:
        messagebox.showinfo(
            "No games left",
            f"All games for {app.chosen_console} have already been picked.\n"
            "Clear history to make them available again.",
        )
        reset(app)
        return

    base = con["color"]
    app.wheel_items = [(g, blend_color(base, i, len(games)))
                        for i, g in enumerate(games)]
    app._label_layout_cache.clear()
    app.angle = 0.0
    app.phase_label.configure(
        text=f"STEP 2 - PICK A {app.chosen_console.upper()} GAME   ({len(games)} games)")
    app.reset_btn.pack(side="left", padx=6)
    app.result_frame.pack_forget()
    app.live_label.configure(text="")
    app.manual_btn.configure(text="PICK GAME", state="normal")
    draw_wheel(app)


def show_result(app, name):
    """Display the result of a pick."""
    for w in app.result_btn_frame.winfo_children():
        w.destroy()
    app.result_text.configure(text=name)
    if app.phase == 1:
        if not available_games_for_console(app, name):
            messagebox.showinfo(
                "No games left",
                f"{name} has no games left to pick. Add games or clear history.",
            )
            set_console_phase(app)
            return
        app.chosen_console = name
        app.result_lbl.configure(text="CONSOLE SELECTED")
        tk.Button(app.result_btn_frame,
                  text=f"Pick a {name} game  ->",
                  bg="#0f3460", fg="#e0e0ff",
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=set_game_phase).pack()
    else:
        app.result_lbl.configure(text="YOUR GAME IS")
        entry = {
            "console": app.chosen_console,
            "game": name,
            "time": time.strftime("%Y-%m-%d %H:%M"),
        }
        app.history.insert(0, entry)
        save_history(app.history)
        refresh_history_tree(app)

        # Remove the picked game from the current wheel immediately.
        app.wheel_items = [(label, color) for (label, color) in app.wheel_items
                            if label != name]
        app._label_layout_cache.clear()
        draw_wheel(app)

        # Lock further picks until user starts over.
        app.spin_btn.configure(state="disabled")
        app.manual_btn.configure(state="disabled")

        tk.Button(app.result_btn_frame,
                  text="Start over",
                  bg="#2c2c4a", fg="#aaaacc",
                  font=("Segoe UI", 10),
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=reset).pack()

    app.result_frame.pack(padx=16, pady=(0, 10), fill="x")


def reset(app):
    """Reset to console selection phase."""
    set_console_phase(app)


def selectable_indices(app):
    """Get list of selectable indices based on current phase."""
    if app.phase == 1:
        return list(app.console_pickable_indices)
    return list(range(len(app.wheel_items)))
