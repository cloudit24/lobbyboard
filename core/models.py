import json

from django.core.cache import cache
from django.db import models
from simple_history.models import HistoricalRecords

PRAYER_METHODS = [
    (8, "Gulf Region"), (4, "Umm Al-Qura, Makkah"), (16, "Dubai (unofficial)"), (9, "Kuwait"),
    (10, "Qatar"), (3, "Muslim World League"), (5, "Egyptian General Authority"),
    (1, "University of Islamic Sciences, Karachi"), (2, "ISNA (North America)"),
    (13, "Diyanet, Turkey"), (12, "UOIF, France"), (11, "MUIS, Singapore"),
]


def bump_content_version():
    """Open screens reload their settings when this number changes."""
    try:
        cache.incr("content_version")
    except ValueError:
        cache.set("content_version", 1, None)


def content_version():
    return cache.get_or_set("content_version", 1, None)


class DisplaySettings(models.Model):
    """Everything the TV shows that is not media: names, logo, welcome text,
    location, sea limits, contact details. One row (pk=1), edited in the admin."""

    # Identity - top bar
    org_name_ar = models.CharField("Organisation name (Arabic)", max_length=200, blank=True,
                                   default="اسم المنظمة", help_text="Big gold name in the middle of the top bar.")
    org_name_en = models.CharField("Organisation name (English)", max_length=200, blank=True,
                                   default="Your Organisation", help_text="Shown under the Arabic name, in capitals.")
    logo = models.ImageField("Logo", upload_to="branding/", blank=True, null=True,
                             help_text="Round badge, top left. Square images look best. Blank shows the initials.")
    logo_initials = models.CharField("Initials (when there is no logo)", max_length=6, blank=True, default="RT")
    logo_name_ar = models.CharField("Name next to the logo (Arabic)", max_length=100, blank=True, default="المنظمة")
    logo_name_en = models.CharField("Name next to the logo (English)", max_length=100, blank=True, default="Organisation")
    logo_tag = models.CharField("Line under the logo name", max_length=100, blank=True, default="الاستقبال · Reception")

    # Welcome screen (centre, when nothing else is playing)
    welcome_ar = models.CharField("Welcome (Arabic)", max_length=100, blank=True, default="أهلاً وسهلاً")
    welcome_en = models.CharField("Welcome (English)", max_length=100, blank=True, default="Welcome")
    welcome_sub = models.CharField("Line under the welcome", max_length=200, blank=True,
                                   default="يسعدنا تواجدكم معنا · We are glad to have you here")
    youtube_id = models.CharField("YouTube video ID", max_length=20, blank=True,
                                  help_text="Optional. Agents can switch the centre to this video. "
                                            "The ID is the part after watch?v= in the link.")

    # Prayer times
    show_prayer = models.BooleanField("Show prayer times", default=True)
    city = models.CharField("City", max_length=100, default="Dubai")
    country = models.CharField("Country code", max_length=2, default="AE", help_text="Two letters, e.g. AE, SA, QA.")
    prayer_method = models.PositiveSmallIntegerField("Calculation method", choices=PRAYER_METHODS, default=8)
    pause_music_for_prayer = models.PositiveSmallIntegerField(
        "Pause music at prayer time (minutes)", default=0,
        help_text="Music and video sound stop for this many minutes from each prayer time. 0 = never.")

    # Sea & weather
    show_marine = models.BooleanField("Show sea conditions", default=True)
    sea_latitude = models.DecimalField("Latitude", max_digits=7, decimal_places=4, default=25.3000,
                                       help_text="A point at sea, not on land - wave data needs water.")
    sea_longitude = models.DecimalField("Longitude", max_digits=7, decimal_places=4, default=55.2800)
    location_name_ar = models.CharField("Place name (Arabic)", max_length=100, blank=True, default="الساحل")
    location_name_en = models.CharField("Place name (English)", max_length=100, blank=True, default="Coast")
    caution_wind_kn = models.PositiveSmallIntegerField("Take care from wind (knots)", default=15)
    danger_wind_kn = models.PositiveSmallIntegerField("Dangerous from wind (knots)", default=25)
    caution_wave_m = models.DecimalField("Take care from waves (metres)", max_digits=4, decimal_places=1, default=1.0)
    danger_wave_m = models.DecimalField("Dangerous from waves (metres)", max_digits=4, decimal_places=1, default=2.0)
    sea_note_ar = models.CharField("Sea note (Arabic)", max_length=200, blank=True,
                                   default="تقديرية · تأكد من النشرة الرسمية قبل الإبحار")
    sea_note_en = models.CharField("Sea note (English)", max_length=200, blank=True,
                                   default="Estimates - check the official bulletin before sailing")

    # Contact
    phone = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)
    email = models.CharField(max_length=100, blank=True)
    website = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=200, blank=True)
    qr_url = models.URLField("QR code link", blank=True, help_text="Where the QR code takes a phone. Blank hides it.")
    qr_label = models.CharField("Under the QR code", max_length=100, blank=True, default="امسح للزيارة · Scan to visit")

    # Behaviour
    slide_seconds = models.PositiveSmallIntegerField("Seconds per photo", default=8)
    show_news = models.BooleanField("Show news headlines", default=True)
    ticker_label = models.CharField("Ticker label", max_length=30, blank=True, default="Live news")
    log_retention_days = models.PositiveIntegerField(
        "Keep logs for (days)", default=180, help_text="Older log rows are deleted by the nightly clean-up. 0 = keep forever.")

    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = verbose_name_plural = "Display settings"

    def __str__(self):
        return "Display settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        bump_content_version()

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class NewsFeed(models.Model):
    """An RSS feed for the news box and ticker. Tried in order; the first
    one that answers is shown."""

    label = models.CharField(max_length=60, help_text="Shown above each headline.")
    url = models.URLField("RSS address", max_length=500)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField("In use", default=True)
    language = models.CharField(max_length=2, choices=[("en", "English"), ("ar", "Arabic")], default="en",
                                help_text="Arabic feeds fill the Arabic headlines panel under the prayer times.")
    history = HistoricalRecords()

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "News feed"

    def __str__(self):
        return self.label

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        bump_content_version()


class TickerMessage(models.Model):
    """Your own announcement in the scrolling bar at the bottom, shown before
    the news headlines."""

    text = models.CharField(max_length=300)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField("Show", default=True)
    starts_at = models.DateTimeField("Show from", blank=True, null=True, help_text="Blank = straight away.")
    ends_at = models.DateTimeField("Show until", blank=True, null=True, help_text="Blank = until switched off.")
    history = HistoricalRecords()

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Ticker message"

    def __str__(self):
        return self.text[:60]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        bump_content_version()


class Singleton(models.Model):
    """One row (pk=1), edited in the admin."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]


class ThemeSettings(Singleton):
    """The look of the desk dashboard (agents, secretaries). Neutral out of the
    box; set your organisation's colours, font and name here."""

    brand_name = models.CharField("Name in the dashboard header", max_length=100, blank=True,
                                  help_text="Blank = the organisation name from Display settings.")
    primary = models.CharField("Main colour", max_length=7, default="#334155", help_text="Header, buttons, links.")
    primary_dark = models.CharField("Main colour, dark", max_length=7, default="#1e293b", help_text="Headings, hover.")
    secondary = models.CharField("Accent colour", max_length=7, default="#b08d3c", help_text="Highlights, current tab.")
    background = models.CharField("Page background", max_length=7, default="#f5f7fa")
    font_family = models.CharField(
        "Font", max_length=60, blank=True,
        help_text="A Google Fonts name, e.g. Cairo or Inter. Blank = the computer's normal font.")
    history = HistoricalRecords()

    class Meta:
        verbose_name = verbose_name_plural = "Dashboard theme"

    def __str__(self):
        return "Dashboard theme"


class NetworkSettings(Singleton):
    """How people reach the app: on the office network (local IP) and from
    outside through a Cloudflare Tunnel."""

    port = models.PositiveIntegerField(
        "Port on the server", default=8080,
        help_text="Changing it needs one restart on the server: run scripts/apply-network (see the note on this page).")
    lan_addresses = models.TextField(
        "Local addresses", blank=True,
        help_text="The server's IP addresses or names on the office network, one per line, e.g. 192.168.1.20")
    public_hostnames = models.TextField(
        "Tunnel / public addresses", blank=True,
        help_text="Names that reach this app from outside (e.g. desk.example.com via Cloudflare Tunnel), one per line.")
    history = HistoricalRecords()

    class Meta:
        verbose_name = verbose_name_plural = "Network settings"

    def __str__(self):
        return "Network settings"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.conf import settings as dj
        from .network import forget
        forget()
        # scripts/apply-network reads this to change the port on the server.
        (dj.DATA_DIR / "network.json").write_text(json.dumps({"port": self.port}), encoding="utf-8")

    def lan_list(self):
        return [x.strip() for x in self.lan_addresses.splitlines() if x.strip()]

    def public_list(self):
        return [x.strip().removeprefix("https://").removeprefix("http://").strip("/")
                for x in self.public_hostnames.splitlines() if x.strip()]
