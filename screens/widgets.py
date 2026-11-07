"""The building blocks an admin places on a TV with the layout designer.

A layout is a list of {"t": type, "x", "y", "w", "h", "o": {settings}} on a grid
of COLS x ROWS cells covering the 1920x1080 screen. Each type is drawn by
templates/display/widgets/<type>.html. FIELDS says which settings a type has;
the designer builds its settings form from it, and clean() checks every value.
"""

from django.utils import timezone

COLS, ROWS = 24, 12

# Settings every widget has: how its box looks.
STYLE_FIELDS = [
    {"k": "look", "label": "Box", "type": "select", "default": "card",
     "choices": [["card", "Glass card"], ["solid", "Solid colour"], ["clear", "No box"]]},
    {"k": "accent", "label": "Accent colour", "type": "color", "default": ""},
    {"k": "fill", "label": "Box colour (solid)", "type": "color", "default": "#0b2233"},
]

ALIGN = [["center", "Centre"], ["start", "Left"], ["end", "Right"]]

# type: label, min width, min height, more than one allowed, own settings
WIDGETS = {
    "logo": ("Logo", 2, 2, False, []),
    "clock": ("Analogue clock and date", 3, 2, False, []),
    "prayer": ("Prayer times", 3, 3, False, []),
    "arnews": ("Arabic headlines wheel", 3, 2, False, []),
    "media": ("Video / slideshow (controlled from the agent panel)", 6, 4, False, []),
    "news": ("About us / news", 6, 3, False, []),
    "flag": ("Flag / picture", 3, 3, False, []),
    "contact": ("Contact and QR", 4, 3, False, []),
    "text": ("Text / announcement", 2, 1, True, [
        {"k": "title", "label": "Title", "type": "text", "default": ""},
        {"k": "body", "label": "Text", "type": "textarea", "default": ""},
        {"k": "size", "label": "Text size (px)", "type": "number", "min": 12, "max": 160, "default": 32},
        {"k": "align", "label": "Line up", "type": "select", "choices": ALIGN, "default": "center"},
        {"k": "rtl", "label": "Right to left (Arabic)", "type": "check", "default": False},
        {"k": "color", "label": "Text colour", "type": "color", "default": "#ffffff"},
    ]),
    "image": ("Picture", 2, 2, True, [
        {"k": "item", "label": "Picture", "type": "image", "default": ""},
        {"k": "fit", "label": "Fit", "type": "select", "default": "cover",
         "choices": [["cover", "Fill the box (may crop)"], ["contain", "Whole picture"]]},
    ]),
    "video": ("Video on a loop", 3, 2, True, [
        {"k": "item", "label": "Video", "type": "video", "default": ""},
        {"k": "fit", "label": "Fit", "type": "select", "default": "cover",
         "choices": [["cover", "Fill the box (may crop)"], ["contain", "Whole video"]]},
    ]),
    "slides": ("Photo slideshow", 3, 2, True, [
        {"k": "playlist", "label": "Photo list (blank = every approved photo)", "type": "playlist", "default": ""},
        {"k": "seconds", "label": "Seconds per photo", "type": "number", "min": 2, "max": 120, "default": 8},
        {"k": "fit", "label": "Fit", "type": "select", "default": "cover",
         "choices": [["cover", "Fill the box (may crop)"], ["contain", "Whole photo"]]},
    ]),
    "digital": ("Digital clock", 3, 1, True, [
        {"k": "hours", "label": "Clock", "type": "select", "default": "24", "choices": [["24", "24 hours"], ["12", "12 hours"]]},
        {"k": "seconds", "label": "Show seconds", "type": "check", "default": False},
        {"k": "date", "label": "Show the date", "type": "check", "default": True},
        {"k": "lang", "label": "Language", "type": "select", "default": "en",
         "choices": [["en", "English"], ["ar", "Arabic"], ["both", "Both"]]},
    ]),
    "countdown": ("Countdown", 3, 1, True, [
        {"k": "label", "label": "What it counts down to", "type": "text", "default": ""},
        {"k": "until", "label": "Date and time", "type": "datetime", "default": ""},
        {"k": "done", "label": "Text when it is over", "type": "text", "default": ""},
    ]),
    "qr": ("QR code", 2, 2, True, [
        {"k": "url", "label": "Link", "type": "url", "default": ""},
        {"k": "label", "label": "Text under it", "type": "text", "default": ""},
    ]),
    "ticker": ("Scrolling announcements", 6, 1, False, [
        {"k": "speed", "label": "Speed (seconds for one pass)", "type": "number", "min": 10, "max": 300, "default": 60},
    ]),
    "weather": ("Weather now", 3, 1, True, [
        {"k": "unit", "label": "Unit", "type": "select", "default": "c", "choices": [["c", "°C"], ["f", "°F"]]},
    ]),
    "web": ("Web page", 3, 2, True, [
        {"k": "url", "label": "Address (https://...)", "type": "url", "default": ""},
        {"k": "zoom", "label": "Zoom %", "type": "number", "min": 25, "max": 200, "default": 100},
    ]),
}


def fields(t):
    return WIDGETS[t][4] + STYLE_FIELDS


def catalog():
    """What the designer needs to know about each widget."""
    return {k: {"label": v[0], "minW": v[1], "minH": v[2], "multi": v[3], "fields": fields(k)}
            for k, v in WIDGETS.items()}


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


def _value(f, v):
    """One setting, checked against its field. Anything odd falls back to the default."""
    d = f["default"]
    try:
        if f["type"] == "check":
            return bool(v)
        if f["type"] == "number":
            return max(f["min"], min(f["max"], int(v)))
        if f["type"] == "select":
            return v if v in [c[0] for c in f["choices"]] else d
        if f["type"] == "color":
            return v if isinstance(v, str) and (v == "" or (len(v) == 7 and v[0] == "#")) else d
        if f["type"] == "url":
            return v if isinstance(v, str) and v.startswith(("https://", "http://")) else ""
        if f["type"] in ("image", "video", "playlist"):
            return int(v) if str(v).isdigit() else ""
        return str(v)[:2000] if v is not None else d
    except (TypeError, ValueError):
        return d


def clean(layout):
    """Keep only known widgets inside the grid, with checked settings. Bad input never breaks the TV."""
    out, seen = [], set()
    for item in layout if isinstance(layout, list) else []:
        if not isinstance(item, dict):
            continue
        t = item.get("t")
        if t not in WIDGETS or (t in seen and not WIDGETS[t][3]):
            continue
        _, min_w, min_h, _, _ = WIDGETS[t]
        try:
            w = max(min_w, min(COLS, int(item.get("w", min_w))))
            h = max(min_h, min(ROWS, int(item.get("h", min_h))))
            x = max(0, min(COLS - w, int(item.get("x", 0))))
            y = max(0, min(ROWS - h, int(item.get("y", 0))))
        except (TypeError, ValueError):
            continue
        seen.add(t)
        given = item.get("o") if isinstance(item.get("o"), dict) else {}
        o = {f["k"]: _value(f, given.get(f["k"], f["default"])) for f in fields(t)}
        out.append({"t": t, "x": x, "y": y, "w": w, "h": h, "o": o})
    return out


def _resolve(item):
    """Look up what a widget shows (file addresses, QR picture, messages) so the template stays simple."""
    from core.models import TickerMessage
    from core.views import _qr_svg
    from library.models import MediaItem, Playlist

    o, t, data = item["o"], item["t"], {}
    if t in ("image", "video") and o.get("item"):
        m = MediaItem.objects.filter(pk=o["item"], status="approved", kind=t).first()
        data["url"] = m.file.url if m else ""
    elif t == "slides":
        pl = Playlist.objects.filter(pk=o["playlist"], kind="image").first() if o.get("playlist") else None
        items = pl.playable_items() if pl else MediaItem.objects.filter(kind="image", status="approved")
        data["urls"] = [m.file.url for m in items]
    elif t == "qr":
        data["svg"] = _qr_svg(o.get("url"))
    elif t == "ticker":
        now = timezone.now()
        data["messages"] = [m.text for m in TickerMessage.objects.filter(is_active=True).order_by("order", "id")
                            if (not m.starts_at or m.starts_at <= now) and (not m.ends_at or m.ends_at > now)]
    return data


def for_screen(screen):
    """The screen's saved layout, or the default when none is saved; ready for the TV template."""
    items = clean(screen.layout) if screen.layout else clean(DEFAULT_LAYOUT)
    return [dict(i, n=n, template=f"display/widgets/{i['t']}.html", data=_resolve(i))
            for n, i in enumerate(items)]
