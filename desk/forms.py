from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password

from inbox.models import Enquiry, Queue
from people.models import AGENT_ROLES
from screens.models import Screen
from visitors.models import Visit, VisitPurpose


class VisitForm(forms.ModelForm):
    class Meta:
        model = Visit
        fields = ["name", "phone", "email", "company", "purpose", "meeting_with", "people_count", "badge",
                  "id_number", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purpose"].queryset = VisitPurpose.objects.filter(is_active=True)


class ReplyForm(forms.Form):
    body = forms.CharField(label="Your reply", widget=forms.Textarea(attrs={"rows": 7}))
    extra_cc = forms.CharField(label="Also copy (CC)", required=False,
                               help_text="Optional, comma separated. Official addresses are copied automatically.")


class NoteForm(forms.Form):
    note = forms.CharField(label="Internal note (the customer doesn't see it)", widget=forms.Textarea(attrs={"rows": 3}))


class NewEnquiryForm(forms.ModelForm):
    message = forms.CharField(label="What they asked", widget=forms.Textarea(attrs={"rows": 5}))

    class Meta:
        model = Enquiry
        fields = ["source", "queue", "subject", "customer_name", "customer_email", "customer_phone"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["queue"].queryset = Queue.objects.filter(is_active=True)
        self.fields["source"].initial = "phone"


class AgentForm(forms.Form):
    """What a secretary may set for an agent. Admin and secretary roles are
    given only in the admin panel."""

    username = forms.SlugField(max_length=150, help_text="For logging in. Letters, numbers, dashes.")
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False, help_text="For new-enquiry alerts.")
    display_name = forms.CharField(label="Name customers see", max_length=100, required=False,
                                   help_text="In email replies: “Customer Care – <this>”. Blank = first name.")
    job_title = forms.CharField(max_length=100, required=False)
    roles = forms.ModelMultipleChoiceField(queryset=Group.objects.none(), widget=forms.CheckboxSelectMultiple,
                                           required=False,
                                           help_text="Reception = TVs, uploads, visitors. Customer care = enquiries.")
    queues = forms.ModelMultipleChoiceField(label="Enquiry topics", queryset=Queue.objects.none(),
                                            widget=forms.CheckboxSelectMultiple, required=False)
    screens = forms.ModelMultipleChoiceField(label="TVs", queryset=Screen.objects.none(),
                                             widget=forms.CheckboxSelectMultiple, required=False,
                                             help_text="Only matters when a TV is limited to chosen agents.")
    is_active = forms.BooleanField(label="Can log in", required=False, initial=True)
    password = forms.CharField(label="New password", required=False, widget=forms.PasswordInput,
                               help_text="Leave blank to keep the current one.")

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["roles"].queryset = Group.objects.filter(name__in=AGENT_ROLES)
        self.fields["queues"].queryset = Queue.objects.filter(is_active=True)
        self.fields["screens"].queryset = Screen.objects.filter(is_active=True)
        if user is None:
            self.fields["password"].required = True
            self.fields["password"].help_text = "They can change it later."

    def clean_username(self):
        name = self.cleaned_data["username"]
        qs = User.objects.filter(username__iexact=name)
        if self.user:
            qs = qs.exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("That username is taken.")
        return name

    def clean_password(self):
        pw = self.cleaned_data.get("password")
        if pw:
            validate_password(pw, self.user)
        return pw
