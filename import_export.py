"""
Import/export functionality for consoles and games.
Handles loading from various file formats and merging strategies.
"""

import os
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from data_manager import save_consoles, dedupe_keep_order


def import_consoles_list(app):
    """Open dialog to import console list from file."""
    path = filedialog.askopenfilename(
        title="Import consoles",
        filetypes=[("Supported", "*.txt *.json"), ("All files", "*.*")],
    )
    if not path:
        return

    try:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".txt":
            names = read_lines_file(path)
            imported = consoles_from_names(app, names)
        else:
            with open(path) as f:
                payload = json.load(f)
            imported = parse_consoles_payload(app, payload)
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
        app.db = imported
    else:
        by_name = {(c["name"]).lower(): dict(c) for c in app.db}
        order = [c["name"].lower() for c in app.db]
        for con in imported:
            key = con["name"].lower()
            if key in by_name:
                merged_games = dedupe_keep_order(by_name[key]["games"] + con["games"])
                by_name[key]["games"] = merged_games
                by_name[key]["color"] = con["color"]
            else:
                by_name[key] = con
                order.append(key)
        app.db = [by_name[k] for k in order]

    save_consoles(app.db)
    from console_manager import refresh_console_list, new_console
    refresh_console_list(app)
    new_console(app)
    from game_picker_engine import set_console_phase
    set_console_phase(app)
    messagebox.showinfo("Import complete", f"Imported {len(imported)} console(s).")


def parse_consoles_payload(app, payload):
    """Parse console data from various JSON formats."""
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

        color = str(item.get("color", app.PALETTE[i % len(app.PALETTE)])).strip()
        if not color.startswith("#") or len(color) != 7:
            color = app.PALETTE[i % len(app.PALETTE)]

        cleaned.append({"name": name, "color": color, "games": games})
    return cleaned


def consoles_from_names(app, names):
    """Create console objects from a list of names."""
    existing_by_name = {c["name"].lower(): c for c in app.db}
    consoles = []
    for i, name in enumerate(names):
        key = name.lower()
        existing = existing_by_name.get(key)
        color = existing["color"] if existing else app.PALETTE[i % len(app.PALETTE)]
        games = list(existing.get("games", [])) if existing else []
        consoles.append({"name": name, "color": color, "games": games})
    return consoles


def import_games_list(app):
    """Open dialog to import games list from file."""
    path = filedialog.askopenfilename(
        title="Import games",
        filetypes=[("Supported", "*.txt *.json *.csv"), ("All files", "*.*")],
    )
    if not path:
        return

    try:
        imported_games = read_games_file(path)
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
    existing = [g.strip() for g in app.games_text.get("1.0", "end").splitlines() if g.strip()]
    merged = imported_games if replace else dedupe_keep_order(existing + imported_games)

    app.games_text.delete("1.0", "end")
    app.games_text.insert("end", "\n".join(merged))
    from console_manager import update_game_count
    update_game_count(app)


def read_games_file(path):
    """Read games from a file in various formats (JSON, TXT, CSV)."""
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
        games = read_lines_file(path)
    else:
        with open(path) as f:
            text = f.read()
        rows = []
        for line in text.splitlines():
            rows.extend(part.strip() for part in line.split(","))
        games = [g for g in rows if g]

    return dedupe_keep_order(games)


def read_lines_file(path):
    """Read lines from a text file, removing duplicates."""
    with open(path) as f:
        lines = [line.strip() for line in f.read().splitlines()]
    return dedupe_keep_order([line for line in lines if line])


# ---------------------------------------------------------------------------
# IGDB console importer
# ---------------------------------------------------------------------------

def import_consoles_from_igdb(app):
    """
    Open a dialog that lists every IGDB console/portable platform sorted by
    year.  The user ticks the ones they want, then clicks Import.
    """
    from igdb_client import is_configured, fetch_all_platforms

    if not is_configured():
        messagebox.showinfo(
            "IGDB Not Configured",
            "Please configure your IGDB credentials in the Manage tab first.",
        )
        return

    # --- outer window --------------------------------------------------------
    win = tk.Toplevel(app)
    win.title("Import Consoles from IGDB")
    win.configure(bg="#1a1a2e")
    win.transient(app)
    win.grab_set()
    win.resizable(True, True)
    win.geometry("560x620")

    tk.Label(
        win, text="Import Consoles from IGDB",
        bg="#1a1a2e", fg="#e0e0ff", font=("Segoe UI", 12, "bold"),
    ).pack(pady=(14, 2))
    tk.Label(
        win, text="Check the consoles you want to add, then click Import Selected.",
        bg="#1a1a2e", fg="#7777aa", font=("Segoe UI", 8),
    ).pack(pady=(0, 8))

    # --- search bar ----------------------------------------------------------
    search_row = tk.Frame(win, bg="#1a1a2e")
    search_row.pack(fill="x", padx=14, pady=(0, 6))
    tk.Label(search_row, text="Search:", bg="#1a1a2e", fg="#7777aa",
             font=("Segoe UI", 9)).pack(side="left")
    search_var = tk.StringVar()
    tk.Entry(
        search_row, textvariable=search_var,
        bg="#16213e", fg="#e0e0ff", insertbackground="#e0e0ff",
        font=("Segoe UI", 9), relief="flat",
    ).pack(side="left", fill="x", expand=True, padx=(6, 0))

    # category filter
    cat_var = tk.StringVar(value="All")
    cat_menu = ttk.Combobox(
        search_row, textvariable=cat_var, state="readonly", width=14,
        values=["All", "Console", "Portable"],
        font=("Segoe UI", 9),
    )
    cat_menu.pack(side="left", padx=(8, 0))

    # --- list area -----------------------------------------------------------
    list_frame = tk.Frame(win, bg="#1a1a2e")
    list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 4))

    canvas = tk.Canvas(list_frame, bg="#16213e", highlightthickness=0)
    vsb    = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg="#16213e")
    canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_inner_configure(_e=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(e):
        canvas.itemconfig(canvas_window, width=e.width)

    inner.bind("<Configure>", _on_inner_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    def _on_mousewheel_canvas(event):
        try:
            canvas.yview_scroll(-1 * (event.delta // 120), "units")
        except tk.TclError:
            return "break"
        return "break"

    win.bind("<MouseWheel>", _on_mousewheel_canvas)

    # State
    _all_platforms   = []   # populated by background thread
    _check_vars      = {}   # id -> BooleanVar
    _row_widgets     = []   # list of (frame_widget, platform_dict)

    status_lbl = tk.Label(
        win, text="Loading platforms...",
        bg="#1a1a2e", fg="#7777aa", font=("Segoe UI", 8, "italic"),
    )
    status_lbl.pack()

    # --- select-all / none row -----------------------------------------------
    sel_row = tk.Frame(win, bg="#1a1a2e")
    sel_row.pack(fill="x", padx=14, pady=(0, 4))

    def _select_visible(value):
        for _frame, plat in _row_widgets:
            if _frame.winfo_ismapped():
                _check_vars[plat["id"]].set(value)

    tk.Button(
        sel_row, text="Select all", bg="#2c2c4a", fg="#ccccee",
        font=("Segoe UI", 8), relief="flat", padx=6, pady=2, cursor="hand2",
        command=lambda: _select_visible(True),
    ).pack(side="left", padx=(0, 4))
    tk.Button(
        sel_row, text="Clear all", bg="#2c2c4a", fg="#ccccee",
        font=("Segoe UI", 8), relief="flat", padx=6, pady=2, cursor="hand2",
        command=lambda: _select_visible(False),
    ).pack(side="left")

    # --- bottom buttons ------------------------------------------------------
    btn_row = tk.Frame(win, bg="#1a1a2e")
    btn_row.pack(fill="x", padx=14, pady=(4, 14))

    def _do_import():
        chosen = [
            p for p in _all_platforms
            if _check_vars.get(p["id"], tk.BooleanVar()).get()
        ]
        if not chosen:
            messagebox.showinfo("Nothing selected", "Please check at least one console.", parent=win)
            return

        replace = messagebox.askyesnocancel(
            "Import consoles",
            "Replace your existing console list?\n\n"
            "Yes = replace all\n"
            "No = append / merge\n"
            "Cancel = do nothing",
            parent=win,
        )
        if replace is None:
            return

        imported = consoles_from_names(app, [p["name"] for p in chosen])
        if replace:
            app.db = imported
        else:
            by_name = {c["name"].lower(): dict(c) for c in app.db}
            order   = [c["name"].lower() for c in app.db]
            for con in imported:
                key = con["name"].lower()
                if key in by_name:
                    by_name[key]["color"] = con["color"]
                else:
                    by_name[key] = con
                    order.append(key)
            app.db = [by_name[k] for k in order]

        save_consoles(app.db)
        from console_manager import refresh_console_list, new_console
        refresh_console_list(app)
        new_console(app)
        from game_picker_engine import set_console_phase
        set_console_phase(app)
        win.destroy()
        
        # Ask if user wants to import games for the new consoles
        if messagebox.askyesno("Import Games", 
                               f"Imported {len(imported)} console(s).\n\n"
                               "Would you like to import games for these consoles?",
                               parent=app):
            import_games_batch(app, [c["name"] for c in imported])

    tk.Button(
        btn_row, text="Cancel", bg="#2c2c4a", fg="#aaaacc",
        font=("Segoe UI", 9), relief="flat", padx=10, pady=4, cursor="hand2",
        command=win.destroy,
    ).pack(side="right")
    import_btn = tk.Button(
        btn_row, text="Import Selected", bg="#0f3460", fg="#e0e0ff",
        font=("Segoe UI", 9, "bold"), relief="flat", padx=14, pady=4, cursor="hand2",
        command=_do_import, state="disabled",
    )
    import_btn.pack(side="right", padx=(0, 6))

    def _submit_console_import(_e=None):
        if str(import_btn.cget("state")) != "disabled":
            _do_import()
            return "break"
        return None

    win.bind("<Return>", _submit_console_import)
    win.bind("<Escape>", lambda _e: win.destroy())

    # --- rebuild list after filter change ------------------------------------
    def _rebuild_list(_e=None):
        query   = search_var.get().strip().lower()
        cat_sel = cat_var.get()  # "All", "Console", "Portable"
        cat_map = {"Console": 1, "Portable": 5}

        for frame, plat in _row_widgets:
            visible = True
            if query and query not in plat["name"].lower():
                visible = False
            if cat_sel in cat_map and plat["category"] != cat_map[cat_sel]:
                visible = False
            if visible:
                frame.pack(fill="x", pady=1)
            else:
                frame.pack_forget()
        canvas.update_idletasks()
        _on_inner_configure()

    search_var.trace_add("write", lambda *_: _rebuild_list())
    cat_var.trace_add("write",    lambda *_: _rebuild_list())

    # --- populate rows -------------------------------------------------------
    def _populate(platforms):
        _all_platforms.clear()
        _all_platforms.extend(platforms)

        for plat in platforms:
            var = tk.BooleanVar(value=False)
            _check_vars[plat["id"]] = var

            row = tk.Frame(inner, bg="#16213e", pady=1)
            row.pack(fill="x", pady=1)

            cb = tk.Checkbutton(
                row, variable=var, bg="#16213e", fg="#e0e0ff",
                selectcolor="#0f3460", activebackground="#16213e",
                relief="flat", cursor="hand2",
            )
            cb.pack(side="left", padx=(6, 2))

            if plat["year"]:
                tk.Label(
                    row, text=f"({plat['year']})",
                    bg="#16213e", fg="#555577",
                    font=("Segoe UI", 8), width=6, anchor="e",
                ).pack(side="left")

            tk.Label(
                row, text=plat["name"],
                bg="#16213e", fg="#ccccee",
                font=("Segoe UI", 9), anchor="w",
            ).pack(side="left", padx=(4, 0))

            cat_tag = "Portable" if plat["category"] == 5 else "Console"
            tk.Label(
                row, text=cat_tag,
                bg="#16213e", fg="#445566",
                font=("Segoe UI", 7), anchor="e",
            ).pack(side="right", padx=6)

            _row_widgets.append((row, plat))

        status_lbl.configure(text=f"{len(platforms)} platforms loaded.")
        import_btn.configure(state="normal")
        _rebuild_list()

    def _fetch_worker():
        try:
            platforms = fetch_all_platforms()
            win.after(0, lambda: _populate(platforms))
        except RuntimeError as exc:
            win.after(0, lambda: status_lbl.configure(
                text="IGDB not configured." if "not_configured" in str(exc)
                     else f"Error: {exc}",
                fg="#ff7777",
            ))
        except Exception as exc:
            win.after(0, lambda: status_lbl.configure(
                text=f"Failed to load: {exc}", fg="#ff7777"
            ))

    threading.Thread(target=_fetch_worker, daemon=True).start()

    # centre window
    win.update_idletasks()
    x = app.winfo_rootx() + (app.winfo_width()  - win.winfo_width())  // 2
    y = app.winfo_rooty() + (app.winfo_height() - win.winfo_height()) // 2
    win.geometry(f"+{max(0, x)}+{max(0, y)}")


# ---------------------------------------------------------------------------
# IGDB game importer (for a specific console already selected in editor)
# ---------------------------------------------------------------------------

def import_games_from_igdb(app, console_name=None):
    """
    Open a dialog that lets the user pick a platform and filter by region,
    then select individual games to append to the current console's game list.
    If console_name is provided, try to auto-match and pre-select that platform.
    """
    from igdb_client import (
        is_configured, fetch_all_platforms, fetch_games_for_platform, REGION_LABELS,
    )

    if not is_configured():
        messagebox.showinfo(
            "IGDB Not Configured",
            "Please configure your IGDB credentials in the Manage tab first.",
        )
        return

    # --- outer window --------------------------------------------------------
    win = tk.Toplevel(app)
    win.title("Import Games from IGDB")
    win.configure(bg="#1a1a2e")
    win.transient(app)
    win.grab_set()
    win.resizable(True, True)
    win.geometry("620x680")

    tk.Label(
        win, text="Import Games from IGDB",
        bg="#1a1a2e", fg="#e0e0ff", font=("Segoe UI", 12, "bold"),
    ).pack(pady=(14, 2))

    # --- step 1: pick platform -----------------------------------------------
    step1 = tk.Frame(win, bg="#1a1a2e")
    step1.pack(fill="x", padx=14, pady=(4, 6))

    tk.Label(step1, text="Platform:", bg="#1a1a2e", fg="#7777aa",
             font=("Segoe UI", 9)).pack(side="left")
    platform_var = tk.StringVar()
    platform_cb  = ttk.Combobox(
        step1, textvariable=platform_var, state="readonly", width=34,
        font=("Segoe UI", 9),
    )
    platform_cb.pack(side="left", padx=(8, 10))

    # Region multi-select
    tk.Label(step1, text="Region:", bg="#1a1a2e", fg="#7777aa",
             font=("Segoe UI", 9)).pack(side="left")

    region_frame  = tk.Frame(win, bg="#1a1a2e")
    region_frame.pack(fill="x", padx=14, pady=(0, 6))
    region_vars   = {}   # region_id -> BooleanVar
    _ORDERED_REGIONS = [
        (2, "North America"),
        (1, "Europe"),
        (8, "Worldwide"),
        (5, "Japan"),
        (3, "Australia"),
        (4, "New Zealand"),
        (7, "Asia"),
        (9, "Korea"),
        (6, "China"),
        (10, "Brazil"),
    ]
    for rid, rlabel in _ORDERED_REGIONS:
        var = tk.BooleanVar(value=(rid in (2, 1, 8)))   # default: NA + EU + Worldwide
        region_vars[rid] = var
        tk.Checkbutton(
            region_frame, text=rlabel, variable=var,
            bg="#1a1a2e", fg="#ccccee", selectcolor="#0f3460",
            activebackground="#1a1a2e", font=("Segoe UI", 8),
            relief="flat", cursor="hand2",
        ).pack(side="left", padx=(0, 6))

    load_games_btn = tk.Button(
        win, text="Load Games", bg="#1f5a42", fg="#e0ffe0",
        font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=4,
        cursor="hand2", state="disabled",
    )
    load_games_btn.pack(anchor="w", padx=14, pady=(0, 8))

    # --- search + list area --------------------------------------------------
    search_row2 = tk.Frame(win, bg="#1a1a2e")
    search_row2.pack(fill="x", padx=14, pady=(0, 4))
    tk.Label(search_row2, text="Search:", bg="#1a1a2e", fg="#7777aa",
             font=("Segoe UI", 9)).pack(side="left")
    game_search_var = tk.StringVar()
    tk.Entry(
        search_row2, textvariable=game_search_var,
        bg="#16213e", fg="#e0e0ff", insertbackground="#e0e0ff",
        font=("Segoe UI", 9), relief="flat",
    ).pack(side="left", fill="x", expand=True, padx=(6, 0))

    list_frame2 = tk.Frame(win, bg="#1a1a2e")
    list_frame2.pack(fill="both", expand=True, padx=14, pady=(0, 4))

    canvas2    = tk.Canvas(list_frame2, bg="#16213e", highlightthickness=0)
    vsb2       = ttk.Scrollbar(list_frame2, orient="vertical", command=canvas2.yview)
    canvas2.configure(yscrollcommand=vsb2.set)
    vsb2.pack(side="right", fill="y")
    canvas2.pack(side="left", fill="both", expand=True)

    inner2        = tk.Frame(canvas2, bg="#16213e")
    canvas_win2   = canvas2.create_window((0, 0), window=inner2, anchor="nw")

    def _on_inner2_configure(_e=None):
        canvas2.configure(scrollregion=canvas2.bbox("all"))

    def _on_canvas2_configure(e):
        canvas2.itemconfig(canvas_win2, width=e.width)

    inner2.bind("<Configure>", _on_inner2_configure)
    canvas2.bind("<Configure>", _on_canvas2_configure)

    def _on_mousewheel_canvas2(event):
        try:
            canvas2.yview_scroll(-1 * (event.delta // 120), "units")
        except tk.TclError:
            return "break"
        return "break"

    win.bind("<MouseWheel>", _on_mousewheel_canvas2)

    game_status_lbl = tk.Label(
        win, text="Select a platform and click Load Games.",
        bg="#1a1a2e", fg="#7777aa", font=("Segoe UI", 8, "italic"),
    )
    game_status_lbl.pack()

    _all_games      = []
    _game_check_vars = {}
    _game_row_widgets = []

    # select all / none
    sel_row2 = tk.Frame(win, bg="#1a1a2e")
    sel_row2.pack(fill="x", padx=14, pady=(0, 4))

    def _select_games(value):
        for _frame, gm in _game_row_widgets:
            if _frame.winfo_ismapped():
                _game_check_vars[gm["id"]].set(value)

    tk.Button(
        sel_row2, text="Select all", bg="#2c2c4a", fg="#ccccee",
        font=("Segoe UI", 8), relief="flat", padx=6, pady=2, cursor="hand2",
        command=lambda: _select_games(True),
    ).pack(side="left", padx=(0, 4))
    tk.Button(
        sel_row2, text="Clear all", bg="#2c2c4a", fg="#ccccee",
        font=("Segoe UI", 8), relief="flat", padx=6, pady=2, cursor="hand2",
        command=lambda: _select_games(False),
    ).pack(side="left")

    # bottom buttons
    btn_row2 = tk.Frame(win, bg="#1a1a2e")
    btn_row2.pack(fill="x", padx=14, pady=(4, 14))

    def _do_import_games():
        chosen = [
            g["name"] for g in _all_games
            if _game_check_vars.get(g["id"], tk.BooleanVar()).get()
        ]
        if not chosen:
            messagebox.showinfo("Nothing selected", "Please check at least one game.", parent=win)
            return

        replace = messagebox.askyesno(
            "Import games",
            "Replace the current games list?\n\nYes = replace\nNo = append",
            parent=win,
        )
        existing = [
            g.strip()
            for g in app.games_text.get("1.0", "end").splitlines()
            if g.strip()
        ]
        merged = chosen if replace else dedupe_keep_order(existing + chosen)

        app.games_text.delete("1.0", "end")
        app.games_text.insert("end", "\n".join(merged))
        from console_manager import update_game_count
        update_game_count(app)
        win.destroy()

    tk.Button(
        btn_row2, text="Cancel", bg="#2c2c4a", fg="#aaaacc",
        font=("Segoe UI", 9), relief="flat", padx=10, pady=4, cursor="hand2",
        command=win.destroy,
    ).pack(side="right")
    add_btn = tk.Button(
        btn_row2, text="Add to Games List", bg="#0f3460", fg="#e0e0ff",
        font=("Segoe UI", 9, "bold"), relief="flat", padx=14, pady=4, cursor="hand2",
        command=_do_import_games, state="disabled",
    )
    add_btn.pack(side="right", padx=(0, 6))

    def _submit_game_import(_e=None):
        if str(add_btn.cget("state")) != "disabled":
            _do_import_games()
            return "break"
        return None

    win.bind("<Return>", _submit_game_import)
    win.bind("<Escape>", lambda _e: win.destroy())

    # --- game list rebuild ---------------------------------------------------
    def _rebuild_games(_e=None):
        query = game_search_var.get().strip().lower()
        for frame, gm in _game_row_widgets:
            visible = not query or query in gm["name"].lower()
            if visible:
                frame.pack(fill="x", pady=1)
            else:
                frame.pack_forget()
        canvas2.update_idletasks()
        _on_inner2_configure()

    game_search_var.trace_add("write", lambda *_: _rebuild_games())

    # --- populate games ------------------------------------------------------
    def _populate_games(games):
        # clear existing
        for w in inner2.winfo_children():
            w.destroy()
        _all_games.clear()
        _game_check_vars.clear()
        _game_row_widgets.clear()
        _all_games.extend(games)

        for gm in games:
            var = tk.BooleanVar(value=False)
            _game_check_vars[gm["id"]] = var

            row = tk.Frame(inner2, bg="#16213e", pady=1)
            row.pack(fill="x", pady=1)

            tk.Checkbutton(
                row, variable=var, bg="#16213e", fg="#e0e0ff",
                selectcolor="#0f3460", activebackground="#16213e",
                relief="flat", cursor="hand2",
            ).pack(side="left", padx=(6, 2))

            if gm["year"]:
                tk.Label(
                    row, text=f"({gm['year']})",
                    bg="#16213e", fg="#555577",
                    font=("Segoe UI", 8), width=6, anchor="e",
                ).pack(side="left")

            region_name = REGION_LABELS.get(gm["region"], "")
            tk.Label(
                row, text=gm["name"],
                bg="#16213e", fg="#ccccee",
                font=("Segoe UI", 9), anchor="w",
            ).pack(side="left", padx=(4, 0))

            if region_name:
                tk.Label(
                    row, text=region_name,
                    bg="#16213e", fg="#445566",
                    font=("Segoe UI", 7), anchor="e",
                ).pack(side="right", padx=6)

            _game_row_widgets.append((row, gm))

        count = len(games)
        if count == 0:
            game_status_lbl.configure(
                text="No games found for that platform/region filter. Try changing regions.",
                fg="#ccaa66",
            )
            add_btn.configure(state="disabled")
        else:
            game_status_lbl.configure(
                text=f"{count} game{'s' if count != 1 else ''} found.",
                fg="#7777aa",
            )
            add_btn.configure(state="normal")
        _rebuild_games()

    # --- load games button ---------------------------------------------------
    _platforms_by_label = {}   # "Name (year)" -> platform dict

    def _on_load_games():
        label = platform_var.get()
        plat  = _platforms_by_label.get(label)
        if not plat:
            return
        regions = [rid for rid, var in region_vars.items() if var.get()]

        game_status_lbl.configure(text="Loading games...", fg="#7777aa")
        for w in inner2.winfo_children():
            w.destroy()
        add_btn.configure(state="disabled")

        def _worker():
            try:
                games = fetch_games_for_platform(plat["id"], regions or None)
                win.after(0, lambda: _populate_games(games))
            except Exception as exc:
                win.after(0, lambda: game_status_lbl.configure(
                    text=f"Failed: {exc}", fg="#ff7777"
                ))

        threading.Thread(target=_worker, daemon=True).start()

    load_games_btn.configure(command=_on_load_games)

    # --- load platform list --------------------------------------------------
    def _load_platforms():
        try:
            platforms = fetch_all_platforms()
            labels = []
            local_map = {}
            matched_idx = None
            for i, p in enumerate(platforms):
                year_str = str(p["year"]) if p["year"] else ""
                lbl = f"{p['name']}  ({year_str})" if year_str else p['name']
                local_map[lbl] = p
                labels.append(lbl)
                # Try to match console_name to platform (case-insensitive)
                if console_name and matched_idx is None:
                    if p['name'].lower() == console_name.lower():
                        matched_idx = i

            def _apply_platforms():
                _platforms_by_label.clear()
                _platforms_by_label.update(local_map)
                platform_cb["values"] = labels
                if labels:
                    if matched_idx is not None:
                        platform_cb.current(matched_idx)
                    else:
                        platform_cb.current(0)
                    load_games_btn.configure(state="normal")
                    game_status_lbl.configure(
                        text="Select a platform and click Load Games.",
                        fg="#7777aa",
                    )
                else:
                    load_games_btn.configure(state="disabled")
                    game_status_lbl.configure(
                        text="No IGDB platforms available for this account.",
                        fg="#ccaa66",
                    )

            win.after(0, _apply_platforms)
        except Exception as exc:
            win.after(0, lambda: game_status_lbl.configure(
                text=f"Failed to load platforms: {exc}", fg="#ff7777"
            ))

    threading.Thread(target=_load_platforms, daemon=True).start()

    # centre window
    win.update_idletasks()
    x = app.winfo_rootx() + (app.winfo_width()  - win.winfo_width())  // 2
    y = app.winfo_rooty() + (app.winfo_height() - win.winfo_height()) // 2
    win.geometry(f"+{max(0, x)}+{max(0, y)}")


def import_games_batch(app, console_names):
    """
    Import games for multiple consoles after console import.
    Asks the user which regions to import, then fetches and saves games.
    """
    import tkinter as tk
    from tkinter import messagebox
    from igdb_client import fetch_all_platforms, fetch_games_for_platform
    from data_manager import save_consoles
    
    # --- outer window --------------------------------------------------------
    win = tk.Toplevel(app)
    win.title("Import Games")
    win.configure(bg="#1a1a2e")
    win.transient(app)
    win.grab_set()
    win.resizable(False, False)
    win.geometry("520x460")
    win.minsize(520, 460)

    tk.Label(
        win, text="Import Games",
        bg="#1a1a2e", fg="#e0e0ff", font=("Segoe UI", 12, "bold"),
    ).pack(pady=(14, 6))
    
    eligible_console_names = []
    pre_skipped_missing = 0
    for name in console_names:
        console = next((c for c in app.db if c["name"].lower() == name.lower()), None)
        if console is None:
            pre_skipped_missing += 1
            continue
        eligible_console_names.append(name)

    tk.Label(
        win, text=f"Select regions to import games for {len(eligible_console_names)} console(s):",
        bg="#1a1a2e", fg="#7777aa", font=("Segoe UI", 9),
    ).pack(pady=(0, 10))

    # Region multi-select
    region_frame = tk.Frame(win, bg="#1a1a2e")
    region_frame.pack(fill="x", padx=14, pady=(0, 12))
    
    region_vars = {}
    _ORDERED_REGIONS = [
        (2, "North America"),
        (1, "Europe"),
        (8, "Worldwide"),
        (5, "Japan"),
        (3, "Australia"),
        (4, "New Zealand"),
        (7, "Asia"),
        (9, "Korea"),
        (6, "China"),
        (10, "Brazil"),
    ]
    
    for idx, (rid, rlabel) in enumerate(_ORDERED_REGIONS):
        var = tk.BooleanVar(value=(rid in (2, 1, 8)))  # default: NA + EU + Worldwide
        region_vars[rid] = var
        chk = tk.Checkbutton(
            region_frame, text=rlabel, variable=var,
            bg="#1a1a2e", fg="#ccccee", selectcolor="#0f3460",
            activebackground="#1a1a2e", font=("Segoe UI", 9),
            relief="flat", cursor="hand2",
        )
        row = idx // 2
        col = idx % 2
        chk.grid(row=row, column=col, sticky="w", padx=6, pady=2)

    region_frame.grid_columnconfigure(0, weight=1)
    region_frame.grid_columnconfigure(1, weight=1)

    # Status label
    status_lbl = tk.Label(
        win, text="",
        bg="#1a1a2e", fg="#7777aa", font=("Segoe UI", 8, "italic"),
    )
    status_lbl.pack(pady=(8, 12))

    tk.Label(
        win, text="Tip: Press Enter to start import, Esc to cancel.",
        bg="#1a1a2e", fg="#666688", font=("Segoe UI", 8),
    ).pack(pady=(0, 8))

    # --- bottom buttons ------
    btn_row = tk.Frame(win, bg="#1a1a2e")
    btn_row.pack(fill="x", padx=14, pady=(0, 14))

    def _set_buttons(state):
        import_btn.configure(state=state)
        auto_btn.configure(state=state)
        cancel_btn.configure(state=state)

    def _finish(imported_count, imported_consoles, skipped_count, not_found_count, changed):
        """Called on the main thread once work is complete."""
        if changed:
            save_consoles(app.db)
            from console_manager import refresh_console_list
            refresh_console_list(app)
        parts = [f"Imported {imported_count} game(s) across {imported_consoles} console(s)."]
        total_skipped = skipped_count + pre_skipped_missing + not_found_count
        if total_skipped:
            detail = ", ".join(filter(None, [
                f"not found on IGDB: {not_found_count}" if not_found_count else "",
                f"missing: {pre_skipped_missing}" if pre_skipped_missing else "",
                f"skipped: {skipped_count}" if skipped_count else "",
            ]))
            parts.append(f"Skipped {total_skipped} ({detail}).")
        status_lbl.configure(text="  ".join(parts), fg="#7777aa")
        _set_buttons("normal")
        win.after(2200, win.destroy)

    def _run_import(auto):
        """Validate, then dispatch work. auto path runs in a background thread."""
        if not eligible_console_names:
            messagebox.showinfo(
                "Import Games",
                "No valid consoles are available to import.",
                parent=win,
            )
            win.destroy()
            return

        selected_regions = [rid for rid, var in region_vars.items() if var.get()]
        if not selected_regions:
            messagebox.showwarning(
                "No Regions Selected",
                "Please select at least one region.",
                parent=win,
            )
            return

        _set_buttons("disabled")
        status_lbl.configure(text="Loading platform list...", fg="#7777aa")

        if auto:
            # ── Auto path: all network work runs in a background thread ──────
            def _worker():
                try:
                    platforms = fetch_all_platforms()
                    platform_by_name = {p["name"].lower(): p["id"] for p in platforms}

                    imported_count = 0
                    imported_consoles = 0
                    skipped_count = 0
                    not_found_count = 0
                    changed = False

                    for idx, console_name in enumerate(eligible_console_names, start=1):
                        win.after(0, lambda n=console_name, i=idx: status_lbl.configure(
                            text=f"Importing {n} ({i}/{len(eligible_console_names)})...",
                            fg="#7777aa",
                        ))

                        console = next(
                            (c for c in app.db if c["name"].lower() == console_name.lower()),
                            None,
                        )
                        if not console:
                            skipped_count += 1
                            continue

                        platform_id = platform_by_name.get(console_name.lower())
                        if not platform_id:
                            not_found_count += 1
                            continue

                        try:
                            games = fetch_games_for_platform(platform_id, regions=selected_regions)
                        except Exception:
                            skipped_count += 1
                            continue

                        if not games:
                            continue

                        existing = set(g.strip().casefold() for g in console["games"])
                        added_here = 0
                        for game in games:
                            game_title = game.get("name", "").strip()
                            norm = game_title.casefold()
                            if game_title and norm not in existing:
                                console["games"].append(game_title)
                                existing.add(norm)
                                added_here += 1

                        if added_here > 0:
                            imported_count += added_here
                            imported_consoles += 1
                            changed = True

                    win.after(0, lambda: _finish(
                        imported_count, imported_consoles,
                        skipped_count, not_found_count, changed,
                    ))
                except Exception as exc:
                    win.after(0, lambda e=exc: (
                        status_lbl.configure(text=f"Error: {e}", fg="#ff7777"),
                        _set_buttons("normal"),
                    ))

            import threading
            threading.Thread(target=_worker, daemon=True).start()

        else:
            # ── Manual path: stays on main thread so messagebox dialogs work ──
            try:
                platforms = fetch_all_platforms()
                platform_by_name = {p["name"].lower(): p["id"] for p in platforms}

                imported_count = 0
                imported_consoles = 0
                skipped_count = 0
                not_found_count = 0
                changed = False
                stop = False

                for idx, console_name in enumerate(eligible_console_names, start=1):
                    choice = messagebox.askyesnocancel(
                        "Import Games by Console",
                        f"Import games for {console_name}?\n\n"
                        f"Console {idx} of {len(eligible_console_names)}\n"
                        "Existing games are kept; duplicates are skipped.\n\n"
                        "Yes = import this console\n"
                        "No = skip this console\n"
                        "Cancel = stop remaining imports",
                        parent=win,
                    )
                    if choice is None:
                        stop = True
                        break
                    if choice is False:
                        skipped_count += 1
                        continue

                    console = next(
                        (c for c in app.db if c["name"].lower() == console_name.lower()),
                        None,
                    )
                    if not console:
                        skipped_count += 1
                        continue

                    platform_id = platform_by_name.get(console_name.lower())
                    if not platform_id:
                        not_found_count += 1
                        messagebox.showwarning(
                            "Platform Not Found",
                            f"Could not find IGDB platform for {console_name}. Skipping.",
                            parent=win,
                        )
                        continue

                    status_lbl.configure(
                        text=f"Importing {console_name} ({idx}/{len(eligible_console_names)})...",
                        fg="#7777aa",
                    )
                    win.update_idletasks()

                    games = None
                    while True:
                        try:
                            games = fetch_games_for_platform(platform_id, regions=selected_regions)
                            break
                        except Exception as exc:
                            retry = messagebox.askyesnocancel(
                                "Import Failed",
                                f"Failed to import {console_name}.\n\n{exc}\n\n"
                                "Yes = retry this console\n"
                                "No = skip this console\n"
                                "Cancel = stop remaining imports",
                                parent=win,
                            )
                            if retry is None:
                                stop = True
                                break
                            if retry is False:
                                skipped_count += 1
                                break

                    if stop:
                        break
                    if not games:
                        continue

                    existing = set(g.strip().casefold() for g in console["games"])
                    added_here = 0
                    for game in games:
                        game_title = game.get("name", "").strip()
                        norm = game_title.casefold()
                        if game_title and norm not in existing:
                            console["games"].append(game_title)
                            existing.add(norm)
                            added_here += 1

                    if added_here > 0:
                        imported_count += added_here
                        imported_consoles += 1
                        changed = True

                _finish(imported_count, imported_consoles, skipped_count, not_found_count, changed)
            except Exception as exc:
                status_lbl.configure(text=f"Error: {exc}", fg="#ff7777")
                _set_buttons("normal")

    cancel_btn = tk.Button(
        btn_row, text="Cancel", bg="#2c2c4a", fg="#aaaacc",
        font=("Segoe UI", 10), relief="flat", padx=16, pady=4,
        cursor="hand2", command=win.destroy,
    )
    cancel_btn.pack(side="right")

    import_btn = tk.Button(
        btn_row, text="Import (confirm each)", bg="#0f3460", fg="#e0e0ff",
        font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=4,
        cursor="hand2", command=lambda: _run_import(auto=False),
    )
    import_btn.pack(side="right", padx=(0, 6))

    auto_btn = tk.Button(
        btn_row, text="Auto Import All", bg="#1f5a42", fg="#e0ffe0",
        font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=4,
        cursor="hand2", command=lambda: _run_import(auto=True),
    )
    auto_btn.pack(side="right", padx=(0, 6))

    def _submit_batch_import(_e=None):
        if str(auto_btn.cget("state")) != "disabled":
            _run_import(auto=True)
            return "break"
        return None

    win.bind("<Return>", _submit_batch_import)
    win.bind("<Escape>", lambda _e: win.destroy())

    # Centre window
    win.update_idletasks()
    x = app.winfo_rootx() + (app.winfo_width()  - win.winfo_width())  // 2
    y = app.winfo_rooty() + (app.winfo_height() - win.winfo_height()) // 2
    win.geometry(f"+{max(0, x)}+{max(0, y)}")
