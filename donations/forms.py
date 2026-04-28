from django import forms
from django.core.validators import RegexValidator
from django.db.utils import OperationalError, ProgrammingError

from .models import Donation, Site

_phone_validator = RegexValidator(
    regex=r'^\+?[\d\s()\-\.]{7,20}$',
    message="Enter a valid phone number (e.g. 555-123-4567 or (555) 867-5309).",
)



class DonationForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        num_bags = cleaned_data.get("num_bags")
        num_boxes = cleaned_data.get("num_boxes")
        cash_check = cleaned_data.get("cash_check")
        gift_cards = cleaned_data.get("gift_cards")
        other_donation = cleaned_data.get("other_donation")
        if not (num_bags or num_boxes or cash_check or gift_cards or (other_donation and other_donation.strip())):
            raise forms.ValidationError(
                "At least one of the following fields must be filled: # of Bags, # of Boxes, Cash/Check $, Gift Cards $, Other Donation."
            )
        return cleaned_data
    donor_type = forms.ChoiceField(
        choices=[
            ("Anonymous", "Anonymous"),
            ("Civic", "Civic"),
            ("Religious", "Religious"),
            ("Corporate", "Corporate"),
            ("Individual", "Individual"),
        ],
        widget=forms.Select,
        initial="Individual",
    )

    class Meta:
        model = Donation
        fields = [
            "donation_date",
            "donor_name",
            "donor_type",
            "organization",
            "email",
            "phone_number",
            "address",
            "num_bags",
            "num_boxes",
            "cash_check",
            "gift_cards",
            "other_donation",
            "total_weight",
            "notes",
            "opt_in_email",
        ]
        widgets = {
            "donation_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 'site' is no longer a form field; no need to set queryset or help_text

        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")
            field.widget.attrs.setdefault("autocomplete", "off")

        self.fields["notes"].required = False
        self.fields["donor_name"].required = False
        self.fields["donor_type"].required = False
        self.fields["email"].required = False
        self.fields["phone_number"].required = False
        self.fields["address"].required = False
        self.fields["num_bags"].required = False
        self.fields["num_boxes"].required = False
        self.fields["cash_check"].required = False
        self.fields["gift_cards"].required = False
        self.fields["other_donation"].required = False
        self.fields["total_weight"].required = False
        self.fields["opt_in_email"].required = False
        self.fields["opt_in_email"].label = "Send confirmation email to donor"
        self.fields["opt_in_email"].widget.attrs.pop("class", None)  # no form-control on checkbox
        self.fields["email"].widget.attrs["pattern"] = r"[^\s@]+@[^\s@]+\.[^\s@]{2,}"
        self.fields["email"].widget.attrs["title"] = "e.g. name@example.com"
        self.fields["phone_number"].validators.append(_phone_validator)
        self.fields["phone_number"].widget.attrs["type"] = "tel"
        self.fields["phone_number"].widget.attrs["pattern"] = r"[\+\d][\d\s()\-\.]{6,19}"
        self.fields["phone_number"].widget.attrs["title"] = "e.g. 555-123-4567 or (555) 867-5309"

