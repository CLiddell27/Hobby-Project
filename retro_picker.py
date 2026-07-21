"""
Retro Game Picker Wheel - Entry Point
A spinning wheel app that picks a random retro console then a random game,
with persistent history and editable libraries.
"""

from game_picker import RetroPickerApp


if __name__ == "__main__":
    app = RetroPickerApp()
    app.mainloop()
