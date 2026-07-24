# Retro Game Picker Wheel

A Python tkinter app that picks a retro console and game using an animated wheel. It includes persistent history, IGDB-powered import/metadata, and fully editable console libraries.

## Overview

Retro Game Picker Wheel is a hobby project that helps you pick what retro game to play when you can't decide. The app presents a beautiful, spinning wheel interface where you select a console first, then a game from that console's library. Your picks are saved to history and you can manage your console collection with ease.

## What's New in v2.0.1

- IGDB integration for consoles, games, and metadata
- Batch game import with two modes:
  - `Auto Import All` (no per-console prompts)
  - `Import (confirm each)` (Yes/No/Cancel per console)
- Duplicate-safe import behavior:
  - existing games are kept
  - only new titles are appended
- Single-entry history removal (`Remove Selected` button and `Delete` key)
- Multi-platform title handling:
  - title can be marked across matching consoles
  - platform checks use IGDB metadata to reduce false matches
- Console wheel now only shows selectable consoles (no grayed-out slices)
- History tab scrolling improvements

## Features

- **Animated Wheel Picker**: Smooth wheel animation for console and game picks
- **Two-Phase Selection**: Pick a console, then pick a game from that console
- **Persistent History**: Tracks picks with timestamps across sessions
- **History Management**: Remove one selected entry or clear everything
- **Console/Game Editor**: Add, edit, delete, reorder, recolor, and import lists
- **IGDB Import**: Import platforms and games directly from IGDB
- **IGDB Metadata**: Shows year, genre, cover art, and platforms for picked games
- **Cross-Platform Support**: Windows, macOS, Linux

## Project Structure

The application is organized into 10 modular files for clean, maintainable code:

### Core Application
- **`retro_picker.py`** - Entry point script to launch the application

### Main Application Class
- **`game_picker.py`** - `RetroPickerApp` class that initializes the main window and application state

### Business Logic
- **`game_picker_engine.py`** - Core game selection logic including:
  - `spin()` - Initiates wheel spin animation
  - `manual_pick()` - Allow manual selection from lists
  - `set_console_phase()` / `set_game_phase()` - Phase transitions
  - `show_result()` / `reset()` - Result handling and state reset
  - `choose_from_list()` - Searchable list picker dialog

- **`wheel_engine.py`** - Wheel rendering and animation:
  - `draw_wheel()` - Renders the wheel with segments
  - `fit_label_text()` - Smart label sizing and caching
  - `animate_spin()` - Smooth animation with easing
  - `get_pointed_idx()` - Segment detection

### UI Components
- **`ui_manager.py`** - Tkinter UI construction:
  - `build_ui()` - Main UI layout
  - `build_wheel_tab()` - Spinning wheel interface
  - `build_history_tab()` - History viewer
  - `build_manage_tab()` - Console/game editor
  - `draw_color_preview()` - Color selector preview

### Data Management
- **`data_manager.py`** - File I/O and persistence:
  - `load_consoles()` / `save_consoles()`
  - `load_history()` / `save_history()`
  - `dedupe_keep_order()` - Utility for deduplication
  - `data_dir()` - Platform-aware data directory

- **`history_manager.py`** - History tracking and UI:
  - `rebuild_history_tabs()` / `refresh_history_tree()`
  - `clear_history()` - Clear all history
  - `available_games_for_console()` - Filter unpicked games

- **`console_manager.py`** - Console CRUD operations:
  - `new_console()` / `save_console()` / `delete_console()`
  - `move_console()` - Reorder consoles
  - `on_console_select()` - Selection handler
  - `pick_color()` - Color customization
  - `update_game_count()` - Update game counter

### Utilities
- **`color_utils.py`** - Color manipulation functions:
  - `hex_to_rgb()` / `rgb_to_hex()` - Color conversion
  - `blend_color()` - Generate alternating color bands
  - `contrasting_text()` - Auto contrast color selection

- **`import_export.py`** - Import/export functionality:
  - `import_consoles_list()` - Load consoles from files
  - `import_games_list()` - Load games from files
  - `parse_consoles_payload()` - Parse various JSON formats
  - `read_games_file()` / `read_lines_file()` - File readers

## Installation

### Requirements
- Python 3.9+
- tkinter (usually included with Python)
- Pillow (for cover image display)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd Hobby\ Project
```

2. (Optional) Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Optional: provide IGDB credentials in `credentials.py`:
```python
IGDB_CLIENT_ID = "your_client_id"
IGDB_CLIENT_SECRET = "your_client_secret"
```

4. Run the application:
```bash
python retro_picker.py
```

### Windows Executable (Pre-built)

A standalone Windows executable is available in the `dist/` folder:

- **`dist/RetroPickerWheel.exe`** - Run this file directly without needing Python installed
- Simply double-click to launch the application
- No dependencies or virtual environment needed
- Includes all required Python modules and libraries

#### Building Your Own Executable

If you want to rebuild the executable from source:

1. Install PyInstaller:
```bash
pip install pyinstaller
```

2. Build using the spec file:
```bash
python -m PyInstaller RetroPickerWheel.spec --noconfirm
```

3. The executable will be created in `dist/RetroPickerWheel.exe`

## Usage

### Main Interface

The application has three tabs:

#### Wheel Tab
- **SPIN**: Randomly select console then game
- **PICK CONSOLE / PICK GAME**: Manual searchable picker
- **RESET**: Return to console selection
- Shows IGDB metadata (when available): cover, year, genre, platforms

#### History Tab
- View all picks with timestamps
- Filter by console tab
- **Remove Selected**: Delete one highlighted history entry
- **Clear History**: Delete all history
- Mouse wheel scrolls the console-tab strip

#### Manage Tab
- **Left Panel**: Console list and import controls
- **Right Panel**: Console editor and IGDB settings
- Import options:
  - local files (TXT/CSV/JSON)
  - IGDB platform import
  - IGDB game import (single console)
  - IGDB batch game import (auto or confirm each)

### Keyboard Shortcuts

- **Enter**: Confirm/import in dialogs
- **Escape**: Cancel/close dialogs
- **Delete**: Remove selected history row
- **Type in search fields**: Filter picker lists

### File Import Formats

**Consoles** (JSON format):
```json
{
  "consoles": [
    {
      "name": "NES",
      "color": "#1565c0",
      "games": ["Super Mario Bros", "The Legend of Zelda"]
    }
  ]
}
```

**Games** (TXT format):
```
Super Mario Bros
The Legend of Zelda
Metroid
```

**Games** (CSV/JSON formats also supported)

## Data Storage

The application stores data in a platform-specific user data directory:

- **Windows**: `%APPDATA%\RetroPickerWheel\`
- **macOS/Linux**: `~/.local/share/RetroPickerWheel/`

Files created:
- `consoles.json` - Your console library
- `history.json` - Pick history with timestamps
- `igdb_config.json` - Optional saved IGDB settings
- `igdb_cache/` - Cached cover images

## Credential Handling

- `credentials.py` is intentionally ignored by git and can store private IGDB credentials for local/exe use.
- If `credentials.py` is empty or missing, the app falls back to saved settings from the UI.

## Development

### Module Organization Philosophy

This project follows a modular design pattern:

1. **Separation of Concerns** - Each module has a single, clear responsibility
2. **Business Logic Isolation** - Core logic separated from UI code
3. **Reusability** - Functions designed to be called independently
4. **Testability** - Modular structure makes unit testing easier
5. **Maintainability** - Clear module boundaries make updates safer

### Adding Features

To add new features:

1. Identify which module owns the functionality
2. Add your function to that module
3. Update imports in dependent modules if needed
4. Test the feature in isolation and with the UI

### Color Palette

The default palette includes 16 rich colors perfect for retro aesthetics:
```python
PALETTE = [
    "#b71c1c","#880e4f","#4a148c","#283593","#01579b","#006064",
    "#1b5e20","#33691e","#e65100","#bf360c","#3e2723","#546e7a",
    "#4527a0","#1565c0","#00695c","#2e7d32",
]
```

## Troubleshooting

### Application won't start
- Ensure Python 3.9+ is installed
- Check that tkinter is available: `python -m tkinter`
- Verify all module imports are working

### Import is slow or limited
- IGDB rate limits can delay large imports
- Use `Auto Import All` for unattended batches
- Use region filters to reduce volume

### Wheel animation is choppy
- Close other applications to free up CPU
- Reduce screen resolution temporarily
- Animation frame rate is fixed at ~60Hz

## Performance Notes

- Label layout is cached to prevent recalculation on every wheel draw
- Wheel animation runs at 16ms intervals (~60 FPS)
- Large game lists (1000+) may be slower when rendering labels

## License

This is a hobby project. Feel free to modify and use as you wish.

## Future Enhancement Ideas

- Sound effects for wheel ticking
- Save/load multiple console libraries
- Weighted selection (favor games played less recently)
- Statistics and analytics (most picked games/consoles)
- Difficulty levels (short list vs. deep library)
- Game metadata (release year, platform, rating)
- Dark/light theme switching
- Network multiplayer picks

## Author

Created as a fun hobby project for retro gaming enthusiasts!
