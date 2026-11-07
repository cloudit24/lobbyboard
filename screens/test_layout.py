import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import widgets
from .models import Screen


class LayoutDesignerTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("layout-admin", "a@example.com", "x-test-only-1")
        self.scr = Screen.objects.create(name="Lobby", slug="lobby")
        self.url = reverse("admin:screens_screen_layout", args=[self.scr.pk])

    def test_clean_drops_unknown_duplicate_and_out_of_grid(self):
        out = widgets.clean([{"t": "clock", "x": 30, "y": -2, "w": 99, "h": 1}, {"t": "clock"}, {"t": "evil"}, "x"])
        self.assertEqual(out, [{"t": "clock", "x": 0, "y": 0, "w": 24, "h": 2}])

    def test_empty_layout_uses_default(self):
        self.assertEqual([w["t"] for w in widgets.for_screen(self.scr)], [w["t"] for w in widgets.DEFAULT_LAYOUT])

    def test_designer_needs_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_save_then_tv_shows_only_saved_widgets(self):
        self.client.force_login(self.admin)
        r = self.client.get(self.url)
        self.assertContains(r, "ld-canvas")
        layout = [{"t": "media", "x": 0, "y": 0, "w": 24, "h": 9}, {"t": "clock", "x": 0, "y": 9, "w": 6, "h": 3}]
        self.client.post(self.url, {"action": "save", "layout": json.dumps(layout)})
        self.scr.refresh_from_db()
        self.assertEqual(self.scr.layout, layout)
        html = self.client.get(reverse("screen", args=["lobby"])).content.decode()
        self.assertIn("cell-media", html)
        self.assertIn("grid-column:1 / span 24", html)
        self.assertNotIn("cell-prayer", html)

    def test_reset_and_copy(self):
        self.client.force_login(self.admin)
        other = Screen.objects.create(name="Hall", slug="hall", layout=[{"t": "logo", "x": 0, "y": 0, "w": 4, "h": 4}])
        self.client.post(self.url, {"action": "copy", "source": other.pk})
        self.scr.refresh_from_db()
        self.assertEqual(self.scr.layout, other.layout)
        self.client.post(self.url, {"action": "reset"})
        self.scr.refresh_from_db()
        self.assertEqual(self.scr.layout, [])
