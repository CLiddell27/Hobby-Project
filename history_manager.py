"""
History management for tracking game picks.
Handles history UI updates and data retrieval.
"""

from data_manager import save_history


def rebuild_history_tabs(app):
    """Rebuild history notebook tabs when console list changes."""
    if not hasattr(app, "history_nb"):
        return

    selected_text = None
    current = app.history_nb.select()
    if current:
        selected_text = app.history_nb.tab(current, "text")

    for tab_id in app.history_nb.tabs():
        app.history_nb.forget(tab_id)

    app.history_console_trees = {}
    app.history_all_tree = add_history_tab(app, "All", include_console=True)

    for con in app.db:
        app.history_console_trees[con["name"]] = add_history_tab(
            app, con["name"], include_console=False
        )

    if selected_text:
        for tab_id in app.history_nb.tabs():
            if app.history_nb.tab(tab_id, "text") == selected_text:
                app.history_nb.select(tab_id)
                break


def add_history_tab(app, title, include_console):
    """Add a single history tab to the history notebook."""
    import tkinter as tk
    from tkinter import ttk
    
    frame = ttk.Frame(app.history_nb)
    app.history_nb.add(frame, text=title)
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


def refresh_history_tree(app):
    """Refresh history treeview with current data."""
    if not hasattr(app, "history_all_tree") or app.history_all_tree is None:
        return

    for row in app.history_all_tree.get_children():
        app.history_all_tree.delete(row)
    for tree in app.history_console_trees.values():
        for row in tree.get_children():
            tree.delete(row)

    sorted_history = sorted(
        app.history,
        key=lambda e: (
            (e.get("console") or "").lower(),
            e.get("time") or "",
        ),
    )
    for entry in sorted_history:
        console = entry.get("console", "")
        app.history_all_tree.insert("", "end",
                                     values=(console,
                                             entry.get("game", ""),
                                             entry.get("time", "")))

        tree = app.history_console_trees.get(console)
        if tree is not None:
            tree.insert("", "end",
                        values=(entry.get("game", ""),
                                entry.get("time", "")))


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


def available_games_for_console(app, console_name):
    """Get list of games for a console that haven't been picked yet."""
    con = next((c for c in app.db if c["name"] == console_name), None)
    if not con:
        return []
    picked = {
        e.get("game", "")
        for e in app.history
        if (e.get("console") or "").lower() == console_name.lower()
    }
    return [g for g in con["games"] if g not in picked]
