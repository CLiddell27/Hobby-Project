# Retro Game Picker Wheel

A Python tkinter application that randomly selects a retro console and game using a visually engaging spinning wheel interface. Features persistent history tracking, editable game libraries, and import/export capabilities.

## Overview

Retro Game Picker Wheel is a hobby project that helps you pick what retro game to play when you can't decide. The app presents a beautiful, spinning wheel interface where you select a console first, then a game from that console's library. Your picks are saved to history and you can manage your console collection with ease.

## Features

- **Interactive Spinning Wheel**: Animated wheel interface for selecting consoles and games
- **Two-Phase Selection**: Pick a console first, then pick a game from that console
- **Persistent History**: Automatically tracks all picks with timestamps
- **Editable Libraries**: Add, edit, or delete consoles and games
- **Import/Export**: Load console and game lists from JSON, TXT, or CSV files
- **Console Management**: Reorder consoles, customize colors, and manage game lists
- **History Browsing**: View full history or filter by console
- **Cross-Platform**: Works on Windows, macOS, and Linux

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
- Python 3.6+
- tkinter (usually included with Python)

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

3. Run the application:
```bash
python retro_picker.py
```

## Usage

### Main Interface

The application has three tabs:

#### Wheel Tab
- **SPIN**: Automatically select a console and then a game
- **PICK CONSOLE**: Manually select a console from a searchable list
- **RESET**: Return to console selection after picking a game
- View the currently highlighted wheel segment above the buttons

#### History Tab
- View all your picks with timestamps
- Filter history by console using separate tabs
- **Clear History**: Remove all recorded picks

#### Manage Tab
- **Left Panel**: Console list with add/delete/reorder controls
- **Right Panel**: Console editor
  - Edit console name and assign color
  - Add/edit/remove games (one per line)
  - Import games from files
- **Import Consoles**: Load console libraries from external files

### Keyboard Shortcuts

- **Search**: Start typing in list picker dialogs to filter items
- **Enter**: Confirm selection in dialogs
- **Escape**: Close dialogs
- **Arrow Keys**: Navigate lists

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
- Ensure Python 3.6+ is installed
- Check that tkinter is available: `python -m tkinter`
- Verify all module imports are working

### Data not saving
- Check that `~/.local/share/RetroPickerWheel/` or `%APPDATA%\RetroPickerWheel\` exists
- Ensure the directory is writable
- Check console output for file I/O errors

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
