import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core import mail as outbox
from django.core.mail import get_connection
from django.test import TestCase, override_settings
from django.urls import reverse
from imap_tools import MailMessage

from audit.models import AuditLog
from core.models import NetworkSettings
from inbox import mail
from inbox.models import Enquiry, MailSettings, Queue
from people.models import AgentProfile
from visitors.models import Visit

TMP = tempfile.mkdtemp()


def raw_email(subject, body, frm="Sara <sara@example.com>", msg_id="<m1@example.com>", extra=""):
    return MailMessage.from_bytes((
        f"From: {frm}\r\nTo: care@org.test\r\nSubject: {subject}\r\nMessage-ID: {msg_id}\r\n{extra}"
        f"Date: Mon, 28 Sep 2026 10:00:00 +0400\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}\r\n").encode())


def locmem(_settings):
    return get_connection("django.core.mail.backends.locmem.EmailBackend")


@override_settings(DATA_DIR=__import__("pathlib").Path(TMP), MEDIA_ROOT=TMP)
class DeskTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.care = User.objects.create_user("mariam", password="pw-care-123", first_name="Mariam", email="m@org.test")
        self.care.groups.add(Group.objects.get(name="Customer care"))
        AgentProfile.objects.create(user=self.care, display_name="Mariam")
        self.reception = User.objects.create_user("omar", password="pw-recep-123")
        self.reception.groups.add(Group.objects.get(name="Reception"))
        self.sec = User.objects.create_user("huda", password="pw-sec-123")
        self.sec.groups.add(Group.objects.get(name="Secretaries"))
        self.membership = Queue.objects.get(name="Membership")
        self.membership.agents.add(self.care)
        s = MailSettings.load()
        s.smtp_host, s.from_email, s.cc_emails = "smtp.org.test", "care@org.test", "official@org.test"
        s.save()

    # --- roles -------------------------------------------------------
    def test_menus_follow_roles(self):
        self.client.login(username="omar", password="pw-recep-123")
        r = self.client.get(reverse("agent:home"))
        self.assertContains(r, "Visitors")
        self.assertNotContains(r, ">Enquiries<")
        self.assertEqual(self.client.get(reverse("agent:enquiries")).status_code, 403)
        self.assertEqual(self.client.get(reverse("agent:team")).status_code, 403)

    def test_secretary_can_open_everything(self):
        self.client.login(username="huda", password="pw-sec-123")
        for name in ("home", "visitors", "enquiries", "team", "reports", "upload"):
            self.assertEqual(self.client.get(reverse(f"agent:{name}")).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("agent:tv") + "?all=1").status_code, 200)

    # --- visitors ----------------------------------------------------
    def test_check_in_and_out_is_logged(self):
        self.client.login(username="omar", password="pw-recep-123")
        self.client.post(reverse("agent:visitors"), {"name": "Ali Hassan", "company": "ACME", "people_count": 2})
        v = Visit.objects.get()
        self.assertTrue(v.is_inside)
        self.client.post(reverse("agent:visitor_out", args=[v.pk]))
        v.refresh_from_db()
        self.assertFalse(v.is_inside)
        self.assertEqual(AuditLog.objects.filter(event_type="visitor").count(), 2)

    # --- enquiries in ------------------------------------------------
    def test_email_routed_by_keyword_and_assigned(self):
        enq, created = mail.ingest(raw_email("Membership renewal", "How do I renew my membership?"))
        self.assertTrue(created)
        self.assertEqual((enq.queue, enq.assigned_to, enq.customer_email), (self.membership, self.care, "sara@example.com"))

    def test_unmatched_goes_to_default_topic(self):
        enq, _ = mail.ingest(raw_email("Hello", "Opening hours please"))
        self.assertEqual(enq.queue.name, "General enquiries")

    def test_website_form_email_finds_real_customer(self):
        body = "Name: Khalid Saeed\nEmail: khalid@example.com\nPhone: 050 111 2222\n\nI want a service request for trading."
        enq, _ = mail.ingest(raw_email("Website contact form", body, frm="Website <no-reply@org.test>"))
        self.assertEqual((enq.customer_name, enq.customer_email, enq.customer_phone, enq.source),
                         ("Khalid Saeed", "khalid@example.com", "050 111 2222", "website"))
        self.assertEqual(enq.queue.name, "Services and trading")

    def test_customer_reply_joins_same_enquiry_and_duplicates_ignored(self):
        enq, _ = mail.ingest(raw_email("Membership", "Question"))
        again, created = mail.ingest(raw_email(f"Re: Membership [{enq.ref}]", "More info", msg_id="<m2@example.com>"))
        self.assertEqual((again.pk, created), (enq.pk, False))
        self.assertEqual(mail.ingest(raw_email("Membership", "Question"))[0], None)  # same Message-ID
        self.assertEqual(enq.messages.count(), 2)

    # --- replies out -------------------------------------------------
    @mock.patch("inbox.mail.connection", locmem)
    def test_reply_uses_agent_name_and_copies_officials(self):
        enq, _ = mail.ingest(raw_email("Membership", "Question"))
        self.client.login(username="mariam", password="pw-care-123")
        self.client.post(reverse("agent:enquiry", args=[enq.pk]), {"action": "reply", "body": "Welcome!", "extra_cc": ""})
        sent = outbox.outbox[-1]
        self.assertEqual(sent.from_email, "Customer Care – Mariam <care@org.test>")
        self.assertEqual(sent.to, ["sara@example.com"])
        self.assertIn("official@org.test", sent.cc)
        self.assertIn(f"[{enq.ref}]", sent.subject)
        self.assertEqual(sent.extra_headers["In-Reply-To"], "<m1@example.com>")
        enq.refresh_from_db()
        self.assertEqual(enq.status, "waiting")
        self.assertIsNotNone(enq.first_reply_at)

    def test_enquiry_page_opens_before_mail_is_set_up(self):
        MailSettings.objects.filter(pk=1).update(from_email="", smtp_host="")
        enq, _ = mail.ingest(raw_email("Membership", "Question"))
        self.client.login(username="mariam", password="pw-care-123")
        self.assertContains(self.client.get(reverse("agent:enquiry", args=[enq.pk])), "Sending isn't set up yet")

    def test_agent_cannot_see_other_topics(self):
        enq, _ = mail.ingest(raw_email("Hello", "general question"))  # General: no agents
        self.client.login(username="mariam", password="pw-care-123")
        self.assertEqual(self.client.get(reverse("agent:enquiry", args=[enq.pk])).status_code, 404)

    def test_secretary_reassigns_and_it_is_logged(self):
        enq, _ = mail.ingest(raw_email("Hello", "general question"))
        self.client.login(username="huda", password="pw-sec-123")
        self.client.post(reverse("agent:enquiry", args=[enq.pk]), {"action": "assign", "agent": self.care.pk})
        enq.refresh_from_db()
        self.assertEqual(enq.assigned_to, self.care)
        self.assertTrue(AuditLog.objects.filter(event_type="desk", summary__contains="Given to").exists())

    # --- secretary ---------------------------------------------------
    def test_secretary_adds_agent_but_not_admins(self):
        self.client.login(username="huda", password="pw-sec-123")
        r = self.client.post(reverse("agent:team_new"), {
            "username": "noor", "first_name": "Noor", "password": "a-Strong-pass-991", "is_active": "on",
            "roles": [Group.objects.get(name="Customer care").pk], "queues": [self.membership.pk]})
        self.assertEqual(r.status_code, 302)
        noor = User.objects.get(username="noor")
        self.assertTrue(noor.has_perm("inbox.handle_enquiries"))
        self.assertFalse(noor.is_staff)
        boss = User.objects.create_superuser("boss", password="x-pass-123-Y")
        self.client.get(reverse("agent:team_edit", args=[boss.pk]))
        self.assertEqual(self.client.post(reverse("agent:team_edit", args=[boss.pk]), {"username": "hacked"}).status_code, 302)
        boss.refresh_from_db()
        self.assertEqual(boss.username, "boss")

    def test_report_exports_excel(self):
        mail.ingest(raw_email("Membership", "Question"))
        Visit.objects.create(name="A")
        self.client.login(username="huda", password="pw-sec-123")
        r = self.client.get(reverse("agent:reports") + "?export=xlsx")
        self.assertEqual(r["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(r.content.startswith(b"PK"))

    # --- network -----------------------------------------------------
    @override_settings(ENV_ALLOWED_HOSTS=["localhost"])
    def test_tunnel_hostname_allowed_after_adding_in_admin(self):
        self.assertEqual(self.client.get("/login/", HTTP_HOST="desk.example.com").status_code, 400)
        n = NetworkSettings.load()
        n.public_hostnames = "https://desk.example.com/"
        n.save()
        self.assertEqual(self.client.get("/login/", HTTP_HOST="desk.example.com").status_code, 200)
