"""Copies About us content from a website's public pages, once.

Used by `manage.py copy_about`. It reads the pages any visitor sees, in
Arabic and English, and picks out the strategy cards (vision, mission,
values, objectives) and the product cards with their icons. The result is
saved in this server's database, so the TV never depends on the website.

Reads the cards on an organisation's About and Products pages.
"""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from core.sources import _get



class _Cards(HTMLParser):
    """Cards with a given class, in page order: [{"id", "icon", "title", "text", "items"}]."""

    def __init__(self, cls):
        super().__init__()
        self.cls, self.cards, self.tag, self.depth = cls, [], None, 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.depth:
            self.depth += tag == "div"
        elif tag == "div" and self.cls in (attrs.get("class") or "").split():
            self.depth = 1
            self.cards.append({"id": attrs.get("id", ""), "icon": "", "title": "", "text": "", "items": []})
        if not self.depth:
            return
        card = self.cards[-1]
        if tag == "use" and not card["icon"]:
            card["icon"] = attrs.get("href") or attrs.get("xlink:href") or ""
        if tag in ("h3", "p", "li") and not (tag == "p" and card["text"]):
            self.tag = tag
            if tag == "li":
                card["items"].append("")

    def handle_endtag(self, tag):
        if self.depth and tag == "div":
            self.depth -= 1
        if tag == self.tag:
            self.tag = None

    def handle_data(self, data):
        if self.depth and self.tag:
            card = self.cards[-1]
            if self.tag == "li":
                card["items"][-1] += data
            else:
                card["title" if self.tag == "h3" else "text"] += data


def _clean(text):
    """Drop the emoji the website puts in front of card titles; the TV draws its own."""
    text = " ".join(text.split())
    return text.split(" ", 1)[1] if text and not text[0].isalnum() and " " in text else text


def _cards(url, cls):
    parser = _Cards(cls)
    parser.feed(_get(url).decode("utf-8", "replace"))
    for c in parser.cards:
        c.update(title=_clean(c["title"]), text=_clean(c["text"]), items=[_clean(i) for i in c["items"]])
    return parser.cards


def _both(url_ar, url_en, cls):
    return _cards(url_ar, cls), _cards(url_en, cls)


def about(url_ar, url_en):
    """Vision, mission, values and objectives. Cards 1-3 are vision, mission, values; the rest are objectives."""
    ar, en = _both(url_ar, url_en, "strategy-card")
    if len(ar) < 3 or len(ar) != len(en):
        return None
    return {
        "vision": {"ar": ar[0]["text"], "en": en[0]["text"]},
        "mission": {"ar": ar[1]["text"], "en": en[1]["text"]},
        "values": [{"ar": a, "en": e} for a, e in zip(ar[2]["items"], en[2]["items"])],
        "objectives": [{"title_ar": a["title"], "title_en": e["title"], "text_ar": a["text"], "text_en": e["text"]}
                       for a, e in zip(ar[3:], en[3:])],
    }


def _icon(page_url, href, sprites):
    """The website's own icon: its symbol from the icon sprite, as a standalone SVG."""
    if "#" not in href:
        return ""
    sprite_url, name = href.rsplit("#", 1)
    sprite_url = urljoin(page_url, sprite_url)
    if sprite_url not in sprites:
        sprites[sprite_url] = _get(sprite_url).decode("utf-8", "replace")
    m = re.search(rf'<symbol id="{re.escape(name)}"([^>]*)>(.*?)</symbol>', sprites[sprite_url], re.S)
    if not m:
        return ""
    box = re.search(r'viewBox="([^"]+)"', m.group(1))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box.group(1) if box else "0 0 24 24"}">'
            f'{m.group(2)}</svg>')


def products(url_ar, url_en, hide=""):
    """Product cards in both languages, matched by their id; anything named in `hide` (id or name) is left out."""
    got = _both(url_ar, url_en, "product-card")
    ar = {c["id"]: c for c in got[0]}
    skip = {h.strip().lower() for h in hide.split(",") if h.strip()}
    out, sprites = [], {}
    for e in got[1]:
        a = ar.get(e["id"], e)
        if {e["id"].lower(), e["title"].lower(), a["title"].lower()} & skip:
            continue
        out.append({"name_ar": a["title"], "name_en": e["title"], "icon_svg": _icon(url_en, e["icon"], sprites)})
    return out
