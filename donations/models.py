from django.db import models


class Site(models.Model):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Donation(models.Model):
    DONOR_TYPE_CHOICES = [
        ("Anonymous", "Anonymous"),
        ("Civic", "Civic"),
        ("Religious", "Religious"),
        ("Corporate", "Corporate"),
        ("Individual", "Individual"),
    ]
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="donations")
    donation_date = models.DateField()
    donor_name = models.CharField(max_length=120, blank=True)
    donor_type = models.CharField(max_length=16, choices=DONOR_TYPE_CHOICES, default="Individual", blank=True)
    organization = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    num_bags = models.PositiveIntegerField(null=True, blank=True, verbose_name="# of Bags")
    num_boxes = models.PositiveIntegerField(null=True, blank=True, verbose_name="# of Boxes")
    cash_check = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Cash/Check $")
    gift_cards = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Gift Cards $")
    other_donation = models.CharField(max_length=255, blank=True, verbose_name="Other Donation")
    total_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Total Weight (lbs)")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    opt_in_email = models.BooleanField(default=False)
    unsubscribe = models.BooleanField(default=False)
    unsubscribe_token = models.CharField(max_length=64, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-donation_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.donor_name} ({self.donation_date})"
