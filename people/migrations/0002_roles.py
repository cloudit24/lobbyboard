"""The four roles, starter enquiry topics and visit purposes. All editable
afterwards (admin panel; secretaries manage agents in the desk dashboard)."""
from django.contrib.auth.management import create_permissions
from django.db import migrations

RECEPTION = [("screens", "control_screen"), ("screens", "view_screen"), ("library", "upload_media"),
             ("library", "view_mediaitem"), ("library", "view_playlist"), ("visitors", "register_visitor")]
CUSTOMER_CARE = [("inbox", "handle_enquiries")]
SECRETARY = RECEPTION + CUSTOMER_CARE + [("people", "secretary_desk")]

TOPICS = [  # name, keywords, default
    ("Membership", "membership\nmember\nعضوية\nعضو", False),
    ("Services and trading", "service request\nservice\ntrading\nquotation\nخدمة\nطلب خدمة\nتجارة", False),
    ("General enquiries", "", True),
]
PURPOSES = ["Enquiry", "Membership", "Meeting", "Delivery", "Service request", "Other"]


def perms(Permission, pairs):
    return [p for app, code in pairs
            for p in [Permission.objects.filter(content_type__app_label=app, codename=code).first()] if p]


def forwards(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    # The old single "Agents" group becomes Reception.
    old = Group.objects.filter(name="Agents").first()
    if old and not Group.objects.filter(name="Reception").exists():
        old.name = "Reception"
        old.save()
    for name, pairs in (("Reception", RECEPTION), ("Customer care", CUSTOMER_CARE), ("Secretaries", SECRETARY)):
        g, _ = Group.objects.get_or_create(name=name)
        g.permissions.add(*perms(Permission, pairs))
    admins, _ = Group.objects.get_or_create(name="Admins")
    admins.permissions.add(*Permission.objects.all())

    Queue = apps.get_model("inbox", "Queue")
    if not Queue.objects.exists():
        for order, (name, kw, default) in enumerate(TOPICS, start=1):
            Queue.objects.create(name=name, keywords=kw, is_default=default, order=order)
    VisitPurpose = apps.get_model("visitors", "VisitPurpose")
    if not VisitPurpose.objects.exists():
        for order, name in enumerate(PURPOSES, start=1):
            VisitPurpose.objects.create(name=name, order=order)


class Migration(migrations.Migration):
    dependencies = [
        ("people", "0001_initial"),
        ("inbox", "0001_initial"),
        ("visitors", "0001_initial"),
        ("screens", "0002_starter_data"),
        ("core", "0001_initial"),
        ("audit", "0001_initial"),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
