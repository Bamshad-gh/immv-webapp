# groups/forms.py
# ─────────────────────────────────────────────────────────────
# What's in this file (in order):
#   1. GroupCreateForm    — create a group + its type-specific extra info
#   2. AddMemberForm      — add an existing user to a group with a role
#   3. ManagedProfileForm — create an interior person (no account needed)
#
# Case assignment, bulk assignment, and managed-profile linking are
# ADMIN PANEL operations — see admin_panel/forms.py for those forms.
#
# All forms validate in clean() and never trust raw POST data.
# ─────────────────────────────────────────────────────────────

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Group, GroupMembership, Role, FamilyInfo, BusinessInfo
from users.models import ManagedProfile

User = get_user_model()


# ── 1. GROUP CREATE FORM ──────────────────────────────────────
# Creates a Group + its type-specific extra info (FamilyInfo or BusinessInfo)
# in one form submission.
#
# Key patterns:
#   - Extra fields declared on the form (not the model) for type-specific data
#   - __init__ receives current user so clean() can enforce group type limits
#   - clean() handles cross-field validation (limits + required fields per type)
#   - save() creates both Group and the related info object
#
# CUSTOMIZE: update limits dict to match your group type rules.
# EXPAND: add a new elif block in clean() and save() for each new group type.

class GroupCreateForm(forms.ModelForm):

    # Extra fields — shown/hidden in template based on selected type
    # EXPAND: add fields here for each new group type that needs extra data
    family_name     = forms.CharField(max_length=100, required=False)
    company_name    = forms.CharField(max_length=100, required=False)
    business_number = forms.CharField(max_length=50,  required=False)

    class Meta:
        model  = Group
        fields = ['name', 'type']
        # 'name' and 'type' come from Group model
        # extra fields above are handled manually in save()

    def __init__(self, *args, user=None, **kwargs):
        """
        Pass the current user in so clean() can check how many groups they own.
        Usage in view: GroupCreateForm(request.POST, user=request.user)
        """
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        """
        Cross-field validation — runs after all individual field checks pass.
        Enforces: group type ownership limits + required extra fields per type.
        """
        cleaned_data = super().clean()
        group_type   = cleaned_data.get('type')

        if not group_type or not self.user:
            return cleaned_data

        # ── Ownership limits per group type ───────────────────
        # CUSTOMIZE: change these numbers to match your business rules
        limits = {
            'family':   1,
            'business': 1,
            'friends':  1,
            'other':    3,
        }
        existing    = Group.objects.filter(
            created_by=self.user,
            type=group_type,
            is_active=True
        )
        max_allowed = limits.get(group_type, 1)

        if existing.count() >= max_allowed:
            raise ValidationError(
                f'You already have the maximum number of {group_type} groups ({max_allowed}).'
            )

        # ── Required extra fields per type ────────────────────
        # EXPAND: add an elif block here for each new group type
        if group_type == 'family':
            if not cleaned_data.get('family_name'):
                self.add_error('family_name', 'Family name is required for family groups.')

        elif group_type == 'business':
            if not cleaned_data.get('company_name'):
                self.add_error('company_name', 'Company name is required.')
            if not cleaned_data.get('business_number'):
                self.add_error('business_number', 'Business number is required.')

        return cleaned_data

    def save(self, commit=True):
        """
        Saves the Group first, then creates the matching extra info object.
        Called in the view AFTER group.created_by is set manually.
        EXPAND: add elif blocks here for each new group type.
        """
        group      = super().save(commit=commit)
        group_type = self.cleaned_data['type']

        if group_type == 'family':
            FamilyInfo.objects.create(
                group=group,
                family_name=self.cleaned_data['family_name'],
            )
        elif group_type == 'business':
            BusinessInfo.objects.create(
                group=group,
                company_name=self.cleaned_data['company_name'],
                business_number=self.cleaned_data['business_number'],
            )

        return group


# ── 2. ADD MEMBER FORM ────────────────────────────────────────
# Adds an existing registered user to a group with an optional role.
# Looks up user by email (since our User model uses email-based login).
#
# CUSTOMIZE: change the lookup field if your project uses username instead.
# EXPAND: add a 'permissions' MultipleChoiceField if you want to assign
#         permissions at the same time as adding the member.

class AddMemberForm(forms.Form):

    email = forms.EmailField(
        label='User Email',
        widget=forms.EmailInput(attrs={'placeholder': 'member@email.com'})
    )
    role = forms.ModelChoiceField(
        queryset=Role.objects.none(),  # empty default — filled in __init__
        required=False,
        empty_label='No role assigned',
    )

    def __init__(self, *args, group=None, **kwargs):
        """
        Pass the group in so we can:
          1. Filter roles to only show roles for this group's type
          2. Check if user is already a member in clean()
        Usage in view: AddMemberForm(request.POST, group=group)
        """
        super().__init__(*args, **kwargs)
        self.group = group
        if group:
            # only show roles relevant to this group's type
            self.fields['role'].queryset = Role.objects.filter(group_type=group.type)

    def clean_email(self):
        """
        Validates:
          1. A user with this email actually exists
          2. They are not already a member of this group
        Stores the found User object on self.cleaned_user for the view to use.
        """
        email = self.cleaned_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError(f'No account found with email: {email}')

        if self.group:
            already_member = GroupMembership.objects.filter(
                user=user,
                group=self.group
            ).exists()
            if already_member:
                raise ValidationError(f'{email} is already a member of this group.')

        self.cleaned_user = user  # stored here — accessed in view as form.cleaned_user
        return email


# ── 3. MANAGED PROFILE FORM ───────────────────────────────────
# Creates a ManagedProfile — an interior person with no account.
# Example: a user creates a profile for their elderly parent.
#
# Note: 'created_by' and 'group' are NOT in the form fields —
# they are set manually in the view (same pattern as Group.created_by).
#
# CUSTOMIZE: update fields list to match what your project collects.
# EXPAND: add a 'relationship' field (e.g., "mother", "employee") if needed.

class ManagedProfileForm(forms.ModelForm):
    """
    Creates a ManagedProfile (interior person, no login account).
    Two group assignment modes:
      1. Default: person joins the group from the URL.
      2. new_group_name filled → a new dedicated group is created for this person.
    'created_by' and 'group' are set in the view.

    CUSTOMIZE: update fields list to match what your project collects.
    EXPAND: add a 'relationship' field (e.g., "mother", "employee") if needed.
    """

    # Optional: create a brand-new group just for this interior person
    # WHY non-model? No DB column — purely a creation-time convenience handled in view.
    new_group_name = forms.CharField(
        required  = False,
        label     = 'Create a dedicated group for this person (optional)',
        help_text = 'Leave blank to add this person to the current group. '
                    'Fill in a name to create a new group exclusively for them.',
        widget    = forms.TextInput(attrs={'placeholder': 'e.g. Doe Family File'}),
    )

    class Meta:
        model  = ManagedProfile
        fields = [
            'first_name',
            'last_name',
            'date_of_birth',
            'gender',
            'country_of_birth',
            'city_of_birth',
            'passport_number',
            'passport_picture',
            'profile_picture',
            # CUSTOMIZE: include only the PersonalInfo fields your project uses
        ]
        widgets = {
            # date input renders as a proper date picker in the browser
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        """
        Add cross-field validation here if needed.
        Example: require passport_number if passport_picture is uploaded.
        """
        cleaned_data = super().clean()
        # EXPAND: add validation logic here as your requirements grow
        return cleaned_data