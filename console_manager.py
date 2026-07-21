"""
Console management operations.
Handles console CRUD operations, editing, and display.
"""

from tkinter import messagebox
from data_manager import save_consoles


def refresh_console_list(app):
    """Refresh console listbox display."""
    app.console_lb.delete(0, "end")
    for c in app.db:
        app.console_lb.insert("end", f"  {c['name']}  ({len(c['games'])} games)")


def on_console_select(app, _=None):
    """Handle console selection in listbox."""
    sel = app.console_lb.curselection()
    if not sel:
        return
    idx = sel[0]
    app._editing_idx = idx
    con = app.db[idx]
    app.name_var.set(con["name"])
    app._selected_color = con["color"]
    from ui_manager import draw_color_preview
    draw_color_preview(app)
    app.games_text.delete("1.0", "end")
    app.games_text.insert("end", "\n".join(con["games"]))
    update_game_count(app)


def new_console(app):
    """Initialize form for creating new console."""
    app._editing_idx = -1
    app.console_lb.selection_clear(0, "end")
    app.name_var.set("")
    app._selected_color = app.PALETTE[len(app.db) % len(app.PALETTE)]
    from ui_manager import draw_color_preview
    draw_color_preview(app)
    app.games_text.delete("1.0", "end")
    update_game_count(app)
    app.name_entry.focus()


def save_console(app):
    """Save current console being edited."""
    name = app.name_var.get().strip()
    color = app._selected_color
    raw = app.games_text.get("1.0", "end")
    games = [g.strip() for g in raw.splitlines() if g.strip()]

    if not name:
        messagebox.showerror("Error", "Console name cannot be empty.")
        return
    if not games:
        messagebox.showerror("Error", "Add at least one game.")
        return

    if app._editing_idx >= 0:
        app.db[app._editing_idx] = {"name": name, "color": color, "games": games}
    else:
        # check duplicate name
        if any(c["name"].lower() == name.lower() for c in app.db):
            messagebox.showerror("Error", f'A console named "{name}" already exists.')
            return
        app.db.append({"name": name, "color": color, "games": games})
        app._editing_idx = len(app.db) - 1

    save_consoles(app.db)
    refresh_console_list(app)
    app.console_lb.selection_set(app._editing_idx)
    from game_picker_engine import set_console_phase
    set_console_phase(app)


def delete_console(app):
    """Delete selected console."""
    sel = app.console_lb.curselection()
    if not sel:
        messagebox.showinfo("Select one", "Select a console to delete.")
        return
    idx = sel[0]
    name = app.db[idx]["name"]
    if messagebox.askyesno("Delete", f"Delete {name}?"):
        app.db.pop(idx)
        save_consoles(app.db)
        refresh_console_list(app)
        new_console(app)
        from game_picker_engine import set_console_phase
        set_console_phase(app)


def move_console(app, direction):
    """Move console up/down in list."""
    sel = app.console_lb.curselection()
    if not sel:
        return
    idx = sel[0]
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(app.db):
        return
    app.db[idx], app.db[new_idx] = app.db[new_idx], app.db[idx]
    save_consoles(app.db)
    refresh_console_list(app)
    app.console_lb.selection_set(new_idx)
    app._editing_idx = new_idx
    from game_picker_engine import set_console_phase
    set_console_phase(app)


def pick_color(app, _=None):
    """Open color picker dialog."""
    from tkinter import colorchooser
    result = colorchooser.askcolor(color=app._selected_color,
                                   title="Pick console color")
    if result and result[1]:
        app._selected_color = result[1]
        from ui_manager import draw_color_preview
        draw_color_preview(app)


def update_game_count(app, _=None):
    """Update game count label."""
    raw = app.games_text.get("1.0", "end")
    count = len([g for g in raw.splitlines() if g.strip()])
    app.game_count_lbl.configure(text=f"{count} games")


def reset_defaults(app):
    """Clear all consoles and reset to empty state."""
    if messagebox.askyesno("Clear Consoles", "Remove all consoles and games from your library?"):
        app.db = []
        save_consoles(app.db)
        refresh_console_list(app)
        new_console(app)
        from game_picker_engine import set_console_phase
        set_console_phase(app)
