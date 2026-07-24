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
    extent_deg = math.degrees(arc)

    # Keep separators visible even for dense wheels so segments don't visually
    # collapse into a single solid disk at very high item counts.
    if extent_deg < 1.8:
        seg_outline = "#5a6288"
        seg_width = 1
    elif extent_deg < 3.0:
        seg_outline = "#7a82aa"
        seg_width = 1
    else:
        seg_outline = "#ffffff"
        seg_width = 1

    for i, (label, color) in enumerate(app.wheel_items):
        start_rad = app.angle + i * arc
        end_rad = start_rad + arc
        start = math.degrees(app.angle + i * arc)
        extent = extent_deg
        # segment
        if extent_deg < 0.9:
            # Tiny arcs can quantize poorly in Tk; draw as a thin annular sector.
            ring_inner = max(20, int(r * 0.18))
            xos = cx + r * math.cos(start_rad)
            yos = cy - r * math.sin(start_rad)
            xoe = cx + r * math.cos(end_rad)
            yoe = cy - r * math.sin(end_rad)
            xis = cx + ring_inner * math.cos(start_rad)
            yis = cy - ring_inner * math.sin(start_rad)
            xie = cx + ring_inner * math.cos(end_rad)
            yie = cy - ring_inner * math.sin(end_rad)
            c.create_polygon(
                xos, yos, xoe, yoe, xie, yie, xis, yis,
                fill=color, outline=seg_outline, width=seg_width
            )
        else:
            c.create_arc(cx - r, cy - r, cx + r, cy + r,
                         start=start, extent=extent,
                         fill=color, outline=seg_outline, width=seg_width, style="pieslice")
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
            txt_color = contrasting_text(color)
            if n >= 80 and txt_color == "#ffffff":
                txt_color = "#c2c9ea"
            elif n >= 80 and txt_color == "#000000":
                txt_color = "#1f2540"
            txt_weight = "normal" if n >= 60 else "bold"
            c.create_text(tx, ty, text=txt, fill=txt_color,
                          font=("Segoe UI", fs, txt_weight),
                          angle=txt_angle,
                          anchor="center")

    # highlight ring
    if highlight_idx >= 0:
        i = highlight_idx
        start = math.degrees(app.angle + i * arc)
        c.create_arc(cx - r, cy - r, cx + r, cy + r,
                     start=start, extent=extent,
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
    angular_space = max(2, int(label_r * arc * 0.62))
    font_by_count = max(2, min(13, int(240 / max(1, n))))

    max_font = min(font_by_count, angular_space)
    min_font = 2

    if max_font < min_font:
        max_font = min_font

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

    # If still too long, truncate at minimum size to prevent text spillover.
    font = tkfont.Font(family="Segoe UI", size=min_font, weight="normal" if n >= 60 else "bold")
    if font.measure(txt) <= radial_space:
        out = (txt, min_font)
        app._label_layout_cache[key] = out
        return out

    lo, hi = 1, len(txt)
    best = txt[:1]
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = txt[:mid]
        if font.measure(cand) <= radial_space:
            best = cand
            lo = mid + 1
        else:
            hi = mid - 1

    out = (best, min_font)
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

        from game_picker_engine import selectable_indices, show_result
        if app.phase == 1:
            selectable = selectable_indices(app)
            if selectable and final not in selectable:
                import random
                final = random.choice(selectable)
                draw_wheel(app, final)

        label, _ = app.wheel_items[final]
        show_result(app, label)
