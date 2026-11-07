import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "First start only: create the admin account from ADMIN_USERNAME / ADMIN_PASSWORD if no admin exists yet."

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            return
        username = os.environ.get("ADMIN_USERNAME", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not username or not password:
            self.stdout.write("No admin yet. Set ADMIN_USERNAME and ADMIN_PASSWORD in .env, "
                              "or run: docker compose exec web python manage.py createsuperuser")
            return
        User.objects.create_superuser(username=username, password=password,
                                      email=os.environ.get("ADMIN_EMAIL", ""))
        self.stdout.write(self.style.SUCCESS(f"Admin account “{username}” created. Change the password after logging in."))
