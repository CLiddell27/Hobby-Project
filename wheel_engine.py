"""
Wheel drawing and animation engine.
Handles all visual wheel operations and animations.
"""

import math
import tkinter.font as tkfont
from color_utils import contrasting_text


def draw_wheel(app, highlight_idx=-1):
    """Draw the spinning wheel on canvas."""
    c = app.canvas
    c.delete("all")
    n = len(app.wheel_items)
    w = int(c.cget("width"))
    h = int(c.cget("height"))
    cx, cy = w // 2, h // 2
    r = min(w, h) // 2 - 12
    if n == 0:
        c.create_text(cx, cy, text="No items", fill="#555577",
                      font=("Segoe UI", 14))
        return

    arc = 2 * math.pi / n
    show_labels = True

    for i, (label, color) in enumerate(app.wheel_items):
        start = math.degrees(app.angle + i * arc)
        extent = math.degrees(arc)
        # segment
        c.create_arc(cx - r, cy - r, cx + r, cy + r,
                     start=start, extent=extent,
                     fill=color, outline="#ffffff", width=1, style="pieslice")
        if show_labels:
            mid_deg = start + extent / 2
            mid_rad = math.radians(mid_deg)
            inner_r = max(28, int(r * 0.26))
            outer_r = max(inner_r + 20, r - 18)
            label_r = (inner_r + outer_r) / 2
            tx = cx + label_r * math.cos(mid_rad)
            ty = cy - label_r * math.sin(mid_rad)

            # Place text at the center of a radial segment inside the slice,
            # so it moves and rotates exactly with that slice.
            # Match canvas text rotation direction to wheel geometry so labels
            # stay locked to their slice instead of counter-rotating.
            txt_angle = mid_deg % 360
            txt, fs = fit_label_text(app, label, arc, inner_r, outer_r, label_r, n)
            c.create_text(tx, ty, text=txt, fill=contrasting_text(color),
                          font=("Segoe UI", fs, "bold"),
                          angle=txt_angle,
                          anchor="center")

    # highlight ring
    if highlight_idx >= 0:
        i = highlight_idx
        start = math.degrees(app.angle + i * arc)
        c.create_arc(cx - r, cy - r, cx + r, cy + r,
                     start=start, extent=math.degrees(arc),
                     fill="", outline="#ffffff", width=3, style="pieslice")

    # rim
    c.create_oval(cx - r, cy - r, cx + r, cy + r,
                  outline="#333355", width=5)
    # hub
    c.create_oval(cx - 18, cy - 18, cx + 18, cy + 18,
                  fill="#ffffff", outline="#cccccc", width=1)
    c.create_text(cx, cy, text=">", fill="#555577",
                  font=("Segoe UI", 11, "bold"))


def fit_label_text(app, label, arc, inner_r, outer_r, label_r, n):
    """Fit label text to available wheel space, with caching."""
    key = (label, n, int(inner_r), int(outer_r), int(label_r), round(arc, 4))
    cached = app._label_layout_cache.get(key)
    if cached:
        return cached

    # Keep labels single-line and within the slice by constraining both
    # radial length (text width) and angular thickness (font size).
    radial_space = max(18, int((outer_r - inner_r) - 6))
    slice_thickness = max(4, int(label_r * arc * 0.72))

    max_font = min(max(7, min(13, int(220 / max(1, n)))), max(5, slice_thickness))
    min_font = 3

    txt = label.strip()
    if not txt:
        out = ("", min_font)
        app._label_layout_cache[key] = out
        return out

    for fs in range(max_font, min_font - 1, -1):
        font = tkfont.Font(family="Segoe UI", size=fs, weight="bold")
        if font.measure(txt) <= radial_space:
            out = (txt, fs)
            app._label_layout_cache[key] = out
            return out

    # If still too long at minimum size, keep full name but use minimum size.
    out = (txt, min_font)
    app._label_layout_cache[key] = out
    return out


def get_pointed_idx(app):
    """Get the index of the wheel segment currently pointed at."""
    n = len(app.wheel_items)
    if n == 0:
        return 0
    arc = 2 * math.pi / n
    # pointer is at the right (0 deg). We want segment at angle=0
    norm = (-app.angle % (2 * math.pi) + 2 * math.pi) % (2 * math.pi)
    return int(norm / arc) % n


def ease(t):
    """Easing function for spin animation (ease-out cubic)."""
    return 1 - (1 - t) ** 3.5


def animate_spin(app):
    """Animate the wheel spin."""
    t = (app._anim_time() - app._anim_start) / app._anim_dur
    t = min(t, 1.0)
    app.angle = app._anim_angle0 + app._anim_delta * ease(t)

    pi = get_pointed_idx(app)
    draw_wheel(app, pi)
    name = app.wheel_items[pi][0] if app.wheel_items else ""
    app.live_label.configure(text=name)

    # tick sound via Tk bell if segment changes
    if pi != app._last_seg:
        app._last_seg = pi

    if t < 1.0:
        app._spin_job = app.after(16, animate_spin, app)
    else:
        app.spinning = False
        app.spin_btn.configure(state="normal")
        app.manual_btn.configure(state="normal")
        app.live_label.configure(text="")
        final = get_pointed_idx(app)

        if app.phase == 1:
            from game_picker_engine import selectable_indices, show_result
            selectable = selectable_indices(app)
            if selectable and final not in selectable:
                import random
                final = random.choice(selectable)
                draw_wheel(app, final)

        label, _ = app.wheel_items[final]
        show_result(app, label)
