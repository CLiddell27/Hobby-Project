"""
History management for tracking game picks.
Handles history UI updates and data retrieval.
"""

from data_manager import save_history
from igdb_client import is_configured, fetch_game_metadata


def _norm(text):
    """Normalize text for case-insensitive comparisons."""
    return str(text or "").strip().casefold()


def rebuild_history_tabs(app):
    """Rebuild history tabs when console list changes."""
    import tkinter as tk
    
    if not hasattr(app, "history_tab_inner"):
        return

    # Clear existing tab buttons and frames
    for widget in app.history_tab_inner.winfo_children():
        widget.destroy()
    
    # Clear old content frames
    for frame in app.history_content.winfo_children():
        frame.destroy()
    
    app.history_tab_buttons = {}
    app.history_console_trees = {}
    app.history_tab_frames = {}

    # "All" tab
    app.history_all_tree = add_history_tab(app, "All", include_console=True)
    _create_tab_button(app, "All", select=True)

    # Per-console tabs
    for con in app.db:
        app.history_console_trees[con["name"]] = add_history_tab(
            app, con["name"], include_console=False
        )
        _create_tab_button(app, con["name"])

    # Update canvas scroll region
    app.history_tab_inner.update_idletasks()
    app.history_tab_canvas.configure(
        scrollregion=app.history_tab_canvas.bbox("all")
    )


def _create_tab_button(app, title, select=False):
    """Create a clickable tab button."""
    import tkinter as tk
    
    def _switch_tab():
        # Deselect all tabs
        for btn in app.history_tab_buttons.values():
            btn.configure(bg="#2c2c4a", fg="#aaaacc")
        
        # Select this tab
        app.history_tab_buttons[title].configure(bg="#0f3460", fg="#e0e0ff")
        app.history_selected_tab = title

        # Hide all frames
        for frame in app.history_tab_frames.values():
            frame.pack_forget()

        # Show selected frame
        if title in app.history_tab_frames:
            app.history_tab_frames[title].pack(fill="both", expand=True)

    btn = tk.Button(
        app.history_tab_inner,
        text=title,
        bg="#0f3460" if select else "#2c2c4a",
        fg="#e0e0ff" if select else "#aaaacc",
        font=("Segoe UI", 10),
        relief="flat",
        padx=16,
        pady=8,
        cursor="hand2",
        command=_switch_tab,
    )
    btn.pack(side="left", padx=4)
    app.history_tab_buttons[title] = btn

    if select:
        app.history_selected_tab = title
        # Pack the initial tab
        if title in app.history_tab_frames:
            app.history_tab_frames[title].pack(fill="both", expand=True)


def add_history_tab(app, title, include_console):
    """Create a history treeview frame with tree and scrollbar."""
    import tkinter as tk
    from tkinter import ttk
    
    frame = tk.Frame(app.history_content, bg="#1a1a2e")
    # Don't pack yet - will be packed when tab is selected
    
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
    tree.bind("<Delete>", lambda _e: remove_selected_history_entry(app))
    
    # Store frame for tab switching
    app.history_tab_frames[title] = frame
    return tree


def refresh_history_tree(app):
    """Refresh history treeview with current data."""
    if not hasattr(app, "history_all_tree") or app.history_all_tree is None:
        return

    app.history_tree_item_map = {}

    # Clear all trees
    for row in app.history_all_tree.get_children():
        app.history_all_tree.delete(row)
    for tree in app.history_console_trees.values():
        for row in tree.get_children():
            tree.delete(row)

    indexed_history = list(enumerate(app.history))
    sorted_history = sorted(
        indexed_history,
        key=lambda item: (
            (item[1].get("console") or "").lower(),
            item[1].get("time") or "",
        ),
    )
    for display_idx, (history_idx, entry) in enumerate(sorted_history):
        console = entry.get("console", "")
        all_iid = f"all_{history_idx}_{display_idx}"
        app.history_all_tree.insert("", "end", iid=all_iid,
                                     values=(console,
                                             entry.get("game", ""),
                                             entry.get("time", "")))
        app.history_tree_item_map[(str(app.history_all_tree), all_iid)] = history_idx

        tree = app.history_console_trees.get(console)
        if tree is not None:
            tree_iid = f"con_{history_idx}_{display_idx}"
            tree.insert("", "end", iid=tree_iid,
                        values=(entry.get("game", ""),
                                entry.get("time", "")))
            app.history_tree_item_map[(str(tree), tree_iid)] = history_idx


def _current_history_tree(app):
    """Return the currently visible history treeview."""
    if getattr(app, "history_selected_tab", "All") == "All":
        return app.history_all_tree
    return app.history_console_trees.get(app.history_selected_tab)


def remove_selected_history_entry(app):
    """Remove a single selected history entry from the active tab."""
    from tkinter import messagebox

    tree = _current_history_tree(app)
    if tree is None:
        return

    selection = tree.selection()
    if not selection:
        messagebox.showinfo("Remove History Entry", "Select a history entry first.")
        return

    item_id = selection[0]
    history_idx = getattr(app, "history_tree_item_map", {}).get((str(tree), item_id))
    if history_idx is None or history_idx < 0 or history_idx >= len(app.history):
        messagebox.showerror("Remove History Entry", "Could not resolve selected history entry.")
        return

    entry = app.history[history_idx]
    console = entry.get("console", "Unknown console")
    game = entry.get("game", "Unknown game")
    when = entry.get("time", "Unknown time")
    if not messagebox.askyesno(
        "Remove History Entry",
        f"Remove this history entry?\n\n{console} - {game}\n{when}",
    ):
        return

    app.history.pop(history_idx)
    save_history(app.history)
    refresh_history_tree(app)

    if app.phase == 1:
        from game_picker_engine import set_console_phase
        set_console_phase(app)


def clear_history(app):
    """Clear all history and refresh UI."""
    from tkinter import messagebox
    if not messagebox.askyesno("Clear History", "Delete all roll history?"):
        return
    app.history = []
    save_history(app.history)
    refresh_history_tree(app)
    if app.phase == 1:
        from game_picker_engine import set_console_phase
        set_console_phase(app)


def consoles_with_game(app, game_name):
    """Return console names that contain the given game title."""
    target = _norm(game_name)
    if not target:
        return []

    names = []
    for con in app.db:
        con_name = con.get("name", "")
        for game in con.get("games", []):
            if _norm(game) == target:
                names.append(con_name)
                break
    return names


def _platform_matched_consoles_for_game(app, picked_console, game_name, candidates):
    """Return candidate consoles whose names match IGDB platforms for this game."""
    if not candidates:
        return []

    picked_norm = _norm(picked_console)
    target_norm = _norm(game_name)
    cache_key = (picked_norm, target_norm)

    cache = getattr(app, "_game_platform_cache", None)
    if cache is None:
        cache = {}
        setattr(app, "_game_platform_cache", cache)

    platform_names = cache.get(cache_key)
    if platform_names is None:
        platform_names = []
        try:
            if is_configured():
                meta = fetch_game_metadata(game_name, picked_console)
                if "platforms" in meta and isinstance(meta["platforms"], list):
                    platform_names = [p for p in meta["platforms"] if str(p).strip()]
        except Exception:
            platform_names = []

        cache[cache_key] = platform_names

    platform_set = {_norm(name) for name in platform_names}
    matched = [name for name in candidates if _norm(name) in platform_set]

    # Always include the picked console itself.
    if picked_console and picked_console not in matched:
        matched.insert(0, picked_console)

    # De-duplicate preserving order.
    out = []
    seen = set()
    for name in matched:
        key = _norm(name)
        if key and key not in seen:
            out.append(name)
            seen.add(key)
    return out


def add_game_pick_history(app, picked_console, game_name, picked_time):
    """Add history for a picked game, including all matching multi-platform consoles."""
    target = _norm(game_name)
    consoles = consoles_with_game(app, game_name)
    if picked_console and picked_console not in consoles:
        consoles = [picked_console] + consoles

    consoles = _platform_matched_consoles_for_game(
        app, picked_console, game_name, consoles
    )

    # Ensure picked console appears first, then keep app.db order for the rest.
    ordered = []
    seen = set()
    if picked_console:
        ordered.append(picked_console)
        seen.add(_norm(picked_console))
    for name in consoles:
        key = _norm(name)
        if key and key not in seen:
            ordered.append(name)
            seen.add(key)

    if not ordered and picked_console:
        ordered = [picked_console]

    existing_pairs = {
        (_norm(e.get("console")), _norm(e.get("game")))
        for e in app.history
    }

    new_entries = []
    for console_name in ordered:
        pair = (_norm(console_name), target)
        if pair in existing_pairs:
            continue
        new_entries.append({
            "console": console_name,
            "game": game_name,
            "time": picked_time,
        })
        existing_pairs.add(pair)

    if new_entries:
        app.history[0:0] = new_entries
        save_history(app.history)

    return ordered, len(new_entries)


def available_games_for_console(app, console_name):
    """Get list of games for a console that haven't been picked yet."""
    con = next((c for c in app.db if c["name"] == console_name), None)
    if not con:
        return []
    picked = {
        _norm(e.get("game", ""))
        for e in app.history
        if _norm(e.get("console")) == _norm(console_name)
    }
    return [g for g in con["games"] if _norm(g) not in picked]
