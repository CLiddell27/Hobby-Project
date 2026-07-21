"""
Retro Game Picker Wheel - Main Application Class
A spinning wheel app that picks a random retro console then a random game,
with persistent history and editable libraries.
"""

import tkinter as tk
import time
from data_manager import load_consoles, load_history
from ui_manager import build_ui
from game_picker_engine import set_console_phase


class RetroPickerApp(tk.Tk):
    """Main application class for the Retro Game Picker."""
    
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
        self._label_layout_cache = {}
        self._last_seg = -1
        self._anim_time = time.perf_counter

        # Build UI
        build_ui(self)
        set_console_phase(self)
