from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models, transaction

from . import catalog


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
    cdonation_number = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-donation_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.donor_name} ({self.donation_date})"

    @property
    def general_goods_value(self):
        """
        Value of loose General Food/Goods, from total_weight at the
        DONATION_VALUE_PER_POUND rate. None when no weight was recorded.
        """
        if self.total_weight is None:
            return None
        rate = Decimal(settings.DONATION_VALUE_PER_POUND)
        return (self.total_weight * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def items_value(self):
        """
        Value of the priced line items, or None when there are none.

        Items whose category is no longer in the catalog have no price and
        contribute nothing here, while still showing as unknown on their own
        line. That only happens if a category is deleted from catalog.py --
        retiring one by leaving it in place keeps historical donations valued.
        """
        values = [item.value for item in self.items.all() if item.value is not None]
        if not values:
            return None
        return sum(values)

    @property
    def estimated_value(self):
        """
        Estimated dollar value of the donated goods: priced line items plus
        loose General Food/Goods by weight. Computed on read rather than
        stored, so a price change applies everywhere at once.

        Cash and gift cards are excluded. They are money already, not an
        estimate, and the receipt reports them separately.

        Returns None when the donation has neither items nor a weight, which
        is what every donation recorded before line items existed looks like.
        """
        parts = [v for v in (self.items_value, self.general_goods_value) if v is not None]
        if not parts:
            return None
        return sum(parts)


class DonationItem(models.Model):
    """
    One priced line on a donation: a category from catalog.py and a quantity.

    Only catalog categories are stored here. General Food/Goods, cash, gift
    cards and Other stay in the Donation's own columns -- each can occur at
    most once per donation, so a child row would buy nothing and would mean
    migrating every historical donation into this table.
    """
    donation = models.ForeignKey(Donation, on_delete=models.CASCADE, related_name="items")
    category = models.CharField(max_length=32, choices=catalog.CATEGORY_CHOICES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.describe()

    @property
    def unit_price(self):
        """Current catalog price, or None if the category is no longer listed."""
        return catalog.price_for(self.category)

    @property
    def value(self):
        """
        quantity x current unit price, or None when the category has been
        dropped from the catalog. None rather than 0 so a retired category
        reads as "unknown" in the exports instead of silently worth nothing.
        """
        price = self.unit_price
        if price is None:
            return None
        return (self.quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def describe(self) -> str:
        return catalog.describe(self.category, self.quantity)


class DonationCounter(models.Model):
    """Singleton row used as a concurrency-safe cycling counter (1–500)."""
    current = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "donation counter"


def get_next_cdonation_number() -> int:
    """
    Return the next cdonation_number in the cycle 1–500, wrapping 500 → 1.
    Uses SELECT FOR UPDATE to prevent two concurrent donations from receiving
    the same number.
    """
    with transaction.atomic():
        counter, _ = DonationCounter.objects.select_for_update().get_or_create(
            id=1, defaults={"current": 0}
        )
        next_num = (counter.current % 500) + 1
        counter.current = next_num
        counter.save(update_fields=["current"])
    return next_num
