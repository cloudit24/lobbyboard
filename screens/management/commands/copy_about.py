"""Copy About us content from your website's public pages into this server, once.

    manage.py copy_about --about-ar URL --about-en URL --products-ar URL --products-en URL [--hide id,name]

After this the TV shows the copy; the website can change or go away without
touching the TV. Running it again replaces the copy. Edit it in Admin > About us.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from screens import aboutcopy
from screens.models import AboutUs


class Command(BaseCommand):
    help = "Copy vision, mission, values, objectives and products from website pages into Admin > About us."

    def add_arguments(self, parser):
        for name in ("--about-ar", "--about-en", "--products-ar", "--products-en"):
            parser.add_argument(name, required=True)
        parser.add_argument("--hide", default="", help="Products to leave out: ids or names, comma separated.")

    @transaction.atomic
    def handle(self, **o):
        about = aboutcopy.about(o["about_ar"], o["about_en"])
        if not about:
            self.stderr.write("No vision/mission/values cards found on the About pages; nothing changed.")
            return
        products = aboutcopy.products(o["products_ar"], o["products_en"], o["hide"])
        a = AboutUs.load()
        a.vision_ar, a.vision_en = about["vision"]["ar"], about["vision"]["en"]
        a.mission_ar, a.mission_en = about["mission"]["ar"], about["mission"]["en"]
        a.products_url = a.products_url or o["products_en"]
        a.save()
        a.values.all().delete()
        a.objectives.all().delete()
        a.products.all().delete()
        for i, v in enumerate(about["values"]):
            a.values.create(text_ar=v["ar"], text_en=v["en"], order=i)
        for i, ob in enumerate(about["objectives"]):
            a.objectives.create(order=i, **ob)
        for i, p in enumerate(products):
            a.products.create(order=i, **p)
        self.stdout.write(f"Copied: {len(about['values'])} values, {len(about['objectives'])} objectives, "
                          f"{len(products)} products. Turn it on in Admin > About us.")
