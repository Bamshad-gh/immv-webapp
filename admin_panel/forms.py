# admin_panel/forms.py
# ─────────────────────────────────────────────────────────────
# What's in this file (in order):
#   1. AdminLoginForm          — staff login form
#   2. CreateUserForm          — admin creates a new user account
#   3. CreateAdminForm         — superadmin creates a new admin + sets permissions
#   4. CreateCaseForm          — admin creates a case for a specific user
#                                Service → Category → Subcategory filtered chain
#   5. AdminGroupCreateForm    — admin creates a group + picks owner
#   6. AdminAddMemberForm      — admin adds user to group with optional role
#   7. AdminAssignCaseForm     — admin picks a category to create a Case
#                                (reused for member cases + managed profile cases + bulk)
#   8. AdminLinkManagedForm    — admin links a ManagedProfile to an existing User account
#   9. AdminManagedProfileForm — admin creates an interior person (no account)
# ─────────────────────────────────────────────────────────────

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from cases.models import Case, Service, Category
from users.models import AdminProfile
from groups.models import Group, GroupMembership, Role, FamilyInfo, BusinessInfo


User = get_user_model()


# ── 1. ADMIN LOGIN FORM ───────────────────────────────────────

class AdminLoginForm(forms.Form):
    """Simple login form for the admin panel."""
    email    = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'admin@email.com'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password'})
    )


# ── 2. CREATE USER FORM ───────────────────────────────────────
# Admin creates a new regular user account.
# CUSTOMIZE: add/remove fields to match your User model.

class CreateUserForm(forms.Form):
    """
    Admin creates a new user account.
    Validates email uniqueness and password match.
    """
    email      = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name  = forms.CharField(max_length=30)
    phone      = forms.CharField(max_length=20, required=False)
    password1  = forms.CharField(widget=forms.PasswordInput, label='Password')
    password2  = forms.CharField(widget=forms.PasswordInput, label='Confirm Password')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError('Passwords do not match.')
        return cleaned_data

    def save(self):
        """Creates and returns the new User."""
        return User.objects.create_user(
            email      = self.cleaned_data['email'],
            password   = self.cleaned_data['password1'],
            first_name = self.cleaned_data['first_name'],
            last_name  = self.cleaned_data['last_name'],
            phone      = self.cleaned_data.get('phone', ''),
        )


# ── 3. CREATE ADMIN FORM ──────────────────────────────────────
# Superadmin creates a new admin and sets their permissions.
# Only superadmins can access the view that uses this form.
#
# EXPAND: add new permission fields here when new AdminProfile booleans are added.

class CreateAdminForm(forms.Form):
    """
    Superadmin creates a staff user + AdminProfile in one form.
    Permissions default to False — superadmin explicitly grants each one.
    """
    email      = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name  = forms.CharField(max_length=30)
    password1  = forms.CharField(widget=forms.PasswordInput, label='Password')
    password2  = forms.CharField(widget=forms.PasswordInput, label='Confirm Password')

    # Permission checkboxes — map directly to AdminProfile boolean fields
    # EXPAND: add a checkbox here for each new AdminProfile boolean
    can_create_groups   = forms.BooleanField(required=False)
    can_assign_members  = forms.BooleanField(required=False)
    can_view_all_cases  = forms.BooleanField(required=False)
    can_create_users    = forms.BooleanField(required=False)
    can_manage_roles    = forms.BooleanField(required=False)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError('Passwords do not match.')
        return cleaned_data

    def save(self, created_by):
        """
        Creates the User (is_staff=True) + AdminProfile with selected permissions.
        created_by = the superadmin performing the action (for audit trail).
        """
        user = User.objects.create_user(
            email      = self.cleaned_data['email'],
            password   = self.cleaned_data['password1'],
            first_name = self.cleaned_data['first_name'],
            last_name  = self.cleaned_data['last_name'],
        )
        user.is_staff = True
        user.save()

        # Create AdminProfile with exactly the permissions that were checked
        # EXPAND: add each new permission field here
        AdminProfile.objects.create(
            user               = user,
            created_by         = created_by,
            can_create_groups  = self.cleaned_data.get('can_create_groups',  False),
            can_assign_members = self.cleaned_data.get('can_assign_members', False),
            can_view_all_cases = self.cleaned_data.get('can_view_all_cases', False),
            can_create_users   = self.cleaned_data.get('can_create_users',   False),
            can_manage_roles   = self.cleaned_data.get('can_manage_roles',   False),
        )
        return user


# ── 4. CREATE CASE FORM ───────────────────────────────────────
# Admin creates a case for a specific user.
# Service → Category → Subcategory filtered chain.
#
# How the filtered chain works:
#   - On page load: category and subcategory querysets are empty
#   - JavaScript sends AJAX requests as admin selects each level
#   - Views return filtered JSON (see admin_panel/views.py get_categories, get_subcategories)
#   - JavaScript populates the next dropdown from the JSON response
#
# Why not just show all categories in one dropdown?
#   Your Category model supports nesting (parent FK).
#   Showing all at once is confusing — the chain makes the relationship clear.
#
# CUSTOMIZE: add 'group' or 'managed_profile' fields if admin should be able
#            to assign cases to groups or managed profiles too.

class CreateCaseForm(forms.Form):
    """
    Admin creates a case for a specific user.
    Category chain is infinite depth — handled via AJAX in the template.
    JavaScript sets the hidden 'category' field to the deepest selected category.

    CUSTOMIZE: add 'group' or 'managed_profile' fields if admin should be able
               to assign cases to groups or managed profiles too.
    """

    user_email = forms.EmailField(
        label='User Email',
        widget=forms.EmailInput(attrs={'placeholder': 'user@email.com'})
    )

    service = forms.ModelChoiceField(
        queryset=Service.objects.filter(is_active=True),
        empty_label='Select a service...',
    )

    # Hidden field — set by JavaScript to the deepest selected category
    # IntegerField so Django accepts a plain integer from POST
    category = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False
    )

    # Keep this for form compatibility but not used — chain replaces it
    subcategory = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False
    )

    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label='Admin Notes',
    )

    def clean_user_email(self):
        """Validates the user exists and stores them for save()."""
        email = self.cleaned_data.get('user_email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError(f'No user found with email: {email}')
        self.cleaned_user = user
        return email

    def clean(self):
        """
        Reads category id from raw POST data — not from cleaned_data.
        Why self.data and not cleaned_data?
          cleaned_data goes through field validation which requires=False
          lets None through. self.data is the raw POST — has the actual value.
        """
        cleaned_data = super().clean()

        category_id = self.data.get('final_category')


        if not category_id:
            raise ValidationError('Please select a category.')

        try:
            self.final_category = Category.objects.get(
                id=int(category_id),
                is_active=True
            )
        except (Category.DoesNotExist, ValueError):
            raise ValidationError('Invalid category selected.')

        return cleaned_data

    def save(self, created_by):
        """
        Creates and returns the Case.
        case.user = the target user (not the admin doing the creating).
        """
        return Case.objects.create(
            user     = self.cleaned_user,
            category = self.final_category,
            notes    = self.cleaned_data.get('notes', ''),
            status   = 'pending',
        )
        
# Add these two forms to admin_panel/forms.py
# They handle group creation and member assignment from the admin panel.



class AdminGroupCreateForm(forms.Form):
    """
    Admin creates a group and picks a user as the owner.
    Owner is auto-added as first member with full permissions.

    CUSTOMIZE: add or remove group type choices to match your domain.
    EXPAND: add a new XxxInfo block in save() for each new group type.
    """
    name  = forms.CharField(max_length=100)
    type  = forms.ChoiceField(choices=Group.GROUP_TYPES)

    # Owner — admin picks any existing user by email
    owner_email = forms.EmailField(
        label='Owner Email',
        help_text='This user will be added as the group owner.'
    )

    # Family-specific fields
    family_name = forms.CharField(max_length=100, required=False)

    # Business-specific fields
    company_name    = forms.CharField(max_length=100, required=False)
    business_number = forms.CharField(max_length=50,  required=False)

    # EXPAND: add fields for new group types here

    def clean_owner_email(self):
        email = self.cleaned_data.get('owner_email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError(f'No user found with email: {email}')
        self.cleaned_owner = user  # stored for use in save()
        return email

    def clean(self):
        cleaned_data = super().clean()
        group_type   = cleaned_data.get('type')

        if group_type == 'family' and not cleaned_data.get('family_name'):
            raise ValidationError('Family name is required for family groups.')
        if group_type == 'business' and not cleaned_data.get('company_name'):
            raise ValidationError('Company name is required for business groups.')
        return cleaned_data

    def save(self, created_by):
        """
        Creates Group + type-specific info + owner membership.
        created_by = the admin performing the action (stored on group.created_by).
        """
        group = Group.objects.create(
            name       = self.cleaned_data['name'],
            type       = self.cleaned_data['type'],
            created_by = created_by,
        )

        # Create type-specific info
        # EXPAND: add elif block for each new group type
        if group.type == 'family':
            FamilyInfo.objects.create(
                group       = group,
                family_name = self.cleaned_data['family_name'],
            )
        elif group.type == 'business':
            BusinessInfo.objects.create(
                group           = group,
                company_name    = self.cleaned_data['company_name'],
                business_number = self.cleaned_data.get('business_number', ''),
            )

        # Add owner as first member
        # Owner gets no specific role initially — admin can assign later
        GroupMembership.objects.create(
            user      = self.cleaned_owner,
            group     = group,
            is_active = True,
        )

        return group


class AdminAddMemberForm(forms.Form):
    """
    Admin adds a user to an existing group with optional role.
    EXPAND: add a permissions field to assign GroupPermissions at the same time.
    """
    email = forms.EmailField(label='User Email')
    role  = forms.ModelChoiceField(
        queryset=Role.objects.none(),  # populated in __init__ based on group type
        required=False,
        empty_label='No role'
    )

    def __init__(self, group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        # Only show roles that match this group's type
        self.fields['role'].queryset = Role.objects.filter(group_type=group.type)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError(f'No user found with email: {email}')
        if GroupMembership.objects.filter(user=user, group=self.group).exists():
            raise ValidationError('This user is already a member of this group.')
        self.cleaned_user = user
        return email

    def save(self):
        return GroupMembership.objects.create(
            user      = self.cleaned_user,
            group     = self.group,
            role      = self.cleaned_data.get('role'),
            is_active = True,
        )


# ── 7. ADMIN ASSIGN CASE FORM ─────────────────────────────────
# Lets the admin pick a Category to create a new Case.
# Used by three views:
#   - admin_assign_case_to_member    → Case for a real group member
#   - admin_create_case_for_managed  → Case for a managed profile
#   - admin_assign_category_to_group → bulk: one Case per member + managed profile
#
# WHY lazy import inside __init__?
#   Category is in the 'cases' app. Importing at module level causes circular
#   import errors during Django startup. __init__ runs at request time — safe.
#
# EXPAND: add a 'notes' TextField for creation-time admin notes on the case.

class AdminAssignCaseForm(forms.Form):

    category = forms.ModelChoiceField(
        # queryset=None placeholder — replaced in __init__ via lazy import
        queryset=None,
        label='Service Category',
        empty_label='— Select a category —',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from cases.models import Category as Cat
        # select_related('service') avoids N+1 when the dropdown renders option labels
        self.fields['category'].queryset = (
            Cat.objects
            .filter(is_active=True)
            .select_related('service')
            .order_by('service__name', 'name')
        )


# ── 8. ADMIN LINK MANAGED FORM ────────────────────────────────
# Admin links a ManagedProfile (interior person, no account) to an
# existing User account — used when the person later registers.
#
# After linking:
#   managed_profile.linked_user → their User account
#   user.managed_account        → the ManagedProfile (reverse OneToOne)
#
# Two validations:
#   1. Email must belong to a registered User
#   2. That User must not already be linked to a DIFFERENT managed profile
#
# EXPAND: add a 'confirm' BooleanField for audit trails.

class AdminLinkManagedForm(forms.Form):

    email = forms.EmailField(
        label='User Email',
        widget=forms.EmailInput(attrs={'placeholder': 'their@email.com'}),
        help_text='Enter the email of the user account to link to this profile.',
    )

    def clean_email(self):
        """
        Looks up the User and stores them on self.cleaned_user so the view
        can access the User object without a second DB query.
        """
        email = self.cleaned_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError(f'No account found with email: {email}')

        # hasattr handles RelatedObjectDoesNotExist — a subclass of AttributeError.
        # If it doesn't exist the user has no linked managed profile → safe to link.
        if hasattr(user, 'managed_account') and user.managed_account is not None:
            raise ValidationError(f'{email} is already linked to another managed profile.')

        self.cleaned_user = user   # accessed in view as form.cleaned_user
        return email


# ── 9. ADMIN MANAGED PROFILE FORM ────────────────────────────
# Admin creates an interior person (ManagedProfile) for a group.
# The person has no account — admin manages them directly.
# 'created_by' and 'group' are set in the view, not in this form.
#
# CUSTOMIZE: add or remove PersonalInfo fields to match your project.
# EXPAND: add a 'relationship' field (e.g., "mother", "employee") if needed.

from users.models import ManagedProfile

class AdminManagedProfileForm(forms.ModelForm):
    """
    Creates a ManagedProfile (interior person, no login account).
    The 'group' assignment is handled in TWO ways:
      1. Default: the profile joins the group provided in the URL (group_id).
      2. Optional override: admin fills 'new_group_name' → a brand-new group is
         created exclusively for this person (their own "file").
    'created_by' and 'group' are always set in the view, not here.

    CUSTOMIZE: add/remove PersonalInfo fields to match your project.
    EXPAND: add a 'relationship' field (e.g. "mother", "employee") if needed.
    """

    # Extra non-model field — if filled, creates a new group for this interior person
    # instead of adding them to the URL's existing group.
    # WHY non-model? ManagedProfile has no 'new_group_name' DB column — this is
    # purely a creation-time convenience field handled in the view.
    new_group_name = forms.CharField(
        required  = False,
        label     = 'Create a dedicated group for this person (optional)',
        help_text = 'Leave blank to add this person to the current group. '
                    'Enter a name (e.g. "Doe Family File") to create a new group just for them.',
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
            # CUSTOMIZE: add/remove fields here to match your PersonalInfo fields
        ]
        widgets = {
            # Renders as a date picker in supporting browsers
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }
