from django import forms
from django.conf import settings


class LegalSignupForm(forms.Form):
    secret_code = forms.CharField(
        max_length=100,
        label="Secret Code",
        widget=forms.PasswordInput(attrs={"placeholder": "Secret Code"}),
    )

    def clean_secret_code(self):
        code = self.cleaned_data.get("secret_code", "")
        signup_secret_required = getattr(settings, "SIGNUP_SECRET_CODE", "")
        if code != signup_secret_required:
            raise forms.ValidationError("Invalid secret code.")
        return code

    def signup(self, request, user):
        pass
