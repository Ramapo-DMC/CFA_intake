
import csv
import logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, F, Q
from django.views.decorators.http import require_POST
from datetime import date, timedelta
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from . import catalog
from .models import Donation, Site
from .forms import DonationForm
from .site_select_form import SiteSelectForm
from .email_service import send_email

logger = logging.getLogger(__name__)


def _catalog_for_js():
    """
    The catalog as plain JSON types for the intake wizard's live pricing.
    Decimal isn't JSON-serializable, so prices go over as floats -- they only
    drive the on-screen preview; the saved value is always recomputed from the
    Decimal prices server-side.
    """
    return {
        key: {"label": entry["label"], "unit": entry["unit"], "price": float(entry["price"])}
        for key, entry in catalog.CATALOG.items()
    }


def _format_items(donation) -> str:
    """Semicolon-separated line items for a single export cell."""
    return "; ".join(item.describe() for item in donation.items.all())


def _fit(canvas_obj, text, width, font, size):
    """
    Truncate text with an ellipsis until it fits within width.

    The table is 16 columns on a landscape letter page, so nearly every cell
    has to be clipped; without this the columns overrun each other and the
    page edge.
    """
    text = text or "-"
    if canvas_obj.stringWidth(text, font, size) <= width:
        return text
    ellipsis = "\u2026"
    while text and canvas_obj.stringWidth(text + ellipsis, font, size) > width:
        text = text[:-1]
    return text + ellipsis


def _format_gift_description(donation) -> str:
    """Build a human-readable summary of what was donated."""
    parts = []
    if donation.cash_check:
        parts.append(f"${donation.cash_check:,.2f} cash/check")
    if donation.gift_cards:
        parts.append(f"${donation.gift_cards:,.2f} in gift cards")
    for item in donation.items.all():
        parts.append(item.describe())
    if donation.num_bags:
        n = donation.num_bags
        parts.append(f"{n} bag{'s' if n != 1 else ''}")
    if donation.num_boxes:
        n = donation.num_boxes
        parts.append(f"{n} box{'es' if n != 1 else ''}")
    if donation.total_weight:
        parts.append(f"{donation.total_weight:,.2f} lbs")
    if donation.other_donation:
        parts.append(donation.other_donation)
    return ", ".join(parts) if parts else "your donation"

@login_required
def donation_detail(request, pk):
    donation = get_object_or_404(Donation.objects.prefetch_related("items"), pk=pk)
    return render(request, "donations/donation_detail.html", {
        "donation": donation,
        "donor_type_choices": Donation.DONOR_TYPE_CHOICES,
        "value_per_pound": settings.DONATION_VALUE_PER_POUND,
        "category_choices": catalog.CATEGORY_CHOICES,
        "catalog_json": _catalog_for_js(),
    })

@login_required
def donation_preview_modal(request, pk):
    donation = get_object_or_404(Donation.objects.prefetch_related("items"), pk=pk)
    donor_type_choices = Donation.DONOR_TYPE_CHOICES
    return render(request, "donations/donation_preview_modal.html", {
        "donation": donation,
        "donor_type_choices": donor_type_choices,
        "category_choices": catalog.CATEGORY_CHOICES,
        "catalog_json": _catalog_for_js(),
    })


@login_required
def donation_edit(request, pk):
    donation = get_object_or_404(Donation, pk=pk)
    if request.method == "POST":
        form = DonationForm(request.POST, instance=donation)
        if form.is_valid():
            donation = form.save()
            form.save_items(donation)
            return JsonResponse({
                "success": True,
                "estimated_value": donation.estimated_value,
            })
        return JsonResponse({"success": False, "errors": form.errors}, status=400)
    return JsonResponse({"success": False}, status=405)


@login_required
@require_POST
def donation_delete(request, pk):
    donation = get_object_or_404(Donation, pk=pk)
    donation.delete()
    return JsonResponse({"success": True})


@login_required
def donation_export_csv(request):
    # Use same filters as donation_log
    query = request.GET.get("q", "").strip()
    site = request.GET.get("site", "").strip()
    donor_type = request.GET.get("donor_type", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    donations = Donation.objects.select_related("site").prefetch_related("items").all()
    if query:
        donations = donations.filter(
            Q(donor_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone_number__icontains=query)
            | Q(notes__icontains=query)
            | Q(site__name__icontains=query)
        )
    if site:
        donations = donations.filter(site__name__iexact=site)
    if donor_type:
        donations = donations.filter(donor_type=donor_type)
    if date_from:
        donations = donations.filter(donation_date__gte=date_from)
    if date_to:
        donations = donations.filter(donation_date__lte=date_to)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="donations.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Date", "Site", "Donor", "Type", "Email", "Phone", "Address", "# of Bags", "# of Boxes", "Cash/Check $", "Gift Cards $", "Other Donation", "Items", "Total Weight (lbs)", "Donation Value ($)", "Notes"
    ])
    for d in donations:
        writer.writerow([
            d.donation_date,
            d.site.name,
            d.donor_name,
            d.donor_type,
            d.email,
            d.phone_number,
            d.address,
            d.num_bags,
            d.num_boxes,
            d.cash_check,
            d.gift_cards,
            d.other_donation,
            _format_items(d),
            d.total_weight,
            d.estimated_value,
            d.notes,
        ])
    return response



@login_required
def donation_export_pdf(request):
    # Use same filters as donation_log
    query = request.GET.get("q", "").strip()
    site = request.GET.get("site", "").strip()
    donor_type = request.GET.get("donor_type", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    donations = Donation.objects.select_related("site").prefetch_related("items").all()
    if query:
        donations = donations.filter(
            Q(donor_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone_number__icontains=query)
            | Q(notes__icontains=query)
            | Q(site__name__icontains=query)
        )
    if site:
        donations = donations.filter(site__name__iexact=site)
    if donor_type:
        donations = donations.filter(donor_type=donor_type)
    if date_from:
        donations = donations.filter(donation_date__gte=date_from)
    if date_to:
        donations = donations.filter(donation_date__lte=date_to)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="donations.pdf"'

    buffer = []
    c = canvas.Canvas(response, pagesize=landscape(letter))
    width, height = landscape(letter)

    # Table header. The widths below total exactly 10 inches, the printable
    # width of a landscape letter page inside its half-inch margins -- the
    # previous set totalled 16.8 inches and ran off the edge of the paper.
    columns = [
        "Date", "Site", "Donor", "Type", "Email", "Phone", "Address", "Bags",
        "Boxes", "Cash $", "Gift $", "Other", "Items", "Wt (lbs)", "Value $", "Notes",
    ]
    col_widths = [
        0.62*inch, 0.75*inch, 0.85*inch, 0.50*inch, 1.00*inch, 0.68*inch,
        0.85*inch, 0.30*inch, 0.32*inch, 0.42*inch, 0.38*inch, 0.63*inch,
        1.15*inch, 0.45*inch, 0.50*inch, 0.60*inch,
    ]
    header_font, header_size = "Helvetica-Bold", 6.5
    row_font, row_size = "Helvetica", 6.5

    def draw_header(y_pos):
        c.setFont(header_font, header_size)
        x_pos = 0.5 * inch
        for i, col in enumerate(columns):
            c.drawString(x_pos, y_pos, _fit(c, col, col_widths[i] - 3, header_font, header_size))
            x_pos += col_widths[i]

    x = 0.5 * inch
    y = height - 0.75 * inch
    draw_header(y)

    # Table rows
    y -= 0.3 * inch
    c.setFont(row_font, row_size)
    for d in donations:
        x = 0.5 * inch
        row = [
            str(d.donation_date),
            d.site.name,
            d.donor_name,
            d.donor_type,
            d.email,
            d.phone_number,
            d.address,
            str(d.num_bags) if d.num_bags is not None else "-",
            str(d.num_boxes) if d.num_boxes is not None else "-",
            str(d.cash_check) if d.cash_check is not None else "-",
            str(d.gift_cards) if d.gift_cards is not None else "-",
            d.other_donation,
            _format_items(d),
            str(d.total_weight) if d.total_weight is not None else "-",
            f"{d.estimated_value:,.2f}" if d.estimated_value is not None else "-",
            d.notes,
        ]
        for i, value in enumerate(row):
            # Leave 3pt of gutter so adjacent cells never touch.
            c.drawString(x, y, _fit(c, value, col_widths[i] - 3, row_font, row_size))
            x += col_widths[i]
        y -= 0.25 * inch
        if y < 0.75 * inch:
            c.showPage()
            y = height - 0.75 * inch
            draw_header(y)
            y -= 0.3 * inch
            c.setFont(row_font, row_size)

    c.save()
    return response
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .forms import DonationForm
from .models import Donation, Site, get_next_cdonation_number


def home(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.session.get("site_id"):
        return redirect("site-select")
    return redirect("donation-create")


def site_select(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if request.method == "POST":
        form = SiteSelectForm(request.POST)
        if form.is_valid():
            request.session["site_id"] = form.cleaned_data["site"].id
            return redirect("donation-create")
    else:
        form = SiteSelectForm()
    return render(request, "donations/site_select.html", {"form": form})

@login_required
def donation_create(request):
    site_id = request.session.get("site_id")
    if not site_id:
        return redirect("site-select")
    try:
        site = Site.objects.get(id=site_id)
    except Site.DoesNotExist:
        return redirect("site-select")
    success = False
    cdonation_number = None
    if request.method == "POST":
        form = DonationForm(request.POST)
        if form.is_valid():
            donation = form.save(commit=False)
            donation.site = site
            donation.cdonation_number = get_next_cdonation_number()
            donation.save()
            form.save_items(donation)
            success = True
            cdonation_number = donation.cdonation_number
            if donation.email:
                gift = _format_gift_description(donation)
                name = donation.donor_name or "Friend"
                received_on = donation.donation_date.strftime("%B %d, %Y")
                # Estimated value paragraph — only when there is something to
                # value. Names what the estimate was based on, since it can now
                # come from priced items, loose weight, or both.
                value_paragraph = ""
                if donation.estimated_value is not None:
                    if donation.items_value is not None and donation.general_goods_value is not None:
                        basis = "the items and weight recorded"
                    elif donation.items_value is not None:
                        basis = "the items recorded"
                    else:
                        basis = (
                            "the recorded weight of "
                            f"<strong>{donation.total_weight:,.2f} lbs</strong>"
                        )
                    value_paragraph = (
                        f'<p>Based on {basis}, the estimated '
                        'value of your donation is '
                        f'<strong>${donation.estimated_value:,.2f}</strong>.</p>\n\n  '
                    )
                html_body = f"""
<div style="font-family:Georgia,'Times New Roman',serif;max-width:600px;
            margin:0 auto;color:#222;line-height:1.75;font-size:15px;">
  <p>Hello {name},</p>

  <p>Thank you for your generous gift of <strong>{gift}</strong>, received on
  <strong>{received_on}</strong>, in support of the Center for Food Action.
  Your kindness helps power our mission to ensure that individuals and families
  facing food insecurity in Bergen and Passaic counties have access to
  nutritious food and essential resources.</p>

  {value_paragraph}<p>Your generosity makes this work possible. We are deeply grateful for your
  belief in our mission and your partnership in creating a stronger, more caring
  community. Thank you for making a meaningful difference.</p>

  <p>The Center for Food Action in NJ is a 501&nbsp;(c)&nbsp;(3) non-profit
  corporation. No goods or services in part or in whole have been provided for
  this charitable contribution.</p>

  <br>
  <p>Sincerely,</p>
  <p>
    Nicole A. Davis<br>
    <em>Executive Director</em>
  </p>
</div>
"""
                logger.info(
                    "Attempting donation receipt email | donation pk=%s | "
                    "cdonation=%s | to=%s | opt_in=%s | unsubscribed=%s",
                    donation.pk,
                    cdonation_number,
                    donation.email,
                    donation.opt_in_email,
                    donation.unsubscribe,
                )
                try:
                    result = send_email(
                        recipient_email=donation.email,
                        recipient_name=donation.donor_name,
                        subject="Thank You for Your Donation to Center for Food Action",
                        html_content=html_body,
                        donation=donation,
                    )
                    if result is None:
                        logger.info(
                            "Receipt email not sent for donation pk=%s "
                            "(skipped by eligibility check – see preceding log line)",
                            donation.pk,
                        )
                    else:
                        logger.info(
                            "Receipt email dispatched for donation pk=%s", donation.pk
                        )
                except Exception:
                    # Email failure must not block the donation save, but it must
                    # never be silent – log the full traceback so it's visible in
                    # the server logs (journalctl on production).
                    logger.exception(
                        "Receipt email FAILED for donation pk=%s (to=%s). "
                        "Donation was still saved.",
                        donation.pk,
                        donation.email,
                    )
            form = DonationForm(initial={"donation_date": date.today()})
    else:
        form = DonationForm(initial={"donation_date": date.today()})

    return render(request, "donations/donation_form.html", {
        "form": form,
        "success": success,
        "site": site,
        "cdonation_number": cdonation_number,
        "category_choices": catalog.CATEGORY_CHOICES,
        "catalog_json": _catalog_for_js(),
        "value_per_pound": settings.DONATION_VALUE_PER_POUND,
        # Re-render whatever line items were posted, so a validation failure
        # elsewhere on the form doesn't silently drop them.
        "posted_items": getattr(form, "parsed_items", []),
    })


@login_required
def donation_log(request):
    query = request.GET.get("q", "").strip()
    site = request.GET.get("site", "").strip()
    donor_type = request.GET.get("donor_type", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    donations = Donation.objects.select_related("site").prefetch_related("items").all()
    if query:
        donations = donations.filter(
            Q(donor_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone_number__icontains=query)
            | Q(notes__icontains=query)
            | Q(site__name__icontains=query)
        )
    if site:
        donations = donations.filter(site__name__iexact=site)
    if donor_type:
        donations = donations.filter(donor_type=donor_type)
    if date_from:
        donations = donations.filter(donation_date__gte=date_from)
    if date_to:
        donations = donations.filter(donation_date__lte=date_to)

    site_totals = (
        Donation.objects.values(site_name=F("site__name"))
        .annotate(total=Count("id"))
        .order_by("site_name")
    )
    recent_cutoff = date.today() - timedelta(days=30)
    last_30_days_total = Donation.objects.filter(donation_date__gte=recent_cutoff).count()

    donor_type_choices = [
        ("", "All Categories"),
        ("Anonymous", "Anonymous"),
        ("Civic", "Civic"),
        ("Religious", "Religious"),
        ("Corporate", "Corporate"),
        ("Individual", "Individual"),
    ]

    context = {
        "donations": donations,
        "query": query,
        "site": site,
        "donor_type": donor_type,
        "date_from": date_from,
        "date_to": date_to,
        "donor_type_choices": donor_type_choices,
        "active_sites": Site.objects.filter(is_active=True).order_by("name"),
        "total_count": donations.count(),
        "all_time_count": Donation.objects.count(),
        "last_30_days_total": last_30_days_total,
        "site_totals": site_totals,
    }
    return render(request, "donations/donation_log.html", context)


@login_required
def donor_suggestions(request):
    term = request.GET.get("q", "").strip()
    if len(term) < 1:
        return JsonResponse({"results": []})

    donors = (
        Donation.objects.filter(Q(donor_name__icontains=term) | Q(email__icontains=term))
        .values("donor_name", "email")
        .annotate(total=Count("id"))
        .order_by("-total", "donor_name")[:10]
    )
    return JsonResponse({"results": list(donors)})


@login_required
def donor_autocomplete(request):
    q     = request.GET.get("q", "").strip()
    field = request.GET.get("field", "name")

    if len(q) < 2:
        return JsonResponse([], safe=False)

    filter_map = {
        "email": Q(email__icontains=q),
        "phone": Q(phone_number__icontains=q),
        "name":  Q(donor_name__icontains=q),
    }
    filter_q = filter_map.get(field, filter_map["name"])

    rows = (
        Donation.objects
        .filter(filter_q)
        .order_by("-donation_date", "-created_at")
        .values("donor_name", "email", "phone_number", "address", "organization")
    )

    seen    = set()
    results = []
    for row in rows:
        key = (row["donor_name"].strip().lower(), row["email"].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "name":         row["donor_name"],
            "email":        row["email"],
            "phone":        row["phone_number"],
            "address":      row["address"],
            "organization": row["organization"],
        })
        if len(results) >= 8:
            break

    return JsonResponse(results, safe=False)


# ---------------------------------------------------------------------------
# Unsubscribe flow (no login required – accessed from email link)
# ---------------------------------------------------------------------------

def unsubscribe(request, token):
    """
    GET  /unsubscribe/<token>/  – show confirmation page
    POST /unsubscribe/<token>/  – process unsubscribe and show success
    """
    try:
        donation = Donation.objects.get(unsubscribe_token=token)
    except Donation.DoesNotExist:
        return render(request, "donations/unsubscribe_invalid.html", status=404)

    if request.method == "POST":
        donation.unsubscribe = True
        donation.save(update_fields=["unsubscribe"])
        return render(request, "donations/unsubscribe_success.html", {"donation": donation})

    return render(request, "donations/unsubscribe_confirm.html", {"donation": donation})
