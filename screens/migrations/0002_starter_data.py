"""Starter data so a fresh install works at once: the Agents group with the
right permissions, one screen, and two general news feeds. Everything can be
changed or removed in the admin afterwards."""
from django.contrib.auth.management import create_permissions
from django.db import migrations

AGENT_PERMS = [
    ("screens", "control_screen"), ("screens", "view_screen"),
    ("library", "upload_media"), ("library", "view_mediaitem"), ("library", "view_playlist"),
]
FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
]


def forwards(apps, schema_editor):
    # Custom permissions are normally created after migrations finish; make them now.
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    agents, _ = Group.objects.get_or_create(name="Agents")
    for app_label, codename in AGENT_PERMS:
        perm = Permission.objects.filter(content_type__app_label=app_label, codename=codename).first()
        if perm:
            agents.permissions.add(perm)

    Screen = apps.get_model("screens", "Screen")
    if not Screen.objects.exists():
        Screen.objects.create(name="Reception", slug="reception")

    NewsFeed = apps.get_model("core", "NewsFeed")
    if not NewsFeed.objects.exists():
        for order, (label, url) in enumerate(FEEDS, start=1):
            NewsFeed.objects.create(label=label, url=url, order=order)


class Migration(migrations.Migration):
    dependencies = [
        ("screens", "0001_initial"),
        ("library", "0001_initial"),
        ("core", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
