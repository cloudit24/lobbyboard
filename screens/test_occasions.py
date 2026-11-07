"""Occasions: celebrations that take over the TV on their dates, or when an
agent presses Play now - and stay stopped when an agent presses Stop."""
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from library.models import MediaItem, Playlist, PlaylistItem
from screens.models import Occasion, Screen

MEDIA = tempfile.mkdtemp()


def playlist(kind, *names):
    pl = Playlist.objects.create(name=f"{kind} list", kind=kind)
    for i, n in enumerate(names):
        item = MediaItem.objects.create(title=n, file=SimpleUploadedFile(n, b"data"), status="approved")
        PlaylistItem.objects.create(playlist=pl, item=item, order=i)
    return pl


@override_settings(MEDIA_ROOT=MEDIA)
class Occasions(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.screen = Screen.objects.get(slug="reception")
        self.now = timezone.now()
        self.occ = Occasion.objects.create(
            name="National Day", greeting_en="Happy National Day", theme="national", mode="mix",
            photos=playlist("image", "a.jpg"), videos=playlist("video", "v.mp4"), songs=playlist("audio", "s.mp3"),
            starts_at=self.now - timedelta(hours=1), ends_at=self.now + timedelta(days=1))

    def occasion(self):
        return self.client.post(reverse("screen_state", args=["reception"]), {"now_playing": ""}).json()["occasion"]

    def test_runs_on_its_dates_and_sends_everything_the_tv_needs(self):
        o = self.occasion()
        self.assertEqual((o["name"], o["theme"], o["mode"]), ("National Day", "national", "mix"))
        self.assertEqual([len(o["photos"]), len(o["videos"]), len(o["songs"])], [1, 1, 1])

    def test_not_before_or_after(self):
        self.occ.starts_at = self.now + timedelta(days=1)
        self.occ.ends_at = self.now + timedelta(days=2)
        self.occ.save()
        self.assertIsNone(self.occasion())

    def test_only_on_its_screens(self):
        other = Screen.objects.create(name="Hall", slug="hall")
        self.occ.screens.add(other)
        self.assertIsNone(self.occasion())

    def test_switched_off_never_runs(self):
        self.occ.is_active = False
        self.occ.save()
        self.assertIsNone(self.occasion())

    def test_photos_only_mode_sends_no_videos(self):
        self.occ.mode = "photos_music"
        self.occ.save()
        o = self.occasion()
        self.assertEqual(o["videos"], [])
        self.assertEqual(len(o["songs"]), 1)

    def test_agent_stop_holds_for_this_run_and_play_brings_it_back(self):
        agent = User.objects.create_user("agent1", password="pw-agent-123")
        agent.groups.add(Group.objects.get(name="Reception"))
        self.client.login(username="agent1", password="pw-agent-123")
        url = reverse("agent:screen", args=["reception"])
        self.client.post(url, {"action": "occasion_stop", "occasion": self.occ.pk})
        self.assertIsNone(self.occasion())
        self.client.post(url, {"action": "occasion_play", "occasion": self.occ.pk})
        self.assertEqual(self.occasion()["name"], "National Day")
        self.assertContains(self.client.get(url), "National Day")

    def test_play_now_without_dates(self):
        manual = Occasion.objects.create(name="Visit", mode="photos_music", is_on=True)
        self.occ.delete()
        self.assertEqual(self.occasion()["id"], manual.pk)
