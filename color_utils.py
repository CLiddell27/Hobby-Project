"""
Color utility functions for color manipulation and contrast calculations.
"""


def hex_to_rgb(h):
    """Convert hex color string to RGB tuple."""
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    """Convert RGB values to hex color string."""
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
    )


def blend_color(base_hex, i, n):
    """Create alternating lighter/darker color bands from base color."""
    r, g, b = hex_to_rgb(base_hex)
    # alternate lighter/darker bands
    shift = 35 if i % 2 == 0 else -20
    return rgb_to_hex(r + shift, g + shift, b + shift)


def contrasting_text(bg_hex):
    """Determine if black or white text contrasts better with background color."""
    r, g, b = hex_to_rgb(bg_hex)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.5 else "#ffffff"
