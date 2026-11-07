import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

# Formats every current TV browser plays without plugins.
EXTENSIONS = {
    "video": {".mp4", ".webm", ".m4v"},
    "audio": {".mp3", ".m4a", ".aac", ".ogg", ".oga", ".wav", ".opus"},
    "image": {".jpg", ".jpeg", ".png", ".webp", ".gif"},
}
ALL_EXTENSIONS = sorted(set().union(*EXTENSIONS.values()))


def kind_for(filename):
    ext = os.path.splitext(filename)[1].lower()
    return next((k for k, exts in EXTENSIONS.items() if ext in exts), None)


def upload_path(instance, filename):
    return f"library/{instance.kind or 'other'}/{filename}"


class MediaItem(models.Model):
    """One video, music track or photo. Agents upload (status Waiting); an
    admin approves it before it can be played."""

    KIND_CHOICES = [("video", "Video"), ("audio", "Music"), ("image", "Photo")]
    STATUS_CHOICES = [("pending", "Waiting for review"), ("approved", "Approved"), ("rejected", "Rejected")]

    title = models.CharField(max_length=200)
    file = models.FileField(upload_to=upload_path, max_length=300)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, editable=False)
    size = models.PositiveBigIntegerField("Size (bytes)", default=0, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", db_index=True)
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers come first in lists.")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="uploads", editable=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="reviews", editable=False)
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    review_note = models.CharField("Note to the uploader", max_length=300, blank=True,
                                   help_text="Optional - e.g. why it was rejected. The agent sees it.")
    history = HistoricalRecords()

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "Media file"
        permissions = [("upload_media", "Can upload media from the agent panel")]

    def __str__(self):
        return self.title

    def clean(self):
        if self.file and not kind_for(self.file.name):
            raise ValidationError({"file": "This file type can't be played. Use: " + ", ".join(ALL_EXTENSIONS)})

    def save(self, *args, **kwargs):
        if self.file:
            self.kind = kind_for(self.file.name) or self.kind
            try:
                self.size = self.file.size
            except (OSError, ValueError):
                pass
        super().save(*args, **kwargs)

    @property
    def is_playable(self):
        return self.status == "approved"


class Playlist(models.Model):
    """An ordered list the admin builds from approved files. Agents pick a
    playlist (or a single file) to play."""

    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=MediaItem.KIND_CHOICES,
                            help_text="Videos, music or photos (slideshow). One kind per list.")
    description = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField("Agents can use it", default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["kind", "order", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"

    def playable_items(self):
        return [pi.item for pi in self.entries.select_related("item").order_by("order", "id")
                if pi.item.status == "approved"]


class PlaylistItem(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="entries")
    item = models.ForeignKey(MediaItem, on_delete=models.CASCADE, related_name="in_playlists",
                             limit_choices_to={"status": "approved"})
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "File in this list"
        verbose_name_plural = "Files in this list (in playing order)"

    def __str__(self):
        return f"{self.playlist.name}: {self.item.title}"

    def clean(self):
        if self.item_id and self.playlist_id and self.item.kind != self.playlist.kind:
            raise ValidationError(f"“{self.item}” is a {self.item.get_kind_display().lower()}; "
                                  f"this list is for {self.playlist.get_kind_display().lower()}s.")
