from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from audit.models import AuditLog
from core.models import DisplaySettings


class Command(BaseCommand):
    help = "Delete log rows older than Display settings > Keep logs for (days). Run nightly."

    def handle(self, *args, **options):
        days = DisplaySettings.load().log_retention_days
        if not days:
            self.stdout.write("Log retention is 0 (keep forever) - nothing deleted.")
            return
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = AuditLog.objects.filter(timestamp__lt=cutoff).delete()
        self.stdout.write(f"Deleted {deleted} log rows older than {days} days.")
