import json
import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from audit.models import AuditLog
from core.models import DisplaySettings
from library.models import MediaItem, Playlist, PlaylistItem
from screens.models import Screen

MEDIA = tempfile.mkdtemp()


def media(title, name, status="approved"):
    return MediaItem.objects.create(title=title, file=SimpleUploadedFile(name, b"data"), status=status)


@override_settings(MEDIA_ROOT=MEDIA)
class FlowTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.screen = Screen.objects.get(slug="reception")  # made by the starter-data migration
        self.agent = User.objects.create_user("agent1", password="pw-agent-123")
        self.agent.groups.add(Group.objects.get(name="Reception"))
        self.admin = User.objects.create_superuser("boss", password="pw-admin-123")

    def state(self):
        r = self.client.post(reverse("screen_state", args=["reception"]), {"now_playing": "Welcome screen"})
        self.assertEqual(r.status_code, 200)
        return r.json()

    # --- access -------------------------------------------------------
    def test_non_agent_is_refused(self):
        User.objects.create_user("visitor", password="pw-visit-123")
        self.client.login(username="visitor", password="pw-visit-123")
        self.assertEqual(self.client.get(reverse("agent:home")).status_code, 403)

    def test_agent_not_assigned_to_screen_is_refused(self):
        other = User.objects.create_user("agent2", password="pw")
        self.screen.agents.add(other)  # screen now limited to agent2
        self.client.login(username="agent1", password="pw-agent-123")
        self.assertEqual(self.client.get(reverse("agent:screen", args=["reception"])).status_code, 403)

    def test_agent_panel_and_screen_page_render(self):
        self.client.login(username="agent1", password="pw-agent-123")
        self.assertContains(self.client.get(reverse("agent:screen", args=["reception"])), "Background music")
        self.client.logout()
        self.assertContains(self.client.get(reverse("screen", args=["reception"])), "tv-config")

    # --- upload -> review -> play --------------------------------------
    def test_upload_waits_for_review_and_is_not_playable(self):
        self.client.login(username="agent1", password="pw-agent-123")
        self.client.post(reverse("agent:upload"), {"files": [SimpleUploadedFile("song.mp3", b"x")]})
        item = MediaItem.objects.get()
        self.assertEqual((item.status, item.kind, item.uploaded_by), ("pending", "audio", self.agent))
        self.assertTrue(AuditLog.objects.filter(event_type="upload").exists())

        # agent cannot pick an unapproved track
        self.client.post(reverse("agent:screen", args=["reception"]), {"action": "music_play", "source": f"item:{item.pk}"})
        self.assertFalse(self.state()["musicOn"])

    def test_bad_file_type_is_refused(self):
        self.client.login(username="agent1", password="pw-agent-123")
        self.client.post(reverse("agent:upload"), {"files": [SimpleUploadedFile("virus.exe", b"x")]})
        self.assertFalse(MediaItem.objects.exists())

    def test_admin_approve_action_logs_review(self):
        item = media("Track", "t.mp3", status="pending")
        self.client.login(username="boss", password="pw-admin-123")
        self.client.post(reverse("admin:library_mediaitem_changelist"),
                         {"action": "approve", "_selected_action": [item.pk]})
        item.refresh_from_db()
        self.assertEqual((item.status, item.reviewed_by), ("approved", self.admin))
        self.assertTrue(AuditLog.objects.filter(event_type="review").exists())

    def test_playlist_music_plays_in_admin_order_and_is_logged(self):
        a, b = media("A", "a.mp3"), media("B", "b.mp3")
        pl = Playlist.objects.create(name="Morning", kind="audio")
        PlaylistItem.objects.create(playlist=pl, item=b, order=1)
        PlaylistItem.objects.create(playlist=pl, item=a, order=2)
        self.client.login(username="agent1", password="pw-agent-123")
        self.client.post(reverse("agent:screen", args=["reception"]), {"action": "music_play", "source": f"playlist:{pl.pk}"})
        s = self.state()
        self.assertTrue(s["musicOn"])
        self.assertEqual([m["title"] for m in s["music"]], ["B", "A"])
        log = AuditLog.objects.get(event_type="agent_action")
        self.assertEqual(log.user, "agent1")
        self.assertIn("Morning", log.summary)

    def test_video_and_volume_and_commands(self):
        v = media("Intro", "intro.mp4")
        self.client.login(username="agent1", password="pw-agent-123")
        url = reverse("agent:screen", args=["reception"])
        self.client.post(url, {"action": "video", "source": f"item:{v.pk}", "muted": "1"})
        seq = self.state()["commandSeq"]
        self.client.post(url, {"action": "volume", "volume": "250"})
        self.client.post(url, {"action": "video_next"})
        s = self.state()
        self.assertEqual((s["center"], s["videoMuted"], s["volume"]), ("video", True, 100))
        self.assertEqual((s["command"], s["commandSeq"]), ("next_video", seq + 1))
        self.assertEqual(s["video"][0]["title"], "Intro")

    # --- screen + settings --------------------------------------------
    def test_screen_poll_marks_online_and_logs_once(self):
        self.state()
        self.state()
        self.screen.refresh_from_db()
        self.assertTrue(self.screen.is_online)
        self.assertEqual(AuditLog.objects.filter(event_type="screen_online").count(), 1)
        self.assertFalse(AuditLog.objects.filter(event_type="request", path__startswith="/api/").exists())

    def test_settings_change_is_logged_and_reloads_screens(self):
        before = self.state()["contentVersion"]
        s = DisplaySettings.load()
        s.org_name_en = "Test Org"
        s.save()
        self.assertNotEqual(self.state()["contentVersion"], before)
        log = AuditLog.objects.filter(event_type="admin_edit").latest("timestamp")
        self.assertEqual(json.loads(log.extra)["changes"]["org_name_en"]["new"], "Test Org")

    def test_screen_page_with_qr_and_contact(self):
        s = DisplaySettings.load()
        s.qr_url, s.phone = "https://example.com", "000 111"
        s.save()
        r = self.client.get(reverse("screen", args=["reception"]))
        self.assertContains(r, "<svg")
        self.assertContains(r, "000 111")

    def test_no_organisation_data_in_defaults(self):
        s = DisplaySettings.load()
        self.assertEqual((s.phone, s.email, s.website, s.qr_url), ("", "", "", ""))

    def test_failed_login_is_logged(self):
        self.client.post(reverse("login"), {"username": "agent1", "password": "wrong"})
        self.assertTrue(AuditLog.objects.filter(event_type="login_fail", user="agent1").exists())

    def test_admin_dashboard_renders(self):
        self.client.login(username="boss", password="pw-admin-123")
        r = self.client.get(reverse("admin:index"))
        self.assertContains(r, "Uploads waiting for review")
        self.assertContains(self.client.get(reverse("admin:core_displaysettings_change", args=[1])), "Top bar")
