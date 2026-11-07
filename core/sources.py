"""Outside data the screen shows, fetched by the server (never by the TV) and
cached, so ten screens cost one request. Every source is free and needs no
account:

  - Open-Meteo  api.open-meteo.com         wind, air, sky, sunrise/sunset
  - Open-Meteo  marine-api.open-meteo.com  waves, swell, sea temperature
  - AlAdhan     api.aladhan.com            prayer times + Hijri date
  - RSS feeds   set in the admin           news headlines

If a source is down the last good answer is kept a while longer and the
screen shows what it has - it never hangs (8 s timeout).
"""
import json
import logging
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from django.core.cache import cache
from django.utils import timezone

log = logging.getLogger(__name__)
TIMEOUT = 8
UA = {"User-Agent": "FrontDesk/1.0 (+https://github.com/)"}


def _get(url, params=None):
    full = f"{url}?{urlencode(params)}" if params else url
    req = urllib.request.Request(full, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _cached(key, ttl, fetch):
    """Fresh value for `ttl` seconds; on failure serve the last good value
    (kept 24 h) instead of nothing."""
    fresh = cache.get(key)
    if fresh is not None:
        return fresh
    try:
        value = fetch()
    except Exception as exc:
        log.warning("Source %s unavailable: %s", key, exc)
        return cache.get(key + ":stale")
    cache.set(key, value, ttl)
    cache.set(key + ":stale", value, 24 * 3600)
    return value


def weather(s):
    common = {"latitude": s.sea_latitude, "longitude": s.sea_longitude,
              "timezone": "auto", "forecast_days": 3}
    key = f"wx2:{s.sea_latitude}:{s.sea_longitude}"

    def fetch_wx():
        return json.loads(_get("https://api.open-meteo.com/v1/forecast", dict(
            common, wind_speed_unit="kn",
            current="temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,"
                    "wind_gusts_10m,weather_code,visibility,uv_index",
            daily="sunrise,sunset,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,"
                  "temperature_2m_max,temperature_2m_min,weather_code",
            hourly="wind_speed_10m,wind_gusts_10m")))

    def fetch_sea():
        return json.loads(_get("https://marine-api.open-meteo.com/v1/marine", dict(
            common,
            current="wave_height,wave_direction,wave_period,swell_wave_height,swell_wave_direction,"
                    "sea_surface_temperature",
            daily="wave_height_max,wave_direction_dominant,wave_period_max",
            hourly="wave_height")))

    return {"weather": _cached(key, 15 * 60, fetch_wx),
            "marine": _cached("sea:" + key, 15 * 60, fetch_sea) if s.show_marine else None,
            "fetched_at": timezone.now().isoformat()}


def prayer(s):
    today = timezone.localdate().strftime("%d-%m-%Y")
    key = f"prayer:{today}:{s.city}:{s.country}:{s.prayer_method}"

    def fetch():
        data = json.loads(_get(f"https://api.aladhan.com/v1/timingsByCity/{today}",
                               {"city": s.city, "country": s.country, "method": s.prayer_method}))
        if data.get("code") != 200:
            raise ValueError(data.get("status"))
        return {"timings": data["data"]["timings"], "date": data["data"]["date"]}

    return _cached(key, 6 * 3600, fetch)


def _rss_items(raw):
    root = ET.fromstring(raw)
    items = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag in ("item", "entry"):
            title = next((c.text for c in node if c.tag.rsplit("}", 1)[-1] == "title" and c.text), "")
            if title.strip():
                items.append({"title": " ".join(title.split())})
        if len(items) >= 12:
            break
    return items


def news(feeds):
    """First feed (in admin order) that answers with headlines."""
    for feed in feeds:
        def fetch(url=feed.url):
            items = _rss_items(_get(url))
            if not items:
                raise ValueError("no items")
            return items

        items = _cached(f"news:{feed.pk}:{feed.url}", 10 * 60, fetch)
        if items:
            return {"label": feed.label, "items": items}
    return {"label": "", "items": []}

