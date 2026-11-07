from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

# The four roles. Each is a permission group (made by a migration); a person's
# role = the groups they are in. Admins also need "Staff status" to open /admin/.
ROLE_ADMIN = "Admins"
ROLE_SECRETARY = "Secretaries"
ROLE_RECEPTION = "Reception"          # TVs, uploads, visitors registry
ROLE_CUSTOMER_CARE = "Customer care"  # enquiries inbox
AGENT_ROLES = [ROLE_RECEPTION, ROLE_CUSTOMER_CARE]  # what a secretary may hand out


class AgentProfile(models.Model):
    """Extra details for a person who works in the desk dashboard."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(
        "Name customers see", max_length=100, blank=True,
        help_text="Used in email replies, e.g. “Mariam” → “Customer Care – Mariam”. Blank = first name.")
    job_title = models.CharField(max_length=100, blank=True)
    extension = models.CharField("Phone extension", max_length=20, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Agent profile"
        permissions = [
            ("secretary_desk", "Can use the secretary pages (all enquiries and visitors, agents, reports)"),
        ]

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.display_name or self.user.first_name or self.user.get_username()


def profile_of(user):
    return AgentProfile.objects.get_or_create(user=user)[0]


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name=ROLE_ADMIN).exists())


def is_secretary(user):
    return user.is_authenticated and (user.is_superuser or user.has_perm("people.secretary_desk"))


def roles_of(user):
    if user.is_superuser:
        return [ROLE_ADMIN]
    return list(user.groups.values_list("name", flat=True))
