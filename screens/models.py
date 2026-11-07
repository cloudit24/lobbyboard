import base64
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from library.models import MediaItem, Playlist

ONLINE_WITHIN = timedelta(seconds=45)


class Screen(models.Model):
    """One TV. Open its address on the TV's browser; agents control it from
    the agent panel."""

    name = models.CharField(max_length=100, help_text="e.g. Reception - main hall")
    slug = models.SlugField("Short name in the address", unique=True,
                            help_text="The TV opens /screen/<this>/ - letters, numbers and dashes only.")
    agents = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="screens",
                                    help_text="Who may control this TV. Nobody ticked = every agent may.")
    is_active = models.BooleanField("In use", default=True)
    notes = models.CharField(max_length=200, blank=True)
    background = models.ForeignKey(
        "library.MediaItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        limit_choices_to={"status": "approved", "kind__in": ["image", "video"]},
        help_text="A photo or video behind everything. Empty = the animated colour background.")
    background_dim = models.PositiveSmallIntegerField(
        "Darken the background (%)", default=40, help_text="0 = as it is, 90 = almost black. Keeps text readable.")
    layout = models.JSONField(default=list, blank=True, editable=False,
                              help_text="Where each widget sits. Set it with the layout designer; empty = the standard layout.")
    last_seen = models.DateTimeField(null=True, blank=True, editable=False)
    last_ip = models.GenericIPAddressField(null=True, blank=True, editable=False)
    now_playing = models.CharField(max_length=300, blank=True, editable=False)
    history = HistoricalRecords(excluded_fields=["last_seen", "last_ip", "now_playing"])

    class Meta:
        ordering = ["name"]
        permissions = [("control_screen", "Can control screens from the agent panel")]

    def __str__(self):
        return self.name

    @property
    def is_online(self):
        return bool(self.last_seen and timezone.now() - self.last_seen < ONLINE_WITHIN)

    def agent_can_control(self, user):
        if not user.is_authenticated or not self.is_active:
            return False
        if user.is_superuser:
            return True
        if not user.has_perm("screens.control_screen"):
            return False
        return not self.agents.exists() or self.agents.filter(pk=user.pk).exists()

    @classmethod
    def for_agent(cls, user):
        return [s for s in cls.objects.filter(is_active=True).prefetch_related("agents") if s.agent_can_control(user)]

    @property
    def state(self):
        return ScreenState.objects.get_or_create(screen=self)[0]


class ScreenState(models.Model):
    """What a screen is playing right now. Changed by agents; every change is
    written to the log. Not kept in history (the log already has it)."""

    CENTER_CHOICES = [("welcome", "Welcome screen"), ("slideshow", "Photo slideshow"),
                      ("video", "Video"), ("youtube", "YouTube")]

    screen = models.OneToOneField(Screen, on_delete=models.CASCADE, related_name="playback")
    center = models.CharField(max_length=10, choices=CENTER_CHOICES, default="welcome")
    video_item = models.ForeignKey(MediaItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    video_playlist = models.ForeignKey(Playlist, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    video_muted = models.BooleanField(default=False)
    slideshow_playlist = models.ForeignKey(Playlist, null=True, blank=True, on_delete=models.SET_NULL,
                                           related_name="+", help_text="Blank = all approved photos.")
    music_item = models.ForeignKey(MediaItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    music_playlist = models.ForeignKey(Playlist, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    music_on = models.BooleanField(default=False)
    music_shuffle = models.BooleanField(default=False)
    volume = models.PositiveSmallIntegerField(default=60)
    # "next" / "restart" are one-off commands: the screen acts once per new number.
    command = models.CharField(max_length=20, blank=True)
    command_seq = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=0)
    # Announcement from reception ("On a short break"): covers the whole screen until switched off.
    NOTICE_ANIMS = [("rise", "Rise in"), ("fade", "Fade"), ("pulse", "Gentle pulse"), ("zoom", "Zoom"),
                    ("slide", "Slide across"), ("none", "No movement")]
    notice_on = models.BooleanField(default=False)
    notice_text = models.CharField(max_length=200, blank=True)
    notice_sub = models.CharField(max_length=300, blank=True)
    notice_anim = models.CharField(max_length=10, choices=NOTICE_ANIMS, default="rise")
    notice_color = models.CharField(max_length=7, default="#0b2233")
    notice_bg = models.ForeignKey(MediaItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    notice_until = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Playback on {self.screen}"

    def save(self, *args, **kwargs):
        self.version += 1
        super().save(*args, **kwargs)

    # -- what the screen should play, resolved to approved files only --
    def video_items(self):
        if self.video_playlist_id:
            return self.video_playlist.playable_items()
        if self.video_item_id and self.video_item.status == "approved":
            return [self.video_item]
        return []

    def slideshow_items(self):
        if self.slideshow_playlist_id:
            return self.slideshow_playlist.playable_items()
        return list(MediaItem.objects.filter(kind="image", status="approved"))

    def music_items(self):
        if self.music_playlist_id:
            return self.music_playlist.playable_items()
        if self.music_item_id and self.music_item.status == "approved":
            return [self.music_item]
        return []

    def describe(self):
        """One line for logs and the agent panel."""
        parts = [dict(self.CENTER_CHOICES)[self.center]]
        if self.center == "video":
            src = self.video_playlist or self.video_item
            parts[0] += f": {src}" if src else " (nothing chosen)"
            if self.video_muted:
                parts[0] += " (muted)"
        if self.music_on:
            src = self.music_playlist or self.music_item
            parts.append(f"Music: {src}" if src else "Music: nothing chosen")
        parts.append(f"Volume {self.volume}%")
        return " · ".join(parts)


class Occasion(models.Model):
    """A celebration - National Day, Eid, an anniversary. Set up once by an
    admin; it starts and stops on its dates, or an agent presses Play now.
    While it runs it takes over what the screen plays and adds its greeting
    and festive look. Prayer pauses still apply."""

    THEMES = [("national", "National day - fireworks in flag colours"),
              ("eid", "Eid - lanterns, crescent and stars"),
              ("celebration", "Celebration - confetti"),
              ("none", "No effects - greeting only")]
    MODES = [("photos_music", "Photos with songs"),
             ("video", "Videos with their own sound"),
             ("video_music", "Videos without sound, with songs"),
             ("mix", "Photos with songs, and a video with its sound every few minutes")]

    name = models.CharField(max_length=100, help_text="For you, e.g. National Day 2026.")
    greeting_ar = models.CharField("Greeting (Arabic)", max_length=120, blank=True)
    greeting_en = models.CharField("Greeting (English)", max_length=120, blank=True)
    theme = models.CharField(max_length=12, choices=THEMES, default="celebration")
    mode = models.CharField("What plays", max_length=12, choices=MODES, default="photos_music")
    photos = models.ForeignKey(Playlist, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                               limit_choices_to={"kind": "image"}, verbose_name="Photo list",
                               help_text="Blank = all approved photos.")
    videos = models.ForeignKey(Playlist, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                               limit_choices_to={"kind": "video"}, verbose_name="Video list")
    songs = models.ForeignKey(Playlist, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                              limit_choices_to={"kind": "audio"}, verbose_name="Song list")
    shuffle_songs = models.BooleanField(default=True)
    video_every_minutes = models.PositiveSmallIntegerField(
        "Video every (minutes)", default=10, help_text="Only for the mixed mode.")
    full_screen = models.BooleanField(
        default=True, help_text="Media fills the TV; the clock, name and ticker stay. Off = media in its usual panel.")
    screens = models.ManyToManyField(Screen, blank=True, related_name="occasions",
                                     help_text="Blank = every screen.")
    starts_at = models.DateTimeField("Starts", null=True, blank=True,
                                     help_text="Blank start and end = only when an agent presses Play now.")
    ends_at = models.DateTimeField("Ends", null=True, blank=True)
    is_on = models.BooleanField("Playing now (pressed by an agent)", default=False)
    stopped_at = models.DateTimeField(null=True, blank=True, editable=False)
    is_active = models.BooleanField("Allowed to run", default=True)
    history = HistoricalRecords(excluded_fields=["stopped_at"])

    class Meta:
        ordering = ["-starts_at", "name"]

    def __str__(self):
        return self.name

    def scheduled_now(self, now=None):
        now = now or timezone.now()
        if not (self.starts_at and self.ends_at and self.starts_at <= now < self.ends_at):
            return False
        # An agent pressed Stop during this run: stays stopped until the next run.
        return not (self.stopped_at and self.stopped_at >= self.starts_at)

    def running(self, now=None):
        return self.is_active and (self.is_on or self.scheduled_now(now))

    @classmethod
    def for_screen(cls, screen, now=None):
        """The occasion this screen should show now, if any (Play now wins over a schedule)."""
        now = now or timezone.now()
        candidates = cls.objects.filter(is_active=True).filter(
            models.Q(screens=screen) | models.Q(screens__isnull=True)).distinct()
        running = [o for o in candidates if o.running(now)]
        running.sort(key=lambda o: (not o.is_on, o.starts_at or now))
        return running[0] if running else None

    def photo_items(self):
        if self.photos_id:
            return self.photos.playable_items()
        return list(MediaItem.objects.filter(kind="image", status="approved"))

    def video_items(self):
        return self.videos.playable_items() if self.videos_id else []

    def song_items(self):
        return self.songs.playable_items() if self.songs_id else []


class AboutUs(models.Model):
    """The About us slides in the TV's news panel: a welcome, vision, mission,
    values, each objective, then the products. Kept here so the TV stands on its
    own. Fill it in the admin, or copy it once from your website with
    `manage.py copy_about`."""

    is_on = models.BooleanField("Show About us on the TV", default=False,
                                help_text="On: the news panel shows these slides; outside news stays in the ticker.")
    vision_ar = models.TextField("Vision (Arabic)", blank=True)
    vision_en = models.TextField("Vision (English)", blank=True)
    mission_ar = models.TextField("Mission (Arabic)", blank=True)
    mission_en = models.TextField("Mission (English)", blank=True)
    products_url = models.URLField("Products page address", blank=True,
                                   help_text="Visitors' phones open this from the QR code on the products slide.")
    history = HistoricalRecords()

    class Meta:
        verbose_name = verbose_name_plural = "About us"

    def __str__(self):
        return "About us"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]


class AboutValue(models.Model):
    about = models.ForeignKey(AboutUs, on_delete=models.CASCADE, related_name="values")
    text_ar = models.CharField("Arabic", max_length=200)
    text_en = models.CharField("English", max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "value"

    def __str__(self):
        return self.text_en


class AboutObjective(models.Model):
    about = models.ForeignKey(AboutUs, on_delete=models.CASCADE, related_name="objectives")
    title_ar = models.CharField("Title (Arabic)", max_length=200)
    title_en = models.CharField("Title (English)", max_length=200)
    text_ar = models.TextField("Text (Arabic)", blank=True)
    text_en = models.TextField("Text (English)", blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "strategic objective"

    def __str__(self):
        return self.title_en


class AboutProduct(models.Model):
    about = models.ForeignKey(AboutUs, on_delete=models.CASCADE, related_name="products")
    name_ar = models.CharField("Name (Arabic)", max_length=120)
    name_en = models.CharField("Name (English)", max_length=120)
    icon_svg = models.TextField("Icon (SVG)", blank=True,
                                help_text="SVG code. Shown as a picture, so nothing in it can run on the TV.")
    show = models.BooleanField("Show on the TV", default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "product"

    def __str__(self):
        return self.name_en

    def icon_url(self, colour="#22d3ee"):
        """The icon as a picture address (data: URL). Its lines take the About panel's colour."""
        if not self.icon_svg.strip().startswith("<svg"):
            return ""
        svg = self.icon_svg.replace("currentColor", colour)
        return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
