from django import forms
from django.contrib.auth import get_user_model

# get_user_model() = always returns the correct User model
# whether default Django User or your custom one
# NEVER import User directly — always use this
User = get_user_model()

class LoginForm(forms.Form):
    """
    REUSE: works with any User model that has email + password.
    Change 'email' to 'username' if your model uses username instead.
    """
    email    = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'your@email.com'}),
        label='Email'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password'}),
        label='Password'
    )

class RegisterForm(forms.Form):
    """
    REUSE: add or remove fields to match your User model.
    Validation runs automatically via clean().
    """
    email      = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'your@email.com'})
    )
    first_name = forms.CharField(max_length=30)
    last_name  = forms.CharField(max_length=30)
    password1  = forms.CharField(
        widget=forms.PasswordInput,
        label='Password'
    )
    password2  = forms.CharField(
        widget=forms.PasswordInput,
        label='Confirm Password'
    )

    def clean_email(self):
        # called automatically by is_valid()
        # validates this one field independently
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already registered')
        return email

    def clean(self):
        # called automatically after all field validation
        # use for validation that spans multiple fields
        cleaned  = super().clean()
        p1       = cleaned.get('password1')
        p2       = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match')
        return cleaned