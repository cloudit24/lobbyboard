"""The building blocks an admin places on a TV with the layout designer.

A layout is a list of {"t": type, "x", "y", "w", "h"} on a grid of COLS x ROWS
cells covering the 1920x1080 screen. Each type is drawn by
templates/display/widgets/<type>.html.
"""

COLS, ROWS = 24, 12

# type: (label for the admin, min width, min height)
WIDGETS = {
    "logo": ("Logo", 2, 2),
    "clock": ("Clock and date", 3, 2),
    "prayer": ("Prayer times", 3, 3),
    "arnews": ("Arabic headlines wheel", 3, 2),
    "media": ("Video / slideshow", 6, 4),
    "news": ("About us / news", 6, 3),
    "flag": ("Flag / picture", 3, 3),
    "contact": ("Contact and QR", 4, 3),
}

# The layout every TV starts with (the original reception design).
DEFAULT_LAYOUT = [
    {"t": "logo", "x": 0, "y": 0, "w": 5, "h": 3},
    {"t": "clock", "x": 0, "y": 3, "w": 5, "h": 2},
    {"t": "prayer", "x": 0, "y": 5, "w": 5, "h": 4},
    {"t": "arnews", "x": 0, "y": 9, "w": 5, "h": 3},
    {"t": "media", "x": 5, "y": 0, "w": 13, "h": 7},
    {"t": "news", "x": 5, "y": 7, "w": 13, "h": 5},
    {"t": "flag", "x": 18, "y": 0, "w": 6, "h": 8},
    {"t": "contact", "x": 18, "y": 8, "w": 6, "h": 4},
]


def clean(layout):
    """Keep only known widgets, each once, inside the grid. Bad input never breaks the TV."""
    out, seen = [], set()
    for item in layout if isinstance(layout, list) else []:
        if not isinstance(item, dict):
            continue
        t = item.get("t")
        if t not in WIDGETS or t in seen:
            continue
        _, min_w, min_h = WIDGETS[t]
        try:
            w = max(min_w, min(COLS, int(item.get("w", min_w))))
            h = max(min_h, min(ROWS, int(item.get("h", min_h))))
            x = max(0, min(COLS - w, int(item.get("x", 0))))
            y = max(0, min(ROWS - h, int(item.get("y", 0))))
        except (TypeError, ValueError):
            continue
        seen.add(t)
        out.append({"t": t, "x": x, "y": y, "w": w, "h": h})
    return out


def for_screen(screen):
    """The screen's saved layout, or the default when none is saved; with template paths for the TV."""
    items = clean(screen.layout) if screen.layout else DEFAULT_LAYOUT
    return [dict(i, template=f"display/widgets/{i['t']}.html") for i in items]
