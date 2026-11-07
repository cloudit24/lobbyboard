"""Admin home page (Dashboard): every section grouped by job, in plain words,
with a short "what is this for" line, live counts and quick actions.

To add a new section: add a line to GROUPS below ("app_label.ModelName").
Anything registered in admin but not listed here still shows, under "Other",
so nothing can go missing. Users only see what their permissions allow.
"""
from datetime import timedelta

from django.urls import NoReverseMatch, reverse
from django.utils import timezone

# (group title, group icon, [(model key, label, icon, description)])
GROUPS = [
    ("Desk - enquiries and visitors", "🛎", [
        ("inbox.Enquiry", "Enquiries", "📨", "Every email and website message, its topic, agent and replies."),
        ("inbox.Queue", "Enquiry topics", "🗂", "General, membership, services... which words send an enquiry where, and who answers."),
        ("inbox.MailSettings", "Mail settings", "✉️", "The enquiries mailbox, how replies are sent, sender name, official copies (CC)."),
        ("visitors.Visit", "Visitors", "🚪", "The visitors registry: who came, when, to see whom."),
        ("visitors.VisitPurpose", "Visit purposes", "🏷", "Choices offered at check-in."),
    ]),
    ("Screens", "📺", [
        ("screens.Screen", "Screens", "📺", "Each TV: its address, who may control it, and whether it is online."),
    ]),
    ("Media library", "🎞", [
        ("library.MediaItem", "Media files", "🎬", "Videos, music and photos. Approve agents' uploads and set their order here."),
        ("library.Playlist", "Playlists", "📋", "Ordered lists of approved files that agents can play."),
    ]),
    ("What the screen shows", "🖥", [
        ("core.DisplaySettings", "Display settings", "⚙️", "Names, logo, welcome text, prayer times, sea point and limits, contact details."),
        ("core.TickerMessage", "Ticker messages", "📣", "Your own announcements in the scrolling bar at the bottom."),
        ("core.NewsFeed", "News feeds", "📰", "RSS feeds for the news box and ticker, tried in order."),
    ]),
    ("People and security", "🔐", [
        ("auth.User", "Users", "👤", "Roles are groups: Admins (also tick Staff), Secretaries, Reception, Customer care."),
        ("auth.Group", "Roles", "👥", "What each role may do. Reception = TVs, uploads, visitors; Customer care = enquiries."),
        ("people.AgentProfile", "Agent profiles", "🪪", "The name customers see in email replies, job title, extension."),
        ("core.NetworkSettings", "Network settings", "🌐", "Port, office IP addresses and Cloudflare Tunnel names people use."),
        ("core.ThemeSettings", "Dashboard theme", "🎨", "Colours, font and name of the desk dashboard."),
        ("audit.AuditLog", "Logs", "🧾", "Every login, visit, change, upload, review and play action, with IP address. Read-only."),
    ]),
]


def _flatten(app_list):
    """{"app_label.ObjectName": model dict from Django's app list}"""
    return {f"{app['app_label']}.{m['object_name']}": m for app in app_list for m in app["models"]}


def dashboard_context(request, app_list):
    from screens.models import Screen
    available = _flatten(app_list)
    counts = _counts()

    groups, used = [], set()
    for title, icon, items in GROUPS:
        rows = []
        for key, label, item_icon, desc in items:
            used.add(key)
            m = available.get(key)
            if not m:
                continue
            rows.append({"label": label, "icon": item_icon, "desc": desc,
                         "url": m.get("admin_url"), "add_url": m.get("add_url"), "badge": counts.get(key)})
        if rows:
            groups.append({"title": title, "icon": icon, "items": rows})

    other = [{"label": m["name"], "icon": "•", "desc": "", "url": m.get("admin_url"),
              "add_url": m.get("add_url"), "badge": None}
             for key, m in available.items() if key not in used]
    if other:
        groups.append({"title": "Other", "icon": "📦", "items": other})

    return {"fd_groups": groups, "fd_stats": _stats(available), "fd_quick": _quick(available),
            "fd_screens": list(Screen.objects.filter(is_active=True))}


def _counts():
    from inbox.models import Enquiry
    from library.models import MediaItem
    from visitors.models import Visit
    waiting = MediaItem.objects.filter(status="pending").count()
    untaken = Enquiry.objects.filter(assigned_to__isnull=True).exclude(status="closed").count()
    inside = Visit.objects.filter(checked_out_at__isnull=True).count()
    return {"library.MediaItem": {"n": waiting, "text": "waiting", "alert": True} if waiting else None,
            "inbox.Enquiry": {"n": untaken, "text": "not taken", "alert": True} if untaken else None,
            "visitors.Visit": {"n": inside, "text": "inside now"} if inside else None}


def _stats(available):
    from audit.models import AuditLog
    from library.models import MediaItem
    from screens.models import Screen

    now = timezone.now()
    start_today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    stats = []
    if "library.MediaItem" in available:
        url = available["library.MediaItem"]["admin_url"]
        waiting = MediaItem.objects.filter(status="pending").count()
        stats.append({"label": "Uploads waiting for review", "value": waiting,
                      "url": url + "?status__exact=pending", "alert": bool(waiting)})
        approved = MediaItem.objects.filter(status="approved")
        stats.append({"label": "Videos ready", "value": approved.filter(kind="video").count(),
                      "url": url + "?status__exact=approved&kind__exact=video"})
        stats.append({"label": "Music tracks ready", "value": approved.filter(kind="audio").count(),
                      "url": url + "?status__exact=approved&kind__exact=audio"})
    if "screens.Screen" in available:
        screens = list(Screen.objects.filter(is_active=True))
        online = sum(s.is_online for s in screens)
        stats.append({"label": "Screens online", "value": f"{online} / {len(screens)}",
                      "url": available["screens.Screen"]["admin_url"], "alert": online < len(screens)})
    if "audit.AuditLog" in available:
        actions = AuditLog.objects.filter(event_type="agent_action", timestamp__gte=start_today).count()
        stats.append({"label": "Agent actions today", "value": actions,
                      "url": available["audit.AuditLog"]["admin_url"] + "?event_type__exact=agent_action"})
        fails = AuditLog.objects.filter(event_type="login_fail", timestamp__gte=now - timedelta(days=1)).count()
        if fails:
            stats.append({"label": "Failed logins (24 h)", "value": fails, "alert": True,
                          "url": available["audit.AuditLog"]["admin_url"] + "?event_type__exact=login_fail"})
    return stats


def _quick(available):
    quick = []
    if "library.MediaItem" in available:
        quick.append({"label": "Review uploads", "url": available["library.MediaItem"]["admin_url"] + "?status__exact=pending"})
    for key, label in (("library.MediaItem", "＋ Add media"), ("library.Playlist", "＋ Add playlist"),
                       ("screens.Screen", "＋ Add screen")):
        if available.get(key, {}).get("add_url"):
            quick.append({"label": label, "url": available[key]["add_url"]})
    quick.append({"label": "Open agent panel", "url": _url("agent:home") + "?all=1"})
    return quick


def _url(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return "#"
