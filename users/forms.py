from django import forms    # This module contains everything needed to 
                            # build, validate, and render forms.

class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)




# Registration form
class RegisterForm(forms.Form):
    email      = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name  = forms.CharField(max_length=30)
    password1  = forms.CharField(widget=forms.PasswordInput, label='Password')
    password2  = forms.CharField(widget=forms.PasswordInput, label='Confirm Password')
 
    def clean(self):
        # clean() = custom validation across multiple fields
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match')
        return cleaned