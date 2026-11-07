"""Mail in and out for enquiries.

In:  poll() reads new messages from the mailbox (IMAP, via imap-tools). A reply
     to an existing enquiry is recognised by the [#123] tag in its subject or by
     its In-Reply-To / References headers; anything else opens a new enquiry,
     sorted into a topic by keywords and given to an agent.
Out: send_reply() sends from the shared address with the agent's name
     ("Customer Care – Mariam"), copies the official addresses, and threads the
     reply so the customer's mail program keeps the conversation together.
"""
import logging
import re
from email.headerregistry import Address
from email.utils import formataddr, make_msgid

from django.core.files.base import ContentFile
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from audit.models import log_event
from people.models import profile_of

from .models import Attachment, Enquiry, MailSettings, Message, Queue, split_emails

log = logging.getLogger(__name__)
REF_RE = re.compile(r"\[#(\d+)\]")
# Website contact forms usually send "Name: ...", "Email: ...", "Phone: ..." lines.
FORM_FIELDS = {
    "name": re.compile(r"^\s*(?:name|full name|الاسم)\s*[:：]\s*(.+)$", re.I | re.M),
    "email": re.compile(r"^\s*(?:e-?mail|البريد(?: الإلكتروني)?)\s*[:：]\s*(\S+@\S+)", re.I | re.M),
    "phone": re.compile(r"^\s*(?:phone|mobile|tel|الهاتف|الجوال)\s*[:：]\s*(.+)$", re.I | re.M),
}
MAX_ATTACHMENT = 25 * 1024 * 1024


# ---------------------------------------------------------------- sorting --
def pick_queue(subject, body):
    text = f"{subject}\n{body[:3000]}".lower()
    queues = list(Queue.objects.filter(is_active=True))
    for q in queues:
        if any(k in text for k in q.keyword_list()):
            return q
    return next((q for q in queues if q.is_default), queues[0] if queues else None)


def pick_agent(queue):
    """The topic's active agent with the fewest open enquiries."""
    if not queue or not queue.auto_assign:
        return None
    return (queue.agents.filter(is_active=True)
            .annotate(open_count=Count("enquiries", filter=~Q(enquiries__status="closed")))
            .order_by("open_count", "id").first())


# -------------------------------------------------------------- incoming --
def _clean_id(value):
    return (value or "").strip().strip("<>")


def _find_enquiry(subject, headers):
    m = REF_RE.search(subject or "")
    if m:
        enq = Enquiry.objects.filter(pk=int(m.group(1))).first()
        if enq:
            return enq
    refs = " ".join(headers.get("in-reply-to", ()) + headers.get("references", ()))
    ids = [_clean_id(x) for x in re.findall(r"<[^>]+>", refs)]
    if ids:
        msg = Message.objects.filter(message_id__in=ids).select_related("enquiry").first()
        if msg:
            return msg.enquiry
    return None


def _customer(msg):
    """(name, email, phone, source). Website forms send from a no-reply
    address; the real customer is in Reply-To or in the form lines."""
    name = msg.from_values.name if msg.from_values else ""
    email = msg.from_
    reply_to = msg.reply_to[0] if msg.reply_to else ""
    body = msg.text or ""
    found = {k: (rx.search(body).group(1).strip() if rx.search(body) else "") for k, rx in FORM_FIELDS.items()}
    source = "email"
    if reply_to and reply_to.lower() != (email or "").lower():
        email, source = reply_to, "website"
        name = (msg.reply_to_values[0].name if msg.reply_to_values else "") or found["name"] or name
    if found["email"] and ("no-reply" in (email or "") or "noreply" in (email or "")):
        email, source = found["email"], "website"
    if found["name"] and source == "website":
        name = found["name"]
    return (name or "")[:150], (email or "")[:254], found["phone"][:50], source


def _store_attachments(message, mail_msg):
    for att in mail_msg.attachments:
        if not att.filename or att.size > MAX_ATTACHMENT:
            continue
        a = Attachment(message=message, filename=att.filename[:255], size=att.size)
        a.file.save(att.filename[:200], ContentFile(att.payload), save=True)


@transaction.atomic
def ingest(mail_msg):
    """Turn one fetched email into an enquiry message. Returns (enquiry, created)."""
    msg_id = _clean_id((mail_msg.headers.get("message-id") or ("",))[0])
    if msg_id and Message.objects.filter(message_id=msg_id).exists():
        return None, False  # already have it
    subject = (mail_msg.subject or "(no subject)")[:300]
    body = mail_msg.text or re.sub(r"<[^>]+>", " ", mail_msg.html or "")
    enq = _find_enquiry(subject, mail_msg.headers)
    created = enq is None
    if created:
        name, email, phone, source = _customer(mail_msg)
        queue = pick_queue(subject, body)
        enq = Enquiry.objects.create(subject=REF_RE.sub("", subject).strip() or "(no subject)", customer_name=name,
                                     customer_email=email, customer_phone=phone, source=source, queue=queue,
                                     assigned_to=pick_agent(queue))  # created_at = when it arrived here
    else:
        if enq.status in ("waiting", "closed"):
            enq.status, enq.closed_at = "open", None
        enq.save()
    m = Message.objects.create(enquiry=enq, kind="in", from_email=mail_msg.from_[:300], to=", ".join(mail_msg.to),
                               cc=", ".join(mail_msg.cc), subject=subject, body=body.strip(), message_id=msg_id,
                               in_reply_to=_clean_id((mail_msg.headers.get("in-reply-to") or ("",))[0]))
    _store_attachments(m, mail_msg)
    log_event("enquiry", f"{'New enquiry' if created else 'Customer replied on'} {enq.ref} “{enq.subject[:80]}”"
              + (f" → {enq.queue}" if created and enq.queue else "")
              + (f", given to {enq.assigned_to}" if created and enq.assigned_to else ""),
              user="", path=f"inbox.Enquiry#{enq.pk}")
    return enq, created


def poll():
    """Fetch unread mail once. Returns the number of messages taken in."""
    from imap_tools import AND, MailBox, MailBoxUnencrypted

    s = MailSettings.load()
    if not (s.enabled and s.imap_host and s.imap_user):
        return 0
    box_cls = MailBox if s.imap_ssl else MailBoxUnencrypted
    count, new = 0, []
    try:
        with box_cls(s.imap_host, port=s.imap_port).login(s.imap_user, s.imap_password, initial_folder=s.imap_folder) as box:
            for mail_msg in box.fetch(AND(seen=False), mark_seen=True, bulk=20):
                try:
                    enq, created = ingest(mail_msg)
                except Exception as exc:  # one bad email must not stop the rest
                    log.exception("Could not take in email %s", mail_msg.uid)
                    log_event("mail_error", f"Could not read an email: {exc}"[:300], user="")
                    continue
                if enq:
                    count += 1
                    if created:
                        new.append(enq)
        MailSettings.objects.filter(pk=1).update(last_checked=timezone.now(), last_error="")
    except Exception as exc:
        MailSettings.objects.filter(pk=1).update(last_checked=timezone.now(), last_error=str(exc)[:1000])
        log.warning("Mailbox check failed: %s", exc)
        return 0
    for enq in new:
        notify_agents(enq)
    return count


# -------------------------------------------------------------- outgoing --
def connection(s):
    return get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=s.smtp_host, port=s.smtp_port,
        username=s.smtp_user or s.imap_user, password=s.smtp_password or s.imap_password,
        use_tls=s.smtp_security == "starttls", use_ssl=s.smtp_security == "ssl", timeout=20)


def sender(s, user):
    agent = profile_of(user).name if user else "Team"
    name = s.from_name_pattern.replace("{agent}", agent)
    if not s.from_email:  # not set up yet - still show who it would be from
        return f"{name} (no send-from address set yet)", agent
    # Address() quotes the name properly and keeps Arabic/Unicode readable; Django encodes it on sending.
    return str(Address(display_name=name, addr_spec=s.from_email)), agent


def send_reply(enquiry, user, body, files=(), extra_cc=""):
    """Send an agent's reply. Returns the stored Message (with send_error set if it failed)."""
    s = MailSettings.load()
    from_header, agent = sender(s, user)
    signature = s.signature.replace("{agent}", agent).strip()
    text = body.strip() + (f"\n\n{signature}" if signature else "")
    last_in = enquiry.messages.filter(kind__in=["in", "out"]).exclude(message_id="").last()
    subject = enquiry.subject if enquiry.subject.lower().startswith("re:") else f"Re: {enquiry.subject}"
    subject = f"{subject} [{enquiry.ref}]"
    cc = list(dict.fromkeys(s.cc_list() + split_emails(enquiry.queue.cc_emails if enquiry.queue else "")
                            + split_emails(extra_cc)))
    domain = (s.from_email.split("@")[-1] or None) if s.from_email else None
    msg_id = make_msgid(domain=domain)
    headers = {"Message-ID": msg_id}
    if last_in:
        refs = " ".join(f"<{m}>" for m in enquiry.messages.exclude(message_id="").values_list("message_id", flat=True))
        headers.update({"In-Reply-To": f"<{last_in.message_id}>", "References": refs})

    stored = Message.objects.create(enquiry=enquiry, kind="out", from_email=from_header, to=enquiry.customer_email,
                                    cc=", ".join(cc), subject=subject, body=text, message_id=_clean_id(msg_id),
                                    in_reply_to=last_in.message_id if last_in else "", sent_by=user)
    for f in files:
        Attachment.objects.create(message=stored, file=f, filename=f.name[:255], size=f.size)
    email = EmailMessage(subject=subject, body=text, from_email=from_header, to=[enquiry.customer_email],
                         cc=cc, reply_to=[s.from_email], headers=headers, connection=connection(s))
    for a in stored.attachments.all():
        with a.file.open("rb") as fh:
            email.attach(a.filename, fh.read())
    try:
        if not s.ready_to_send:
            raise RuntimeError("Mail settings are not filled in (SMTP server and Send-from address).")
        if not enquiry.customer_email:
            raise RuntimeError("This enquiry has no customer email address.")
        email.send()
    except Exception as exc:
        stored.send_error = str(exc)[:1000]
        stored.save(update_fields=["send_error"])
        log_event("mail_error", f"Reply on {enquiry.ref} not sent: {exc}"[:300], user=user)
        return stored

    now = timezone.now()
    enquiry.first_reply_at = enquiry.first_reply_at or now
    if enquiry.status in ("new", "open"):
        enquiry.status = "waiting"
    enquiry.save()
    log_event("enquiry", f"Replied on {enquiry.ref} to {enquiry.customer_email}" + (f" (cc {', '.join(cc)})" if cc else ""),
              user=user, path=f"inbox.Enquiry#{enquiry.pk}")
    return stored


def notify_agents(enquiry):
    """Short alert to the assigned agent, or everyone on the topic."""
    s = MailSettings.load()
    if not (s.notify_agents and s.ready_to_send):
        return
    people = [enquiry.assigned_to] if enquiry.assigned_to else list(enquiry.queue.agents.all()) if enquiry.queue else []
    to = [p.email for p in people if p and p.is_active and p.email]
    if not to:
        return
    try:
        EmailMessage(subject=f"New enquiry {enquiry.ref}: {enquiry.subject[:120]}",
                     body=(f"Topic: {enquiry.queue or '-'}\nFrom: {enquiry.customer_name} <{enquiry.customer_email}>\n"
                           f"Given to: {enquiry.assigned_to or 'nobody yet - pick it up'}\n\n"
                           "Open the desk dashboard to answer it."),
                     from_email=formataddr(("Desk dashboard", s.from_email)), to=to, connection=connection(s)).send()
    except Exception as exc:
        log.warning("Agent alert not sent: %s", exc)


def test_connection():
    """(ok, message) for the admin's "Test" button."""
    from imap_tools import MailBox, MailBoxUnencrypted
    s = MailSettings.load()
    lines, ok = [], True
    if s.imap_host:
        try:
            box_cls = MailBox if s.imap_ssl else MailBoxUnencrypted
            with box_cls(s.imap_host, port=s.imap_port).login(s.imap_user, s.imap_password, initial_folder=s.imap_folder):
                lines.append("Mailbox: connected ✓")
        except Exception as exc:
            ok = False
            lines.append(f"Mailbox: {exc}")
    if s.smtp_host:
        try:
            c = connection(s)
            c.open()
            c.close()
            lines.append("Sending: connected ✓")
        except Exception as exc:
            ok = False
            lines.append(f"Sending: {exc}")
    return ok, " · ".join(lines) or "Nothing filled in yet."
