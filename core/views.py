import io

import segno
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from audit.models import client_ip, log_event
from screens import widgets
from screens.models import ONLINE_WITHIN, AboutUs, Screen

from . import sources
from .models import DisplaySettings, NewsFeed, TickerMessage, content_version


def home(request):
    if request.user.is_authenticated:
        from desk.access import desk_user
        if desk_user(request.user) or not request.user.is_staff:
            return redirect("agent:home")
        return redirect("admin:index")
    return redirect("login")


def _qr_svg(url):
    if not url:
        return ""
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=4, border=0, xmldecl=False, svgns=True,
                                    dark="#000", light="#fff")
    return buf.getvalue().decode("utf-8")


def _config(s):
    now = timezone.now()
    ticker = TickerMessage.objects.filter(is_active=True).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now)).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
    return {
        "orgNameAr": s.org_name_ar, "orgNameEn": s.org_name_en,
        "logoUrl": s.logo.url if s.logo else "", "logoInitials": s.logo_initials,
        "logoNameAr": s.logo_name_ar, "logoNameEn": s.logo_name_en, "logoTag": s.logo_tag,
        "welcomeAr": s.welcome_ar, "welcomeEn": s.welcome_en, "welcomeSub": s.welcome_sub,
        "youtubeId": s.youtube_id,
        "showPrayer": s.show_prayer, "pauseForPrayerMin": s.pause_music_for_prayer,
        "showMarine": s.show_marine, "showNews": s.show_news,
        "marine": {"locationAr": s.location_name_ar, "locationEn": s.location_name_en,
                   "cautionWindKn": s.caution_wind_kn, "dangerWindKn": s.danger_wind_kn,
                   "cautionWaveM": float(s.caution_wave_m), "dangerWaveM": float(s.danger_wave_m),
                   "noteAr": s.sea_note_ar, "noteEn": s.sea_note_en},
        "contact": {"phone": s.phone, "mobile": s.mobile, "email": s.email, "website": s.website,
                    "address": s.address},
        "qrLabel": s.qr_label,
        "slideSeconds": max(s.slide_seconds, 2),
        "tickerLabel": s.ticker_label,
        "ticker": [t.text for t in ticker],
    }


@never_cache
def screen(request, slug):
    scr = get_object_or_404(Screen, slug=slug)
    if not scr.is_active:
        raise Http404("This screen is switched off in the admin.")
    s = DisplaySettings.load()
    return render(request, "display/screen.html", {
        "screen": scr, "config": _config(s), "qr_svg": _qr_svg(s.qr_url), "widgets": widgets.for_screen(scr),
        "content_version": content_version(), "title": s.org_name_en or s.org_name_ar,
    })


def _media(items):
    return [{"id": i.pk, "title": i.title, "url": i.file.url} for i in items]


@csrf_exempt
@require_POST
@never_cache
def screen_state(request, slug):
    """The TV calls this every few seconds: it reports what it is playing and
    gets back what it should be playing. Also marks the screen online."""
    scr = get_object_or_404(Screen, slug=slug, is_active=True)
    now = timezone.now()
    playing = (request.POST.get("now_playing") or "")[:300]
    was_offline = not scr.last_seen or now - scr.last_seen > ONLINE_WITHIN * 3
    if was_offline:
        log_event("screen_online", f"Screen “{scr.name}” is online", request=request, user="",
                  path=f"screen:{scr.slug}", offline_since=scr.last_seen)
    # Write only when something changed or every ~15 s, to spare the database.
    if was_offline or playing != scr.now_playing or now - scr.last_seen > ONLINE_WITHIN / 3:
        Screen.objects.filter(pk=scr.pk).update(last_seen=now, last_ip=client_ip(request), now_playing=playing)

    st = scr.state
    return JsonResponse({
        "version": st.version, "contentVersion": content_version(),
        "center": st.center, "video": _media(st.video_items()) if st.center == "video" else [],
        "videoMuted": st.video_muted,
        "slides": _media(st.slideshow_items()) if st.center == "slideshow" else [],
        "musicOn": st.music_on, "music": _media(st.music_items()) if st.music_on else [],
        "shuffle": st.music_shuffle, "volume": st.volume,
        "command": st.command, "commandSeq": st.command_seq,
        "occasion": _occasion(scr),
    })


def _occasion(scr):
    """The celebration running on this screen now, or None. It overrides what agents picked."""
    from screens.models import Occasion
    occ = Occasion.for_screen(scr)
    if not occ:
        return None
    return {"id": occ.pk, "name": occ.name, "theme": occ.theme, "mode": occ.mode, "fullScreen": occ.full_screen,
            "greetingAr": occ.greeting_ar, "greetingEn": occ.greeting_en,
            "videoEvery": max(occ.video_every_minutes, 1), "shuffle": occ.shuffle_songs,
            "photos": _media(occ.photo_items()) if occ.mode in ("photos_music", "mix") else [],
            "videos": _media(occ.video_items()) if occ.mode != "photos_music" else [],
            "songs": _media(occ.song_items()) if occ.mode != "video" else []}


@never_cache
@never_cache
def api_about(request):
    """The About us slides, from this server's own copy (Admin > About us)."""
    a = AboutUs.load()
    if not a.is_on:
        return JsonResponse({"about": None})
    return JsonResponse({
        "about": {
            "vision": {"ar": a.vision_ar, "en": a.vision_en},
            "mission": {"ar": a.mission_ar, "en": a.mission_en},
            "values": [{"ar": v.text_ar, "en": v.text_en} for v in a.values.all()],
            "objectives": [{"title_ar": o.title_ar, "title_en": o.title_en, "text_ar": o.text_ar, "text_en": o.text_en}
                           for o in a.objectives.all()],
        },
        "products": [{"nameAr": p.name_ar, "nameEn": p.name_en, "iconUrl": p.icon_url()}
                     for p in a.products.filter(show=True)],
        "productsQr": _qr_svg(a.products_url) if a.products_url else "",
    })


def api_weather(request):
    return JsonResponse(sources.weather(DisplaySettings.load()))


@never_cache
def api_prayer(request):
    s = DisplaySettings.load()
    return JsonResponse(sources.prayer(s) or {} if s.show_prayer else {})


@never_cache
def api_news(request):
    s = DisplaySettings.load()
    if not s.show_news:
        return JsonResponse({"label": "", "items": []})
    return JsonResponse(sources.news(NewsFeed.objects.filter(is_active=True, language="en")))


@never_cache
def api_news_ar(request):
    """Arabic headlines for the picker panel under the prayer times."""
    return JsonResponse(sources.news(NewsFeed.objects.filter(is_active=True, language="ar")))


def healthz(request):
    return JsonResponse({"ok": True})
