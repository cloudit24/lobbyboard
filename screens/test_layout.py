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
        self.assertEqual([{k: v for k, v in i.items() if k != "o"} for i in out],
                         [{"t": "clock", "x": 0, "y": 0, "w": 24, "h": 2}])
        self.assertEqual(out[0]["o"]["look"], "card")

    def test_settings_are_checked_and_multi_widgets_allowed(self):
        out = widgets.clean([
            {"t": "text", "x": 0, "y": 0, "w": 4, "h": 2, "o": {"size": 9999, "align": "evil", "body": "Hi"}},
            {"t": "text", "x": 4, "y": 0, "w": 4, "h": 2},
            {"t": "web", "x": 8, "y": 0, "w": 4, "h": 2, "o": {"url": "javascript:alert(1)"}},
        ])
        self.assertEqual(len(out), 3)
        self.assertEqual((out[0]["o"]["size"], out[0]["o"]["align"], out[0]["o"]["body"]), (160, "center", "Hi"))
        self.assertEqual(out[2]["o"]["url"], "")

    def test_empty_layout_uses_default(self):
        self.assertEqual([w["t"] for w in widgets.for_screen(self.scr)], [w["t"] for w in widgets.DEFAULT_LAYOUT])

    def test_designer_needs_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_save_then_tv_shows_only_saved_widgets(self):
        self.client.force_login(self.admin)
        r = self.client.get(self.url)
        self.assertContains(r, "ld-canvas")
        layout = [{"t": "media", "x": 0, "y": 0, "w": 24, "h": 9}, {"t": "clock", "x": 0, "y": 9, "w": 6, "h": 3},
                  {"t": "text", "x": 6, "y": 9, "w": 6, "h": 3, "o": {"body": "Open 9 to 5"}}]
        other = Screen.objects.create(name="Hall", slug="hall")
        self.client.post(self.url, {"action": "save", "layout": json.dumps(layout), "background_dim": "60", "all_tvs": "on"})
        self.scr.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual([i["t"] for i in self.scr.layout], ["media", "clock", "text"])
        self.assertEqual((self.scr.background_dim, other.layout), (60, self.scr.layout))
        html = self.client.get(reverse("screen", args=["lobby"])).content.decode()
        self.assertIn("cell-media", html)
        self.assertIn("grid-column:1 / span 24", html)
        self.assertNotIn("cell-prayer", html)
        self.assertIn("Open 9 to 5", html)

    def test_reset_and_copy(self):
        self.client.force_login(self.admin)
        other = Screen.objects.create(name="Hall", slug="hall", layout=[{"t": "logo", "x": 0, "y": 0, "w": 4, "h": 4}])
        self.client.post(self.url, {"action": "copy", "source": other.pk})
        self.scr.refresh_from_db()
        self.assertEqual(self.scr.layout, other.layout)
        self.client.post(self.url, {"action": "reset"})
        self.scr.refresh_from_db()
        self.assertEqual(self.scr.layout, [])


class AnnouncementTests(TestCase):
    def test_reception_turns_announcement_on_and_off(self):
        admin = get_user_model().objects.create_superuser("notice-admin", "n@example.com", "x-test-only-1")
        scr = Screen.objects.create(name="Lobby", slug="lobby")
        self.client.force_login(admin)
        url = reverse("agent:screen", args=["lobby"])
        state = reverse("screen_state", args=["lobby"])
        self.client.post(url, {"action": "notice_on", "notice_text": "On a short break", "notice_anim": "zoom",
                               "notice_color": "#123456", "notice_minutes": "10"})
        n = self.client.post(state).json()["notice"]
        self.assertEqual((n["text"], n["anim"], n["color"]), ("On a short break", "zoom", "#123456"))
        self.client.post(url, {"action": "notice_off"})
        self.assertIsNone(self.client.post(state).json()["notice"])
        scr.refresh_from_db()

    def test_reception_saves_and_removes_own_button(self):
        from .models import NoticePreset
        admin = get_user_model().objects.create_superuser("preset-admin", "p@example.com", "x-test-only-1")
        Screen.objects.create(name="Lobby", slug="lobby")
        self.client.force_login(admin)
        url = reverse("agent:screen", args=["lobby"])
        self.client.post(url, {"action": ["notice_on", "preset_save"], "notice_text": "Lift out of order",
                               "preset_label": "Lift", "notice_minutes": "30"})
        p = NoticePreset.objects.get()
        self.assertEqual((p.label, p.text, p.minutes, p.created_by), ("Lift", "Lift out of order", 30, admin))
        self.assertContains(self.client.get(url), "⭐ Lift")
        self.client.post(url, {"action": "preset_delete", "preset": p.pk})
        self.assertFalse(NoticePreset.objects.exists())
