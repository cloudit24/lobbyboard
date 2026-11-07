"""About us: copied once from a website's pages, then served from this server only."""
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from .models import AboutUs

CARD = '<div class="strategy-card"><h3>{t}</h3><p>{p}</p></div>'


def about_page(v, m, vals, obj):
    return ('<div>' + CARD.format(t="🎯 V", p=v) + CARD.format(t="🤝 M", p=m)
            + '<div class="strategy-card"><h3>💎 Values</h3><ul>' + "".join(f"<li>{x}</li>" for x in vals)
            + "</ul></div>" + CARD.format(t="📈 " + obj, p="Do it.") + "</div>")


def products_page(names):
    return "".join(f'<div class="product-card" id="{i}"><div class="product-card-img"><svg><use href="/i.svg#{i}"></use>'
                   f'</svg></div><div class="product-card-body"><h3>{n}</h3><p>Text</p></div></div>'
                   for i, n in names)


PAGES = {
    "http://x/ar/about": about_page("رؤية", "رسالة", ["تعاون"], "تطوير"),
    "http://x/en/about": about_page("A vision", "A mission", ["Teamwork"], "Develop"),
    "http://x/ar/products": products_page([("ice", "ثلج"), ("trading", "تجارة")]),
    "http://x/en/products": products_page([("ice", "Ice"), ("trading", "Trading")]),
    "http://x/i.svg": '<svg><symbol id="ice" viewBox="0 0 24 24"><path stroke="currentColor" d="M1 1"/></symbol></svg>',
}


class AboutUsTests(TestCase):
    @mock.patch("screens.aboutcopy._get", side_effect=lambda url: PAGES[url].encode())
    def copy(self, _):
        call_command("copy_about", about_ar="http://x/ar/about", about_en="http://x/en/about",
                     products_ar="http://x/ar/products", products_en="http://x/en/products", hide="trading", stdout=mock.Mock())

    def test_off_by_default(self):
        self.copy()
        self.assertIsNone(self.client.get("/api/about/").json()["about"])

    def test_copied_and_served(self):
        self.copy()
        a = AboutUs.load()
        a.is_on = True
        a.save()
        d = self.client.get("/api/about/").json()
        self.assertEqual(d["about"]["vision"], {"ar": "رؤية", "en": "A vision"})
        self.assertEqual(d["about"]["values"], [{"ar": "تعاون", "en": "Teamwork"}])
        self.assertEqual(d["about"]["objectives"][0]["title_en"], "Develop")
        self.assertEqual([p["nameEn"] for p in d["products"]], ["Ice"])           # Trading left out
        self.assertTrue(d["products"][0]["iconUrl"].startswith("data:image/svg+xml;base64,"))
        self.assertIn("<svg", d["productsQr"])

    def test_copy_again_replaces(self):
        self.copy()
        self.copy()
        self.assertEqual(AboutUs.load().values.count(), 1)
