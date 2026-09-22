from decimal import Decimal, InvalidOperation

from django import forms
from django.core.validators import RegexValidator
from django.db.utils import OperationalError, ProgrammingError

from . import catalog
from .models import Donation, Site

_phone_validator = RegexValidator(
    regex=r'^\+?[\d\s()\-\.]{7,20}$',
    message="Enter a valid phone number (e.g. 555-123-4567 or (555) 867-5309).",
)



class DonationForm(forms.ModelForm):
    """
    The donation's own columns plus any number of priced line items.

    Line items arrive as parallel item_category/item_quantity lists rather
    than a formset: the intake wizard builds them in JavaScript, and a
    formset's management form would be one more thing for that JavaScript to
    keep correct for no gain. They are validated here so both the intake
    wizard and the detail page's AJAX edit get the same rules.
    """

    def _parse_items(self):
        """
        Read item_category/item_quantity off the raw POST data into a list of
        (category, Decimal quantity) pairs, recording a form error for each
        line that doesn't make sense.

        A blank quantity with a blank category is skipped rather than
        rejected -- that is just an empty row the wizard left behind.
        """
        if not self.data:
            return []

        categories = self.data.getlist("item_category")
        quantities = self.data.getlist("item_quantity")
        items = []
        for index, category in enumerate(categories):
            category = (category or "").strip()
            raw_quantity = (quantities[index] if index < len(quantities) else "").strip()
            if not category and not raw_quantity:
                continue
            if category not in catalog.CATALOG:
                self.add_error(None, f"Unknown donation category: {category or '(blank)'}.")
                continue
            try:
                quantity = Decimal(raw_quantity)
            except (InvalidOperation, ValueError):
                self.add_error(
                    None, f"Enter a number for the {catalog.label_for(category)} quantity."
                )
                continue
            if quantity <= 0:
                self.add_error(
                    None,
                    f"The {catalog.label_for(category)} quantity must be greater than zero.",
                )
                continue
            items.append((category, quantity))
        return items

    def clean(self):
        cleaned_data = super().clean()
        self.parsed_items = self._parse_items()
        num_bags = cleaned_data.get("num_bags")
        num_boxes = cleaned_data.get("num_boxes")
        cash_check = cleaned_data.get("cash_check")
        gift_cards = cleaned_data.get("gift_cards")
        other_donation = cleaned_data.get("other_donation")
        total_weight = cleaned_data.get("total_weight")
        if not (num_bags or num_boxes or cash_check or gift_cards or total_weight or (other_donation and other_donation.strip()) or self.parsed_items):
            raise forms.ValidationError(
                "Record at least one thing donated: add an item, or fill in "
                "# of Bags, # of Boxes, Total Weight (lbs), Cash/Check $, "
                "Gift Cards $ or Other Donation."
            )
        return cleaned_data

    def save_items(self, donation):
        """
        Replace the donation's line items with the ones just submitted.

        Called separately from save() because the intake view saves with
        commit=False to attach the site and donation number first, so there is
        no donation to hang items off until after it returns.

        Replace rather than merge: the wizard and the edit modal both submit
        the complete list, so anything missing from it was removed.
        """
        items = getattr(self, "parsed_items", [])
        donation.items.all().delete()
        for category, quantity in items:
            donation.items.create(category=category, quantity=quantity)
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
        self.fields["opt_in_email"].initial = True  # receipt enabled by default
        self.fields["opt_in_email"].label = "Send confirmation email to donor"
        self.fields["opt_in_email"].widget.attrs.pop("class", None)  # no form-control on checkbox
        # Deliberately permissive: any local part, any domain, any TLD
        # (.org, .net, .edu, .co.uk, …). All it requires is name@domain.tld.
        # Django's EmailField is the authoritative check on the server.
        self.fields["email"].widget.attrs["pattern"] = r"[^\s@]+@[^\s@]+\.[^\s@.]{2,}"
        self.fields["email"].widget.attrs["title"] = (
            "A full email address, e.g. info@example.org"
        )
        self.fields["phone_number"].validators.append(_phone_validator)
        self.fields["phone_number"].widget.attrs["type"] = "tel"
        self.fields["phone_number"].widget.attrs["pattern"] = r"[\+\d][\d\s()\-\.]{6,19}"
        self.fields["phone_number"].widget.attrs["title"] = "e.g. 555-123-4567 or (555) 867-5309"

