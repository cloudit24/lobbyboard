"""The desk dashboard: home, visitors registry, enquiries, and the secretary
pages (team, reports). TV control and uploads live in screens/views.py."""
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.models import AuditLog, log_event
from inbox import mail
from inbox.models import Attachment, Enquiry, MailSettings, Message, Queue
from people.models import AGENT_ROLES, AgentProfile, profile_of
from screens.models import Screen
from visitors.models import Visit

from .access import areas, can, enquiry_scope, needs
from .forms import AgentForm, NewEnquiryForm, NoteForm, ReplyForm, VisitForm


def _today_start():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


# ------------------------------------------------------------------ home --
@needs()
def home(request):
    u, a = request.user, areas(request.user)
    ctx = {"title": "Home"}
    if a["visitors"] or a["secretary"]:
        ctx["inside"] = Visit.objects.filter(checked_out_at__isnull=True).select_related("purpose")[:12]
        ctx["visits_today"] = Visit.objects.filter(checked_in_at__gte=_today_start()).count()
    if a["enquiries"] or a["secretary"]:
        scope = enquiry_scope(u).exclude(status="closed")
        ctx["my_open"] = scope.filter(assigned_to=u)[:10]
        ctx["unassigned"] = scope.filter(assigned_to__isnull=True)[:10]
        ctx["open_count"] = scope.count()
    if a["tv"]:
        ctx["screens"] = Screen.for_agent(u)
    if a["secretary"]:
        open_qs = Enquiry.objects.exclude(status="closed")
        ctx["sec"] = {
            "open": open_qs.count(),
            "unassigned": open_qs.filter(assigned_to__isnull=True).count(),
            "old": open_qs.filter(status="new", created_at__lt=timezone.now() - timedelta(hours=24)).count(),
            "per_agent": (User.objects.filter(is_active=True, enquiries__isnull=False)
                          .annotate(n=Count("enquiries", filter=~Q(enquiries__status="closed")))
                          .filter(n__gt=0).order_by("-n")[:10]),
            "mail_error": MailSettings.load().last_error,
        }
    return render(request, "desk/home.html", ctx)


# -------------------------------------------------------------- visitors --
@needs("visitors")
def visitors(request):
    if request.method == "POST":
        form = VisitForm(request.POST)
        if form.is_valid():
            v = form.save(commit=False)
            v.registered_by = request.user
            v.save()
            log_event("visitor", f"Checked in {v.name}" + (f" ({v.company})" if v.company else "")
                      + (f" to see {v.meeting_with}" if v.meeting_with else ""), request=request,
                      path=f"visitors.Visit#{v.pk}")
            messages.success(request, f"{v.name} checked in.")
            return redirect("agent:visitors")
    else:
        form = VisitForm()
    q = request.GET.get("q", "").strip()
    history = Visit.objects.select_related("purpose", "registered_by")
    if q:
        history = history.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(company__icontains=q)
                                 | Q(email__icontains=q) | Q(meeting_with__icontains=q) | Q(badge__icontains=q))
    elif not can(request.user, "secretary"):
        history = history.filter(checked_in_at__gte=timezone.now() - timedelta(days=30))
    page = Paginator(history, 30).get_page(request.GET.get("page"))
    return render(request, "desk/visitors.html", {
        "title": "Visitors", "form": form, "q": q, "page": page,
        "inside": Visit.objects.filter(checked_out_at__isnull=True).select_related("purpose"),
    })


@require_POST
@needs("visitors")
def visitor_out(request, pk):
    v = get_object_or_404(Visit, pk=pk, checked_out_at__isnull=True)
    v.checked_out_at, v.checked_out_by = timezone.now(), request.user
    v.save()
    log_event("visitor", f"Checked out {v.name} after {v.duration}", request=request, path=f"visitors.Visit#{v.pk}")
    messages.success(request, f"{v.name} checked out.")
    return redirect(request.POST.get("next") or "agent:visitors")


# ------------------------------------------------------------- enquiries --
@needs("enquiries")
def enquiries(request):
    u = request.user
    tab = request.GET.get("tab") or "mine"
    qs = enquiry_scope(u)
    if tab == "mine":
        qs = qs.filter(assigned_to=u).exclude(status="closed")
    elif tab == "unassigned":
        qs = qs.filter(assigned_to__isnull=True).exclude(status="closed")
    elif tab == "open":
        qs = qs.exclude(status="closed")
    elif tab == "closed":
        qs = qs.filter(status="closed")
    topic, status, q = request.GET.get("topic"), request.GET.get("status"), request.GET.get("q", "").strip()
    if topic:
        qs = qs.filter(queue_id=topic)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(subject__icontains=q) | Q(customer_name__icontains=q) | Q(customer_email__icontains=q)
                       | Q(customer_phone__icontains=q) | Q(pk=int(q.lstrip("#")) if q.lstrip("#").isdigit() else 0))
    page = Paginator(qs.order_by("-updated_at"), 30).get_page(request.GET.get("page"))
    return render(request, "desk/enquiries.html", {
        "title": "Enquiries", "tab": tab, "page": page, "q": q, "topic": topic, "status": status,
        "topics": Queue.objects.filter(is_active=True), "statuses": Enquiry.STATUS,
        "mail": MailSettings.load(),
    })


@needs("enquiries")
def enquiry_new(request):
    if request.method == "POST":
        form = NewEnquiryForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                enq = form.save(commit=False)
                enq.assigned_to = request.user
                enq.status = "open"
                enq.save()
                Message.objects.create(enquiry=enq, kind="in", subject=enq.subject, body=form.cleaned_data["message"],
                                       from_email=enq.customer_email or enq.customer_phone, sent_by=request.user)
            log_event("enquiry", f"Logged a {enq.get_source_display().lower()} enquiry {enq.ref} “{enq.subject[:80]}”",
                      request=request, path=f"inbox.Enquiry#{enq.pk}")
            return redirect("agent:enquiry", pk=enq.pk)
    else:
        form = NewEnquiryForm()
    return render(request, "desk/enquiry_new.html", {"title": "Log an enquiry", "form": form})


@needs("enquiries")
def enquiry(request, pk):
    u = request.user
    enq = get_object_or_404(enquiry_scope(u), pk=pk)
    secretary = can(u, "secretary")
    reply_form, note_form = ReplyForm(), NoteForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "reply":
            reply_form = ReplyForm(request.POST)
            if reply_form.is_valid():
                if not enq.assigned_to:
                    enq.assigned_to = u
                    enq.save()
                sent = mail.send_reply(enq, u, reply_form.cleaned_data["body"], request.FILES.getlist("files"),
                                       reply_form.cleaned_data["extra_cc"])
                if sent.send_error:
                    messages.error(request, f"Saved, but NOT sent: {sent.send_error}")
                else:
                    messages.success(request, f"Reply sent to {enq.customer_email}.")
                return redirect("agent:enquiry", pk=enq.pk)
        elif action == "note":
            note_form = NoteForm(request.POST)
            if note_form.is_valid():
                Message.objects.create(enquiry=enq, kind="note", body=note_form.cleaned_data["note"], sent_by=u)
                enq.save()
                log_event("enquiry", f"Note on {enq.ref}", request=request, path=f"inbox.Enquiry#{enq.pk}")
                return redirect("agent:enquiry", pk=enq.pk)
        else:
            msg = _enquiry_change(request, enq, action, secretary)
            if msg:
                messages.success(request, msg)
            return redirect("agent:enquiry", pk=enq.pk)

    agents = User.objects.none()
    if secretary:
        agents = User.objects.filter(is_active=True).filter(
            Q(groups__permissions__codename="handle_enquiries") | Q(is_superuser=True)).distinct().order_by("first_name")
    return render(request, "desk/enquiry.html", {
        "title": f"{enq.ref} {enq.subject}", "enq": enq, "secretary": secretary,
        "thread": enq.messages.select_related("sent_by").prefetch_related("attachments"),
        "reply_form": reply_form, "note_form": note_form, "agents": agents,
        "topics": Queue.objects.filter(is_active=True), "statuses": Enquiry.STATUS,
        "sender": mail.sender(MailSettings.load(), u)[0], "mail_ready": MailSettings.load().ready_to_send,
    })


def _enquiry_change(request, enq, action, secretary):
    u, before = request.user, (enq.status, enq.assigned_to_id, enq.queue_id)
    if action == "take":
        enq.assigned_to, msg = u, f"{enq.ref} is now yours."
    elif action == "status":
        new = request.POST.get("status")
        if new not in dict(Enquiry.STATUS):
            return None
        enq.status = new
        enq.closed_at = timezone.now() if new == "closed" else None
        msg = f"Marked {dict(Enquiry.STATUS)[new].lower()}."
    elif action == "assign" and secretary:
        agent = User.objects.filter(pk=request.POST.get("agent") or 0, is_active=True).first()
        enq.assigned_to = agent
        msg = f"Given to {profile_of(agent).name}." if agent else "Unassigned."
    elif action == "topic" and secretary:
        enq.queue = Queue.objects.filter(pk=request.POST.get("queue") or 0).first()
        msg = f"Moved to {enq.queue or 'no topic'}."
    else:
        return None
    enq.save()
    log_event("desk" if action in ("assign", "topic") else "enquiry", f"{enq.ref}: {msg}", request=request,
              path=f"inbox.Enquiry#{enq.pk}", before=before, after=(enq.status, enq.assigned_to_id, enq.queue_id))
    return msg


@needs("enquiries")
def attachment(request, pk):
    att = get_object_or_404(Attachment.objects.select_related("message__enquiry"), pk=pk)
    if not enquiry_scope(request.user).filter(pk=att.message.enquiry_id).exists():
        raise Http404
    log_event("enquiry", f"Opened attachment “{att.filename}” on {att.message.enquiry.ref}", request=request)
    return FileResponse(att.file.open("rb"), as_attachment=True, filename=att.filename)


# ------------------------------------------------------------ secretary --
@needs("secretary")
def team(request):
    people = (User.objects.filter(Q(groups__name__in=AGENT_ROLES)).distinct()
              .prefetch_related("groups", "queues").select_related("profile").order_by("-is_active", "first_name"))
    return render(request, "desk/team.html", {"title": "Team", "people": people})


def _editable(user):
    """Secretaries manage agents only - never admins or other secretaries."""
    return not (user.is_superuser or user.is_staff or user.has_perm("people.secretary_desk"))


@needs("secretary")
def team_edit(request, pk=None):
    person = get_object_or_404(User, pk=pk) if pk else None
    if person and not _editable(person):
        messages.error(request, "Admins and secretaries are managed in the admin panel.")
        return redirect("agent:team")
    initial = {}
    if person:
        prof = profile_of(person)
        initial = {"username": person.username, "first_name": person.first_name, "last_name": person.last_name,
                   "email": person.email, "display_name": prof.display_name, "job_title": prof.job_title,
                   "roles": person.groups.filter(name__in=AGENT_ROLES), "queues": person.queues.all(),
                   "screens": person.screens.all(), "is_active": person.is_active}
    form = AgentForm(request.POST or None, initial=initial, user=person)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            created = person is None
            person = person or User(username=d["username"])
            person.username, person.first_name, person.last_name = d["username"], d["first_name"], d["last_name"]
            person.email, person.is_active = d["email"], d["is_active"]
            if d["password"]:
                person.set_password(d["password"])
            person.save()
            AgentProfile.objects.update_or_create(user=person, defaults={
                "display_name": d["display_name"], "job_title": d["job_title"]})
            person.groups.remove(*Group.objects.filter(name__in=AGENT_ROLES))
            person.groups.add(*d["roles"])
            person.queues.set(d["queues"])
            person.screens.set(d["screens"])
        log_event("desk", f"{'Added' if created else 'Updated'} agent {person.username}: "
                          f"roles {', '.join(g.name for g in d['roles']) or 'none'}; "
                          f"topics {', '.join(q.name for q in d['queues']) or 'none'}"
                          + ("; password changed" if d["password"] and not created else "")
                          + ("" if d["is_active"] else "; login switched off"),
                  request=request, path=f"auth.User#{person.pk}")
        messages.success(request, f"{person.username} saved.")
        return redirect("agent:team")
    return render(request, "desk/team_edit.html", {"title": "Edit agent" if person else "Add agent",
                                                   "form": form, "person": person})


def _period(request):
    today = timezone.localdate()
    try:
        start = datetime.strptime(request.GET.get("from", ""), "%Y-%m-%d").date()
    except ValueError:
        start = today.replace(day=1)
    try:
        end = datetime.strptime(request.GET.get("to", ""), "%Y-%m-%d").date()
    except ValueError:
        end = today
    tz = timezone.get_current_timezone()
    return start, end, datetime.combine(start, time.min, tz), datetime.combine(end, time.max, tz)


def report_data(start_dt, end_dt):
    visits = Visit.objects.filter(checked_in_at__range=(start_dt, end_dt))
    enq = Enquiry.objects.filter(created_at__range=(start_dt, end_dt))
    replied = enq.filter(first_reply_at__isnull=False)
    avg = replied.aggregate(a=Avg(F("first_reply_at") - F("created_at")))["a"]
    per_agent = []
    for user in User.objects.filter(Q(enquiries__in=enq) | Q(visits_registered__in=visits)).distinct():
        mine = enq.filter(assigned_to=user)
        per_agent.append({
            "name": profile_of(user).name, "enquiries": mine.count(),
            "closed": mine.filter(status="closed").count(),
            "replies": Message.objects.filter(kind="out", sent_by=user, created_at__range=(start_dt, end_dt),
                                              send_error="").count(),
            "visitors": visits.filter(registered_by=user).count(),
            "tv_actions": AuditLog.objects.filter(event_type="agent_action", user=user.username,
                                                  timestamp__range=(start_dt, end_dt)).count(),
        })
    return {
        "visits_total": visits.count(),
        "visitors_people": visits.aggregate(n=Sum("people_count"))["n"] or 0,
        "visits_by_purpose": list(visits.values("purpose__name").annotate(n=Count("id")).order_by("-n")),
        "visits_by_day": list(visits.annotate(day=TruncDate("checked_in_at")).values("day")
                              .annotate(n=Count("id")).order_by("day")),
        "enq_total": enq.count(),
        "enq_by_topic": list(enq.values("queue__name").annotate(n=Count("id")).order_by("-n")),
        "enq_by_status": [(dict(Enquiry.STATUS)[r["status"]], r["n"])
                          for r in enq.values("status").annotate(n=Count("id")).order_by("status")],
        "enq_by_source": [(dict(Enquiry.SOURCE)[r["source"]], r["n"])
                          for r in enq.values("source").annotate(n=Count("id")).order_by("-n")],
        "avg_first_reply": (f"{int(avg.total_seconds() // 3600)} h {int(avg.total_seconds() % 3600 // 60)} min"
                            if avg else "-"),
        "unanswered": enq.filter(first_reply_at__isnull=True).exclude(status="closed").count(),
        "per_agent": sorted(per_agent, key=lambda r: -r["enquiries"] - r["visitors"]),
    }


@needs("secretary")
def reports(request):
    start, end, start_dt, end_dt = _period(request)
    data = report_data(start_dt, end_dt)
    if request.GET.get("export") == "xlsx":
        log_event("desk", f"Exported report {start} to {end}", request=request)
        return _xlsx(start, end, start_dt, end_dt, data)
    return render(request, "desk/reports.html", {"title": "Reports", "start": start, "end": end, "d": data})


def _xlsx(start, end, start_dt, end_dt, data):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    rows = [("Report", f"{start} to {end}"), (), ("Visits", data["visits_total"]),
            ("Visitors (people)", data["visitors_people"]), ("Enquiries", data["enq_total"]),
            ("Average first reply", data["avg_first_reply"]), ("Open and not answered yet", data["unanswered"]), ()]
    rows += [("Enquiries by topic", "")] + [(r["queue__name"] or "No topic", r["n"]) for r in data["enq_by_topic"]] + [()]
    rows += [("Visits by purpose", "")] + [(r["purpose__name"] or "Not given", r["n"]) for r in data["visits_by_purpose"]]
    for r in rows:
        ws.append(list(r))
    ws["A1"].font = Font(bold=True)

    ws = wb.create_sheet("Per agent")
    ws.append(["Agent", "Enquiries", "Closed", "Replies sent", "Visitors checked in", "TV actions"])
    for r in data["per_agent"]:
        ws.append([r["name"], r["enquiries"], r["closed"], r["replies"], r["visitors"], r["tv_actions"]])

    ws = wb.create_sheet("Visits")
    ws.append(["In", "Out", "Name", "Company", "Phone", "Email", "Purpose", "Here to see", "People", "Badge",
               "Checked in by"])
    for v in Visit.objects.filter(checked_in_at__range=(start_dt, end_dt)).select_related("purpose", "registered_by"):
        ws.append([timezone.localtime(v.checked_in_at).replace(tzinfo=None),
                   timezone.localtime(v.checked_out_at).replace(tzinfo=None) if v.checked_out_at else None,
                   v.name, v.company, v.phone, v.email, str(v.purpose or ""), v.meeting_with, v.people_count, v.badge,
                   v.registered_by.username if v.registered_by else ""])

    ws = wb.create_sheet("Enquiries")
    ws.append(["Ref", "Received", "Topic", "Subject", "Customer", "Email", "Phone", "Source", "Agent", "Status",
               "First reply (min)"])
    for e in Enquiry.objects.filter(created_at__range=(start_dt, end_dt)).select_related("queue", "assigned_to"):
        ws.append([e.ref, timezone.localtime(e.created_at).replace(tzinfo=None), str(e.queue or ""), e.subject,
                   e.customer_name, e.customer_email, e.customer_phone, e.get_source_display(),
                   e.assigned_to.username if e.assigned_to else "", e.get_status_display(), e.response_minutes()])
    for sheet in wb.worksheets:
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = min(40, max(10, *(len(str(c.value or "")) for c in col)))

    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="report_{start}_{end}.xlsx"'
    wb.save(resp)
    return resp
