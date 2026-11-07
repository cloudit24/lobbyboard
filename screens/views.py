import os

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.models import log_event
from desk.access import needs
from core.models import DisplaySettings
from library.models import ALL_EXTENSIONS, MediaItem, Playlist, kind_for

from .models import Occasion, Screen


def _ctx(request, **extra):
    return extra


@needs("tv")
def home(request):
    screens = Screen.for_agent(request.user)
    if len(screens) == 1 and not request.GET.get("all"):
        return redirect("agent:screen", slug=screens[0].slug)
    return render(request, "agent/home.html", _ctx(request, title="TVs", screens=screens))


def _choices(kind):
    items = MediaItem.objects.filter(kind=kind, status="approved")
    lists = Playlist.objects.filter(kind=kind, is_active=True)
    return {"items": items, "playlists": lists}


def _pick(value, kind):
    """'item:5' / 'playlist:3' -> (item, playlist), approved/active only."""
    try:
        what, pk = (value or "").split(":", 1)
        pk = int(pk)
    except ValueError:
        return None, None
    if what == "item":
        return MediaItem.objects.filter(pk=pk, kind=kind, status="approved").first(), None
    if what == "playlist":
        return None, Playlist.objects.filter(pk=pk, kind=kind, is_active=True).first()
    return None, None


@needs("tv")
def screen(request, slug):
    scr = get_object_or_404(Screen, slug=slug)
    if not scr.agent_can_control(request.user):
        raise PermissionDenied("You are not allowed to control this screen.")
    st = scr.state

    if request.method == "POST":
        action = request.POST.get("action", "")
        before = st.describe()
        msg = _apply(action, request.POST, st)
        if msg is None:
            messages.error(request, "Choose something to play first.")
        else:
            st.updated_by = request.user
            st.save()
            log_event("agent_action", f"{scr.name}: {msg}", request=request, path=f"screen:{scr.slug}",
                      action=action, before=before, after=st.describe())
            messages.success(request, msg)
        return redirect("agent:screen", slug=scr.slug)

    def current(item, playlist):
        return f"playlist:{playlist.pk}" if playlist else f"item:{item.pk}" if item else ""

    return render(request, "agent/screen.html", _ctx(
        request, title=scr.name, screen=scr, st=st,
        videos=_choices("video"), music=_choices("audio"), photo_lists=_choices("image")["playlists"],
        photo_count=MediaItem.objects.filter(kind="image", status="approved").count(),
        current_video=current(st.video_item, st.video_playlist),
        current_music=current(st.music_item, st.music_playlist),
        youtube=bool(DisplaySettings.load().youtube_id),
        screens=Screen.for_agent(request.user),
        occasions=[(o, o.running()) for o in Occasion.objects.filter(is_active=True).filter(
            Q(screens=scr) | Q(screens__isnull=True)).distinct()],
    ))


def _apply(action, data, st):
    """Change the playback state. Returns a plain-English line for the log,
    or None when the request made no sense (nothing chosen)."""
    if action == "welcome":
        st.center = "welcome"
        return "Showing the welcome screen"
    if action == "slideshow":
        pl = Playlist.objects.filter(pk=data.get("playlist") or 0, kind="image", is_active=True).first()
        st.center, st.slideshow_playlist = "slideshow", pl
        return f"Showing photos: {pl.name if pl else 'all approved photos'}"
    if action == "video":
        item, pl = _pick(data.get("source"), "video")
        if not (item or pl):
            return None
        st.center, st.video_item, st.video_playlist = "video", item, pl
        st.video_muted = data.get("muted") == "1"
        st.command, st.command_seq = "restart", st.command_seq + 1
        return f"Playing video: {pl or item}" + (" (muted)" if st.video_muted else "")
    if action == "youtube":
        st.center = "youtube"
        return "Showing the YouTube video"
    if action == "video_mute":
        st.video_muted = not st.video_muted
        return "Video sound off" if st.video_muted else "Video sound on"
    if action == "video_next":
        st.command, st.command_seq = "next_video", st.command_seq + 1
        return "Next video"
    if action == "music_play":
        item, pl = _pick(data.get("source"), "audio")
        if not (item or pl):
            return None
        st.music_item, st.music_playlist, st.music_on = item, pl, True
        st.music_shuffle = data.get("shuffle") == "1"
        st.command, st.command_seq = "restart", st.command_seq + 1
        return f"Playing music: {pl or item}" + (" (shuffle)" if st.music_shuffle else "")
    if action == "music_stop":
        st.music_on = False
        return "Music stopped"
    if action == "music_next":
        st.command, st.command_seq = "next_music", st.command_seq + 1
        return "Next song"
    if action == "volume":
        try:
            st.volume = max(0, min(100, int(data.get("volume", st.volume))))
        except ValueError:
            return None
        return f"Volume {st.volume}%"
    if action in ("occasion_play", "occasion_stop"):
        occ = Occasion.objects.filter(pk=data.get("occasion") or 0, is_active=True).first()
        if not occ:
            return None
        if action == "occasion_play":
            occ.is_on, occ.stopped_at = True, None
            occ.save()
            return f"Started the occasion: {occ.name}"
        occ.is_on, occ.stopped_at = False, timezone.now()
        occ.save()
        return f"Stopped the occasion: {occ.name}"
    if action == "reload":
        st.command, st.command_seq = "reload", st.command_seq + 1
        return "Screen reloaded"
    return None


@needs("tv")
def screen_status(request, slug):
    scr = get_object_or_404(Screen, slug=slug)
    if not scr.agent_can_control(request.user):
        raise Http404
    return JsonResponse({
        "online": scr.is_online, "now_playing": scr.now_playing,
        "last_seen": timezone.localtime(scr.last_seen).strftime("%d %b %H:%M:%S") if scr.last_seen else None,
        "state": scr.state.describe(),
    })


@needs("upload")
def upload(request):
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024

    if request.method == "POST":
        files = request.FILES.getlist("files")
        title = request.POST.get("title", "").strip()
        added, refused = 0, []
        for f in files:
            kind = kind_for(f.name)
            if not kind:
                refused.append(f"{f.name} (this file type can't be played)")
                continue
            if f.size > limit:
                refused.append(f"{f.name} (bigger than {settings.MAX_UPLOAD_MB} MB)")
                continue
            auto = request.user.is_staff and request.user.has_perm("library.change_mediaitem")
            item = MediaItem(title=(title if len(files) == 1 and title else os.path.splitext(f.name)[0])[:200],
                             file=f, kind=kind, uploaded_by=request.user,
                             status="approved" if auto else "pending")
            if auto:
                item.reviewed_by, item.reviewed_at = request.user, timezone.now()
            item.save()
            log_event("upload", f"Uploaded {item.get_kind_display().lower()} “{item.title}” "
                                f"({'approved - uploaded by an admin' if auto else 'waiting for review'})",
                      request=request, path=f"library.MediaItem#{item.pk}", size=item.size, file=item.file.name)
            added += 1
        if added:
            messages.success(request, f"{added} file(s) uploaded." +
                             ("" if request.user.is_staff else " An admin will review them before they can be played."))
        for r in refused:
            messages.error(request, f"Not uploaded: {r}")
        return redirect("agent:upload")

    mine = MediaItem.objects.filter(uploaded_by=request.user).order_by("-uploaded_at")[:100]
    return render(request, "agent/upload.html", _ctx(
        request, title="Upload files", mine=mine, accept=",".join(ALL_EXTENSIONS),
        max_mb=settings.MAX_UPLOAD_MB, screens=Screen.for_agent(request.user)))


@require_POST
@needs("upload")
def delete_upload(request, pk):
    """An agent may take back their own upload while it is still waiting."""
    item = get_object_or_404(MediaItem, pk=pk, uploaded_by=request.user, status="pending")
    name = item.title
    item.file.delete(save=False)
    item.delete()
    log_event("upload", f"Withdrew upload “{name}” before review", request=request)
    messages.success(request, f"“{name}” removed.")
    return redirect("agent:upload")
