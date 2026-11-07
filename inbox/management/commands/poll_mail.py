import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from inbox import mail
from inbox.models import MailSettings


class Command(BaseCommand):
    help = "Take in new emails from the enquiries mailbox. --loop keeps checking (Mail settings > Check every)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")

    def handle(self, loop=False, **options):
        while True:
            close_old_connections()
            try:
                n = mail.poll()
                if n:
                    self.stdout.write(f"Took in {n} email(s).")
            except Exception as exc:  # keep the loop alive
                self.stderr.write(f"Mail check failed: {exc}")
            if not loop:
                return
            time.sleep(max(MailSettings.load().poll_seconds, 15))
