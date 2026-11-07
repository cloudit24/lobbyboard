from django.conf import settings
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


class VisitPurpose(models.Model):
    """Reasons for a visit, shown as choices at check-in. Edited in the admin."""
    name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField("In use", default=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Visit purpose"

    def __str__(self):
        return self.name


class Visit(models.Model):
    """One person's visit: checked in at the desk, checked out when they leave."""

    name = models.CharField("Visitor name", max_length=150)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    company = models.CharField("Company / from", max_length=150, blank=True)
    id_number = models.CharField("ID / Emirates ID / passport", max_length=60, blank=True,
                                 help_text="Only if your policy requires it.")
    purpose = models.ForeignKey(VisitPurpose, null=True, blank=True, on_delete=models.SET_NULL)
    meeting_with = models.CharField("Here to see", max_length=150, blank=True)
    badge = models.CharField("Badge / card no.", max_length=30, blank=True)
    people_count = models.PositiveSmallIntegerField("Number of people", default=1)
    notes = models.TextField(blank=True)
    checked_in_at = models.DateTimeField(default=timezone.now, db_index=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="visits_registered", editable=False)
    checked_out_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name="+", editable=False)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-checked_in_at"]
        permissions = [("register_visitor", "Can check visitors in and out at the desk")]

    def __str__(self):
        return f"{self.name} ({timezone.localtime(self.checked_in_at):%d %b %H:%M})"

    @property
    def is_inside(self):
        return self.checked_out_at is None

    @property
    def duration(self):
        end = self.checked_out_at or timezone.now()
        mins = int((end - self.checked_in_at).total_seconds() // 60)
        return f"{mins // 60} h {mins % 60} min" if mins >= 60 else f"{mins} min"
