import json

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import DisplaySettings, NetworkSettings, NewsFeed, ThemeSettings, TickerMessage


class Command(BaseCommand):
    help = ("Load display settings (and optionally news feeds / ticker messages) from a JSON file made by "
            "export_settings. Keep your organisation's file outside the repository.")

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--replace-lists", action="store_true",
                            help="Delete existing news feeds / ticker messages before adding the file's ones.")

    @transaction.atomic
    def handle(self, path, replace_lists=False, **options):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            raise CommandError(f"Can't read {path}: {exc}")

        s = DisplaySettings.load()
        fields = {f.name for f in DisplaySettings._meta.fields} - {"id", "logo", "updated_at"}
        unknown = []
        for key, value in (data.get("settings") or {}).items():
            if key in fields:
                setattr(s, key, value)
            else:
                unknown.append(key)
        s.full_clean(exclude=["logo"])
        s.save()

        for key, model in (("theme", ThemeSettings), ("network", NetworkSettings)):
            if key in data:
                obj = model.load()
                names = {f.name for f in model._meta.fields} - {"id"}
                for k, v in data[key].items():
                    if k in names:
                        setattr(obj, k, v)
                    else:
                        unknown.append(f"{key}.{k}")
                obj.full_clean()
                obj.save()

        if "news_feeds" in data:
            if replace_lists:
                NewsFeed.objects.all().delete()
            for f in data["news_feeds"]:
                NewsFeed.objects.update_or_create(url=f["url"], defaults=f)
        if "ticker" in data:
            if replace_lists:
                TickerMessage.objects.all().delete()
            for t in data["ticker"]:
                TickerMessage.objects.update_or_create(text=t["text"], defaults=t)

        self.stdout.write(self.style.SUCCESS("Settings imported."))
        if unknown:
            self.stdout.write(f"Ignored unknown keys: {', '.join(unknown)}")
