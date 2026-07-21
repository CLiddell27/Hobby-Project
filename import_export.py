"""
Import/export functionality for consoles and games.
Handles loading from various file formats and merging strategies.
"""

import os
import json
from tkinter import filedialog, messagebox
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
