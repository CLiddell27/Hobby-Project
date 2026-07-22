"""
UI building and layout management.
Handles all tkinter widget creation and styling.
"""

import tkinter as tk
from tkinter import ttk
from game_picker_engine import spin, manual_pick, reset, set_game_phase
from console_manager import (
    refresh_console_list, on_console_select, new_console, save_console,
    delete_console, move_console, pick_color, update_game_count, reset_defaults
)
from import_export import import_consoles_list, import_games_list, import_consoles_from_igdb, import_games_from_igdb
from history_manager import clear_history, remove_selected_history_entry


def build_ui(app):
    """Build the main UI with tabs."""
    # ---
    style = ttk.Style(app)
    style.theme_use("clam")
    style.configure("TNotebook", background="#1a1a2e", borderwidth=0)
    style.configure("TNotebook.Tab", background="#16213e", foreground="#aaaacc",
                    padding=[12, 5], font=("Segoe UI", 9))
    style.map("TNotebook.Tab",
              background=[("selected", "#0f3460")],
              foreground=[("selected", "#e0e0ff")])
    style.configure("TFrame", background="#1a1a2e")

    app.nb = ttk.Notebook(app)
    app.nb.pack(fill="both", expand=True)

    app.tab_wheel = ttk.Frame(app.nb)
    app.tab_history = ttk.Frame(app.nb)
    app.tab_manage = ttk.Frame(app.nb)

    app.nb.add(app.tab_wheel, text=" Wheel ")
    app.nb.add(app.tab_history, text=" History ")
    app.nb.add(app.tab_manage, text=" Manage ")

    build_wheel_tab(app)
    build_history_tab(app)
    build_manage_tab(app)


def build_wheel_tab(app):
    """Build the wheel/spinning tab."""
    f = app.tab_wheel
    f.configure(style="TFrame")

    app.phase_label = tk.Label(f, text="", bg="#1a1a2e", fg="#7777aa",
                                font=("Segoe UI", 9), pady=6)
    app.phase_label.pack()

    # Content row: wheel on left, result/metadata on right
    content_row = tk.Frame(f, bg="#1a1a2e")
    content_row.pack(fill="both", expand=True, padx=8, pady=8)

    # Left side: canvas + pointer
    left_frame = tk.Frame(content_row, bg="#1a1a2e")
    left_frame.pack(side="left", anchor="n")

    app.canvas = tk.Canvas(left_frame, width=app.wheel_size, height=app.wheel_size,
                            bg="#1a1a2e", highlightthickness=0)
    app.canvas.pack(side="left")

    ptr = tk.Frame(left_frame, bg="#1a1a2e")
    ptr.pack(side="left")
    app.ptr_canvas = tk.Canvas(ptr, width=28, height=30,
                                bg="#1a1a2e", highlightthickness=0)
    app.ptr_canvas.pack()
    app.ptr_canvas.create_polygon(0, 0, 0, 30, 26, 15, fill="#ef5350", outline="")

    # Right side: result/metadata panel
    right_frame = tk.Frame(content_row, bg="#1a1a2e", padx=8)
    right_frame.pack(side="left", fill="both", expand=True, anchor="n")

    # live indicator
    app.live_label = tk.Label(f, text="", bg="#1a1a2e", fg="#aaaacc",
                               font=("Segoe UI", 10, "italic"), pady=4)
    app.live_label.pack()

    # buttons
    btn_row = tk.Frame(f, bg="#1a1a2e", pady=6)
    btn_row.pack()

    app.spin_btn = tk.Button(btn_row, text="SPIN", font=("Segoe UI", 11, "bold"),
                              bg="#0f3460", fg="#e0e0ff", activebackground="#1a5276",
                              relief="flat", padx=20, pady=8, cursor="hand2",
                              command=lambda: spin(app))
    app.spin_btn.pack(side="left", padx=6)

    app.manual_btn = tk.Button(btn_row, text="PICK CONSOLE", font=("Segoe UI", 10, "bold"),
                    bg="#1f5a42", fg="#e0ffe0", activebackground="#2b7658",
                    relief="flat", padx=14, pady=8, cursor="hand2",
                    command=lambda: manual_pick(app))
    app.manual_btn.pack(side="left", padx=6)

    app.reset_btn = tk.Button(btn_row, text="RESET", font=("Segoe UI", 10),
                               bg="#2c2c4a", fg="#aaaacc", activebackground="#3a3a5a",
                               relief="flat", padx=14, pady=8, cursor="hand2",
                               command=lambda: reset(app))
    app.reset_btn.pack(side="left", padx=6)
    app.reset_btn.pack_forget()

    # result box (parent is now right_frame)
    app.result_frame = tk.Frame(right_frame, bg="#16213e", padx=16, pady=12)
    app.result_lbl = tk.Label(app.result_frame, text="", bg="#16213e",
                                 fg="#7777aa", font=("Segoe UI", 8))
    app.result_lbl.pack()
    app.result_text = tk.Label(app.result_frame, text="", bg="#16213e",
                                 fg="#e0e0ff", font=("Segoe UI", 16, "bold"),
                                 wraplength=440)
    app.result_text.pack()
    app.result_btn_frame = tk.Frame(app.result_frame, bg="#16213e", pady=8)
    app.result_btn_frame.pack()

    # --- IGDB metadata panel (shown only after a game is picked) ---
    app.meta_sep = tk.Frame(app.result_frame, bg="#2a2a4a", height=1)
    app.meta_outer = tk.Frame(app.result_frame, bg="#16213e")

    app.meta_status_lbl = tk.Label(
        app.meta_outer, text="", bg="#16213e", fg="#555577",
        font=("Segoe UI", 8, "italic"),
    )
    app.meta_status_lbl.pack(pady=(4, 0))

    app.meta_frame = tk.Frame(app.meta_outer, bg="#16213e")

    app.meta_cover_lbl = tk.Label(app.meta_frame, bg="#16213e", bd=0)
    app.meta_cover_lbl.pack(side="left", padx=(6, 14), pady=4)

    _meta_info = tk.Frame(app.meta_frame, bg="#16213e")
    _meta_info.pack(side="left", anchor="n", pady=6)

    app.meta_year_lbl = tk.Label(
        _meta_info, text="", bg="#16213e", fg="#9999cc",
        font=("Segoe UI", 9), anchor="w",
    )
    app.meta_year_lbl.pack(anchor="w")

    app.meta_genre_lbl = tk.Label(
        _meta_info, text="", bg="#16213e", fg="#7799bb",
        font=("Segoe UI", 9), anchor="w", wraplength=280,
    )
    app.meta_genre_lbl.pack(anchor="w", pady=(4, 0))

    app.meta_platforms_lbl = tk.Label(
        _meta_info, text="", bg="#16213e", fg="#88aacc",
        font=("Segoe UI", 9), anchor="w", justify="left", wraplength=280,
    )
    app.meta_platforms_lbl.pack(anchor="w", pady=(4, 0))

    app._meta_photo = None   # hold Pillow PhotoImage reference to prevent GC


def build_history_tab(app):
    """Build the history tab."""
    f = app.tab_history
    f.configure(style="TFrame")

    top = tk.Frame(f, bg="#1a1a2e")
    top.pack(fill="x", padx=12, pady=10)
    tk.Label(top, text="Roll History", bg="#1a1a2e", fg="#e0e0ff",
             font=("Segoe UI", 13, "bold")).pack(side="left")
    tk.Button(top, text="Remove Selected", bg="#4a2a1a", fg="#ffbb77",
              font=("Segoe UI", 9), relief="flat", padx=10, pady=4,
              cursor="hand2", command=lambda: remove_selected_history_entry(app)).pack(side="right", padx=(0, 6))
    tk.Button(top, text="Clear History", bg="#3a1a1a", fg="#ff7777",
              font=("Segoe UI", 9), relief="flat", padx=10, pady=4,
              cursor="hand2", command=lambda: clear_history(app)).pack(side="right")

    style = ttk.Style()
    style.configure("Treeview", background="#16213e", foreground="#ccccee",
                    fieldbackground="#16213e", rowheight=26,
                    font=("Segoe UI", 9))
    style.configure("Treeview.Heading", background="#0f3460", foreground="#e0e0ff",
                    font=("Segoe UI", 9, "bold"))
    style.map("Treeview", background=[("selected", "#1a5276")])

    # Tab bar with scrollable buttons
    tab_bar_frame = tk.Frame(f, bg="#1a1a2e", height=40)
    tab_bar_frame.pack(fill="x", padx=12, pady=(4, 0))
    tab_bar_frame.pack_propagate(False)

    # Canvas for scrollable tab buttons
    app.history_tab_canvas = tk.Canvas(tab_bar_frame, bg="#1a1a2e", 
                                        highlightthickness=0, height=40)
    app.history_tab_canvas.pack(side="left", fill="both", expand=True)

    # Scrollbar for tabs
    tab_scroll = ttk.Scrollbar(tab_bar_frame, orient="horizontal", 
                               command=app.history_tab_canvas.xview)
    tab_scroll.pack(side="left", fill="x")
    app.history_tab_canvas.configure(xscrollcommand=tab_scroll.set)

    # Inner frame to hold tab buttons
    app.history_tab_inner = tk.Frame(app.history_tab_canvas, bg="#1a1a2e")
    app.history_tab_canvas_window = app.history_tab_canvas.create_window(
        0, 0, window=app.history_tab_inner, anchor="nw"
    )

    # Bind mousewheel to scroll tabs horizontally
    def _on_mousewheel(event):
        app.history_tab_canvas.xview_scroll(int(-1*(event.delta/120)), "units")
        return "break"

    def _bind_history_wheel(_event=None):
        app.bind_all("<MouseWheel>", _on_mousewheel)

    def _unbind_history_wheel(_event=None):
        app.unbind_all("<MouseWheel>")

    app.history_tab_canvas.bind("<Enter>", _bind_history_wheel)
    app.history_tab_inner.bind("<Enter>", _bind_history_wheel)
    tab_bar_frame.bind("<Enter>", _bind_history_wheel)

    app.history_tab_canvas.bind("<Leave>", _unbind_history_wheel)
    app.history_tab_inner.bind("<Leave>", _unbind_history_wheel)
    tab_bar_frame.bind("<Leave>", _unbind_history_wheel)

    # Content frame for treeview
    app.history_content = tk.Frame(f, bg="#1a1a2e")
    app.history_content.pack(fill="both", expand=True, padx=12, pady=4)

    app.history_all_tree = None
    app.history_console_trees = {}
    app.history_current_tree = None
    app.history_tab_buttons = {}
    app.history_tab_frames = {}
    app.history_selected_tab = None

    from history_manager import rebuild_history_tabs, refresh_history_tree
    rebuild_history_tabs(app)
    refresh_history_tree(app)



def build_manage_tab(app):
    """Build the console management tab."""
    f = app.tab_manage
    f.configure(style="TFrame")

    panes = tk.PanedWindow(f, orient="horizontal", bg="#1a1a2e",
                           sashrelief="flat", sashwidth=6)
    panes.pack(fill="both", expand=True, padx=8, pady=8)

    # ---
    left = tk.Frame(panes, bg="#1a1a2e", width=200)
    panes.add(left, minsize=180)

    tk.Label(left, text="Consoles", bg="#1a1a2e", fg="#e0e0ff",
             font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 4))

    app.console_lb = tk.Listbox(left, bg="#16213e", fg="#ccccee",
                                 selectbackground="#0f3460", selectforeground="#e0e0ff",
                                 font=("Segoe UI", 10), relief="flat",
                                 activestyle="none", cursor="hand2")
    app.console_lb.pack(fill="both", expand=True, padx=8)
    app.console_lb.bind("<<ListboxSelect>>", lambda e: on_console_select(app, e))

    lb_btns = tk.Frame(left, bg="#1a1a2e")
    lb_btns.pack(fill="x", padx=8, pady=6)
    tk.Button(lb_btns, text="+ Add", bg="#0f3460", fg="#e0e0ff",
              font=("Segoe UI", 9), relief="flat", padx=8, pady=4,
              cursor="hand2", command=lambda: new_console(app)).pack(side="left", padx=(0, 4))
    tk.Button(lb_btns, text="Delete", bg="#3a1a1a", fg="#ff7777",
              font=("Segoe UI", 9), relief="flat", padx=8, pady=4,
              cursor="hand2", command=lambda: delete_console(app)).pack(side="left")
    tk.Button(lb_btns, text="^", bg="#2c2c4a", fg="#aaaacc",
              font=("Segoe UI", 9), relief="flat", padx=6, pady=4,
              cursor="hand2", command=lambda: move_console(app, -1)).pack(side="right")
    tk.Button(lb_btns, text="v", bg="#2c2c4a", fg="#aaaacc",
              font=("Segoe UI", 9), relief="flat", padx=6, pady=4,
              cursor="hand2", command=lambda: move_console(app, 1)).pack(side="right", padx=(0, 4))

    import_row = tk.Frame(left, bg="#1a1a2e")
    import_row.pack(fill="x", padx=8, pady=(0, 4))
    tk.Button(import_row, text="Import Consoles", bg="#2c2c4a", fg="#ccccee",
          font=("Segoe UI", 9), relief="flat", padx=8, pady=4,
          cursor="hand2", command=lambda: import_consoles_list(app)).pack(fill="x")

    igdb_con_row = tk.Frame(left, bg="#1a1a2e")
    igdb_con_row.pack(fill="x", padx=8, pady=(0, 8))
    tk.Button(igdb_con_row, text="Import from IGDB", bg="#1f3a5a", fg="#88ccff",
          font=("Segoe UI", 9), relief="flat", padx=8, pady=4,
          cursor="hand2", command=lambda: import_consoles_from_igdb(app)).pack(fill="x")

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
    app.name_var = tk.StringVar()
    app.name_entry = tk.Entry(name_row, textvariable=app.name_var,
                               bg="#16213e", fg="#e0e0ff", insertbackground="#e0e0ff",
                               font=("Segoe UI", 10), relief="flat", width=22)
    app.name_entry.pack(side="left", padx=6)

    app.color_preview = tk.Canvas(name_row, width=28, height=28,
                                   bg="#1a1a2e", highlightthickness=1,
                                   highlightbackground="#444466", cursor="hand2")
    app.color_preview.pack(side="left", padx=2)
    app._selected_color = "#1565c0"
    draw_color_preview(app)
    app.color_preview.bind("<Button-1>", lambda e: pick_color(app, e))
    tk.Label(name_row, text="Color", bg="#1a1a2e", fg="#7777aa",
             font=("Segoe UI", 8)).pack(side="left", padx=2)

    # Games text box
    games_hdr = tk.Frame(form, bg="#1a1a2e")
    games_hdr.pack(fill="x")
    tk.Label(games_hdr, text="Games (one per line):", bg="#1a1a2e", fg="#7777aa",
         font=("Segoe UI", 9)).pack(side="left")
    tk.Button(games_hdr, text="Import from IGDB", bg="#1f3a5a", fg="#88ccff",
          font=("Segoe UI", 8), relief="flat", padx=8, pady=3,
          cursor="hand2", command=lambda: import_games_from_igdb(app, app.name_var.get())).pack(side="right")
    tk.Button(games_hdr, text="Import Games", bg="#2c2c4a", fg="#ccccee",
          font=("Segoe UI", 8), relief="flat", padx=8, pady=3,
          cursor="hand2", command=lambda: import_games_list(app)).pack(side="right", padx=(0, 4))
    games_frame = tk.Frame(form, bg="#1a1a2e")
    games_frame.pack(fill="both", expand=True, pady=(4, 6))
    app.games_text = tk.Text(games_frame, bg="#16213e", fg="#ccccee",
                              insertbackground="#ccccee", font=("Segoe UI", 9),
                              relief="flat", wrap="word", height=18)
    gscroll = ttk.Scrollbar(games_frame, command=app.games_text.yview)
    app.games_text.configure(yscrollcommand=gscroll.set)
    app.games_text.pack(side="left", fill="both", expand=True)
    gscroll.pack(side="left", fill="y")

    app.game_count_lbl = tk.Label(form, text="", bg="#1a1a2e", fg="#7777aa",
                                   font=("Segoe UI", 8))
    app.game_count_lbl.pack(anchor="e")
    app.games_text.bind("<KeyRelease>", lambda e: update_game_count(app, e))

    # Save / Reset defaults
    save_row = tk.Frame(form, bg="#1a1a2e")
    save_row.pack(fill="x", pady=4)
    tk.Button(save_row, text="Save Console", bg="#0f3460", fg="#e0e0ff",
              font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=6,
              cursor="hand2", command=lambda: save_console(app)).pack(side="left", padx=(0, 6))
    tk.Button(save_row, text="Clear Consoles", bg="#2c2c4a", fg="#aaaacc",
              font=("Segoe UI", 9), relief="flat", padx=10, pady=6,
              cursor="hand2", command=lambda: reset_defaults(app)).pack(side="left")

    app._editing_idx = -1
    refresh_console_list(app)

    # --- IGDB settings row ---
    tk.Frame(right, bg="#2a2a4a", height=1).pack(fill="x", pady=(10, 6))
    igdb_row = tk.Frame(right, bg="#1a1a2e")
    igdb_row.pack(fill="x", padx=8, pady=(0, 8))
    tk.Label(
        igdb_row, text="IGDB Metadata:", bg="#1a1a2e", fg="#7777aa",
        font=("Segoe UI", 9),
    ).pack(side="left")

    from igdb_client import is_configured, open_settings_dialog
    _igdb_ok = is_configured()
    app.igdb_status_lbl = tk.Label(
        igdb_row,
        text="Connected" if _igdb_ok else "Not configured",
        bg="#1a1a2e",
        fg="#55cc88" if _igdb_ok else "#cc7755",
        font=("Segoe UI", 9),
    )
    app.igdb_status_lbl.pack(side="left", padx=8)

    def _open_igdb():
        def _on_save():
            from igdb_client import is_configured as _ic
            ok = _ic()
            app.igdb_status_lbl.configure(
                text="Connected" if ok else "Not configured",
                fg="#55cc88" if ok else "#cc7755",
            )
        open_settings_dialog(app, on_save=_on_save)

    tk.Button(
        igdb_row, text="Configure", bg="#2c2c4a", fg="#ccccee",
        font=("Segoe UI", 9), relief="flat", padx=8, pady=3,
        cursor="hand2", command=_open_igdb,
    ).pack(side="right")


def draw_color_preview(app):
    """Redraw the color preview canvas."""
    app.color_preview.delete("all")
    app.color_preview.create_rectangle(2, 2, 26, 26,
                                        fill=app._selected_color, outline="")
