import json

from django.apps import apps
from django.core.management.base import BaseCommand
from django.forms.models import model_to_dict

from core.models import DisplaySettings, NetworkSettings, NewsFeed, ThemeSettings, TickerMessage

SKIP = {"id", "logo", "updated_at"}


class Command(BaseCommand):
    help = "Print display settings, news feeds and ticker messages as JSON (to keep a copy or move to another install)."

    def handle(self, *args, **options):
        s = model_to_dict(DisplaySettings.load())
        data = {
            "settings": {k: (str(v) if hasattr(v, "as_tuple") else v) for k, v in s.items() if k not in SKIP},
            "theme": {k: v for k, v in model_to_dict(ThemeSettings.load()).items() if k != "id"},
            "network": {k: v for k, v in model_to_dict(NetworkSettings.load()).items() if k != "id"},
            "news_feeds": [{"label": f.label, "url": f.url, "order": f.order, "is_active": f.is_active}
                           for f in NewsFeed.objects.all()],
            "ticker": [{"text": t.text, "order": t.order, "is_active": t.is_active} for t in TickerMessage.objects.all()],
        }
        self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2))
