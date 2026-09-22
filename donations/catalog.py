"""
Priced categories for in-kind donations.

CFA assigns each kind of donated good a fixed dollar value. Most are priced
per item (a turkey is $35.00); a few are priced per pound (ham), and the carts
are priced per pound but only ever arrive as whole carts of a known weight, so
they are quoted here as a price per cart.

Values are computed on read from this table rather than stored on the donation,
matching how DONATION_VALUE_PER_POUND already works: revising a price re-values
every donation that used it, including receipts already sent. That is the
accepted tradeoff -- CFA revises this list about once a year and wants the
current list applied everywhere.

General Food/Goods is deliberately absent. It has no per-item price; it is
valued from its recorded weight at settings.DONATION_VALUE_PER_POUND, and is
recorded in the Donation's own num_bags/num_boxes/total_weight columns rather
than as a line item.
"""

from decimal import Decimal

# unit -- the noun shown next to the quantity box ("3 packs", "12.50 pounds").
# Kept singular here; pluralize_unit() handles display.
CATALOG = {
    "snack_pack": {
        "label": "Snack Packs",
        "unit": "pack",
        "price": Decimal("7.50"),
    },
    "smile_pack": {
        "label": "Smile Packs",
        "unit": "pack",
        "price": Decimal("4.50"),
    },
    "diapers_child": {
        "label": "Diapers - child",
        "unit": "package",
        "price": Decimal("11.99"),
    },
    "adult_briefs": {
        "label": "Adult briefs",
        "unit": "package",
        "price": Decimal("14.00"),
    },
    "backpack_empty": {
        "label": "Backpacks - empty",
        "unit": "backpack",
        "price": Decimal("40.00"),
    },
    "backpack_filled": {
        "label": "Backpacks - filled",
        "unit": "backpack",
        "price": Decimal("110.00"),
    },
    "school_supplies": {
        "label": "School supplies (assorted)",
        "unit": "bag/box",
        "price": Decimal("70.00"),
    },
    "turkey": {
        "label": "Turkey",
        "unit": "turkey",
        "price": Decimal("35.00"),
    },
    "chicken_turkey_breast": {
        "label": "Chicken/Turkey Breast",
        "unit": "breast",
        "price": Decimal("12.15"),
    },
    "ham": {
        # Quantity is POUNDS of ham, not a count of hams.
        "label": "Ham",
        "unit": "pound",
        "price": Decimal("5.43"),
    },
    "cart_small": {
        # 100 lb cart at $3.91/lb. Priced per cart because staff count carts,
        # never weigh them. Note $3.91 is CFA's cart rate and is deliberately
        # independent of DONATION_VALUE_PER_POUND ($3.90), which applies to
        # loose General Food/Goods.
        "label": "Small cart (100 lbs)",
        "unit": "cart",
        "price": Decimal("391.00"),
    },
    "cart_large": {
        # 200 lb cart at $3.91/lb.
        "label": "Large cart (200 lbs)",
        "unit": "cart",
        "price": Decimal("782.00"),
    },
}

# Django choices, in the order above -- CFA's own sheet order, which staff
# scanning the dropdown will recognize.
CATEGORY_CHOICES = [(key, entry["label"]) for key, entry in CATALOG.items()]


def get_entry(category):
    """Return the catalog entry for a category key, or None if unknown."""
    return CATALOG.get(category)


def unit_for(category):
    """Unit noun for a category, or "" when the category is unknown."""
    entry = CATALOG.get(category)
    return entry["unit"] if entry else ""


def price_for(category):
    """Unit price for a category, or None when the category is unknown."""
    entry = CATALOG.get(category)
    return entry["price"] if entry else None


def label_for(category):
    """Display label for a category, falling back to the raw key."""
    entry = CATALOG.get(category)
    return entry["label"] if entry else category


def pluralize_unit(unit, quantity):
    """
    "pack" -> "packs" for any quantity but exactly 1.

    Only handles the units in this table; "bag/box" pluralizes as "bags/boxes"
    and the rest take a plain -s.
    """
    if quantity == 1:
        return unit
    if unit == "bag/box":
        return "bags/boxes"
    return f"{unit}s"


def describe(category, quantity):
    """
    Human-readable line for receipts and exports: "3 x Turkey", "2 x Small cart
    (100 lbs)", "12.50 lbs of Ham".

    Counts use "x <label>" rather than a pluralized label, because the labels
    are inconsistently plural already ("Snack Packs" but "Turkey") and
    pluralizing them produces nonsense. Whole quantities drop their decimals.
    """
    entry = CATALOG.get(category)
    label = entry["label"] if entry else category
    if quantity == quantity.to_integral_value():
        qty_text = f"{quantity.to_integral_value():,}"
    else:
        qty_text = f"{quantity:,.2f}"
    if entry and entry["unit"] == "pound":
        return f"{qty_text} lbs of {label}"
    return f"{qty_text} x {label}"
