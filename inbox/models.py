import re

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


def split_emails(text):
    return [e for e in re.split(r"[\s,;]+", text or "") if "@" in e]


class MailSettings(models.Model):
    """The mailbox enquiries arrive in, and the mail server replies go out
    through. One row, set by an admin."""

    SECURITY = [("starttls", "STARTTLS (usually port 587)"), ("ssl", "SSL/TLS (usually port 465)"), ("none", "None")]

    enabled = models.BooleanField("Check the mailbox", default=False,
                                  help_text="Tick once the settings below are filled in and tested.")
    # Incoming (IMAP)
    imap_host = models.CharField("IMAP server", max_length=200, blank=True, help_text="e.g. mail.example.com")
    imap_port = models.PositiveIntegerField("IMAP port", default=993)
    imap_ssl = models.BooleanField("IMAP uses SSL", default=True)
    imap_user = models.CharField("Mailbox login", max_length=200, blank=True)
    imap_password = models.CharField("Mailbox password", max_length=200, blank=True)
    imap_folder = models.CharField("Folder to read", max_length=100, default="INBOX")
    poll_seconds = models.PositiveIntegerField("Check every (seconds)", default=60)

    # Outgoing (SMTP)
    smtp_host = models.CharField("SMTP server", max_length=200, blank=True)
    smtp_port = models.PositiveIntegerField("SMTP port", default=587)
    smtp_security = models.CharField("SMTP security", max_length=10, choices=SECURITY, default="starttls")
    smtp_user = models.CharField("SMTP login", max_length=200, blank=True, help_text="Blank = same as mailbox login.")
    smtp_password = models.CharField("SMTP password", max_length=200, blank=True, help_text="Blank = same as mailbox password.")
    from_email = models.EmailField("Send from address", blank=True, help_text="Usually the same mailbox, e.g. care@example.com")
    from_name_pattern = models.CharField(
        "Sender name", max_length=100, default="Customer Care – {agent}",
        help_text="What customers see as the sender. {agent} = the agent's name.")
    signature = models.TextField("Signature under every reply", blank=True,
                                 help_text="{agent} = the agent's name. Organisation details go here.")
    cc_emails = models.TextField("Always copy (CC) these addresses", blank=True,
                                 help_text="Official addresses that get a copy of every reply. One per line.")
    notify_agents = models.BooleanField("Email agents about new enquiries", default=True,
                                        help_text="The assigned agent (or the topic's agents) get a short alert.")

    last_checked = models.DateTimeField(null=True, blank=True, editable=False)
    last_error = models.TextField(blank=True, editable=False)
    history = HistoricalRecords(excluded_fields=["last_checked", "last_error"])

    class Meta:
        verbose_name = verbose_name_plural = "Mail settings"

    def __str__(self):
        return "Mail settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]

    @property
    def ready_to_send(self):
        return bool(self.smtp_host and self.from_email)

    def cc_list(self):
        return split_emails(self.cc_emails)


class Queue(models.Model):
    """A topic enquiries are sorted into (General, Trading, Membership...),
    and the agents who answer it."""

    name = models.CharField(max_length=100)
    keywords = models.TextField(
        blank=True, help_text="An enquiry goes here when its subject or text contains one of these words "
                              "(one per line, any language). The first matching topic wins.")
    agents = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="queues",
                                    help_text="Who answers this topic.")
    auto_assign = models.BooleanField("Give new enquiries to an agent automatically", default=True,
                                      help_text="To the agent with the fewest open enquiries. Off = agents pick them up.")
    cc_emails = models.TextField("Also copy (CC)", blank=True, help_text="Extra addresses copied on replies for this topic.")
    is_default = models.BooleanField("Default topic", default=False, help_text="Used when no keywords match.")
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField("In use", default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Topic"

    def __str__(self):
        return self.name

    def keyword_list(self):
        return [k.strip().lower() for k in (self.keywords or "").splitlines() if k.strip()]


class Enquiry(models.Model):
    STATUS = [("new", "New"), ("open", "Open"), ("waiting", "Waiting for customer"), ("closed", "Closed")]
    SOURCE = [("email", "Email"), ("website", "Website form"), ("phone", "Phone"), ("walk_in", "Walk-in"),
              ("other", "Other")]

    queue = models.ForeignKey(Queue, null=True, blank=True, on_delete=models.SET_NULL, related_name="enquiries",
                              verbose_name="Topic")
    subject = models.CharField(max_length=300)
    customer_name = models.CharField(max_length=150, blank=True)
    customer_email = models.EmailField(blank=True, db_index=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="new", db_index=True)
    source = models.CharField(max_length=10, choices=SOURCE, default="email")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="enquiries")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    first_reply_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-updated_at"]
        verbose_name_plural = "Enquiries"
        permissions = [("handle_enquiries", "Can answer enquiries in the desk dashboard")]

    def __str__(self):
        return f"#{self.pk} {self.subject}"

    @property
    def ref(self):
        return f"#{self.pk}"

    def response_minutes(self):
        if not self.first_reply_at:
            return None
        return int((self.first_reply_at - self.created_at).total_seconds() // 60)


class Message(models.Model):
    """One email in or out, or an internal note, on an enquiry."""

    KIND = [("in", "From customer"), ("out", "Reply"), ("note", "Internal note")]

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="messages")
    kind = models.CharField(max_length=5, choices=KIND)
    from_email = models.CharField(max_length=300, blank=True)
    to = models.TextField(blank=True)
    cc = models.TextField(blank=True)
    subject = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True)
    message_id = models.CharField(max_length=300, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=300, blank=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    send_error = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.get_kind_display()} on {self.enquiry.ref}"


# Customer files are private: kept outside /media (which nginx serves to anyone)
# and only handed out by a view that checks who is asking.
#
# A function, not a ready-made object: Django writes a storage object's full
# path into the migration file, so a folder rename or a move to a server left
# the old path (C:/.../TV Dashboard/data/private) frozen in there for ever.
def private_storage():
    return FileSystemStorage(location=settings.DATA_DIR / "private", base_url=None)


class Attachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="enquiries/%Y/%m/", storage=private_storage, max_length=300)
    filename = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.filename
