"""
Brevo (Sendinblue) transactional email service.

Environment variables:
  BREVO_API_KEY                   – required; Brevo API key
  LIVE_EMAIL                      – set to "true" to send to real recipients
  LIVE_EMAIL_RECIPIENT_OVERRIDE   – email address used when not in live mode
  SITE_BASE_URL                   – base URL for building unsubscribe links
                                    (default: http://localhost:8000)
"""

import logging
import os
import secrets

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

logger = logging.getLogger(__name__)

SENDER_NAME = "CFA"
SENDER_EMAIL = "cfa@ramapo-dmc.dev"
_DEFAULT_OVERRIDE = "tnosrati@ramapo.edu"

# Addresses BCC'd on every donation receipt (live mode only).
RECEIPT_BCC_EMAILS = ["vpaulson@cfanj.org", "sfrees@ramapo.edu"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_live() -> bool:
    return os.environ.get("LIVE_EMAIL", "").strip().lower() == "true"


def _get_final_recipient(intended_email: str, intended_name: str) -> tuple[str, str]:
    """Return (email, name) for the actual send target based on LIVE_EMAIL."""
    if _is_live():
        return intended_email, intended_name
    override = os.environ.get("LIVE_EMAIL_RECIPIENT_OVERRIDE", _DEFAULT_OVERRIDE).strip()
    return override, intended_name


def _get_brevo_api() -> sib_api_v3_sdk.TransactionalEmailsApi:
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    if not api_key:
        logger.error(
            "BREVO_API_KEY environment variable is not set – cannot send email. "
            "On production this must be provided via the .env file next to manage.py "
            "or the systemd unit's Environment/EnvironmentFile directive."
        )
        raise RuntimeError("BREVO_API_KEY environment variable is not set")
    # Log a safe fingerprint of the key (length + last 4 chars only) so you can
    # confirm the *right* key is loaded without ever leaking it into the logs.
    logger.debug(
        "Brevo API key loaded (length=%d, ...%s)", len(api_key), api_key[-4:]
    )
    config = sib_api_v3_sdk.Configuration()
    config.api_key["api-key"] = api_key
    return sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(config))


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_unsubscribe_url(token: str) -> str:
    base = os.environ.get("SITE_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/unsubscribe/{token}/"


def ensure_unsubscribe_token(donation) -> str:
    """
    Return the donation's unsubscribe_token, generating and saving one first
    if it does not yet exist.
    """
    if not donation.unsubscribe_token:
        donation.unsubscribe_token = secrets.token_urlsafe(32)
        donation.save(update_fields=["unsubscribe_token"])
    return donation.unsubscribe_token


def can_send_email(donation) -> tuple[bool, str | None]:
    """
    Return (True, None) when the donation record is eligible to receive email.
    Return (False, reason) otherwise.
    """
    if not donation.email:
        return False, "no email address on record"
    if not donation.opt_in_email:
        return False, "donor has not opted in to email"
    if donation.unsubscribe:
        return False, "donor has unsubscribed"
    return True, None


def _build_unsubscribe_footer(unsubscribe_url: str) -> str:
    return (
        '<hr style="margin-top:40px;border:none;border-top:1px solid #eee;">'
        '<p style="font-size:12px;color:#888;text-align:center;">'
        "If you no longer want to receive these emails, "
        f'<a href="{unsubscribe_url}" style="color:#888;">unsubscribe here</a>.'
        "</p>"
    )


# ---------------------------------------------------------------------------
# Main send function
# ---------------------------------------------------------------------------

def send_email(
    recipient_email: str,
    recipient_name: str,
    subject: str,
    html_content: str,
    donation=None,
):
    """
    Send a transactional email via Brevo.

    Parameters
    ----------
    recipient_email : str
        The *intended* recipient's email address.
    recipient_name : str
        The *intended* recipient's display name.
    subject : str
        Email subject line.
    html_content : str
        HTML body of the email.
    donation : Donation | None
        When provided, the function:
          - checks opt_in_email and unsubscribe status
          - ensures an unsubscribe token exists
          - appends an unsubscribe footer to the HTML

    Returns
    -------
    The Brevo API response object, or None if sending was skipped.

    Raises
    ------
    RuntimeError   – BREVO_API_KEY is not configured
    ApiException   – Brevo API returned an error
    """
    # --- log the effective configuration for this send -----------------------
    live = _is_live()
    logger.info(
        "send_email() called | intended=%s | subject=%r | LIVE_EMAIL=%s | "
        "BREVO_API_KEY set=%s | donation pk=%s",
        recipient_email,
        subject,
        live,
        bool(os.environ.get("BREVO_API_KEY", "").strip()),
        getattr(donation, "pk", None),
    )
    if not live:
        logger.warning(
            "LIVE_EMAIL is not 'true' – this email will be REDIRECTED to the "
            "override address (%s), not delivered to the real donor. Set "
            "LIVE_EMAIL=true in the environment to send to real recipients.",
            os.environ.get("LIVE_EMAIL_RECIPIENT_OVERRIDE", _DEFAULT_OVERRIDE).strip(),
        )

    # --- eligibility check ---------------------------------------------------
    if donation is not None:
        eligible, reason = can_send_email(donation)
        if not eligible:
            logger.info(
                "Email to %s skipped: %s (donation pk=%s)",
                recipient_email,
                reason,
                getattr(donation, "pk", "?"),
            )
            return None

        token = ensure_unsubscribe_token(donation)
        html_content = html_content + _build_unsubscribe_footer(get_unsubscribe_url(token))

    # --- recipient routing ---------------------------------------------------
    final_email, final_name = _get_final_recipient(recipient_email, recipient_name)

    if not _is_live():
        logger.info(
            "Non-live mode: redirecting email intended for %s → %s",
            recipient_email,
            final_email,
        )

    # --- BCC routing ---------------------------------------------------------
    # BCC fixed monitoring addresses on every receipt, but only when sending for
    # real – in non-live mode we don't want to email the real BCC recipients.
    bcc = None
    if _is_live() and RECEIPT_BCC_EMAILS:
        bcc = [{"email": addr} for addr in RECEIPT_BCC_EMAILS]
        logger.info("BCC'ing receipt to %s", ", ".join(RECEIPT_BCC_EMAILS))

    # --- send ----------------------------------------------------------------
    api = _get_brevo_api()
    payload = sib_api_v3_sdk.SendSmtpEmail(
        sender={"name": SENDER_NAME, "email": SENDER_EMAIL},
        to=[{"email": final_email, "name": final_name}],
        bcc=bcc,
        subject=subject,
        html_content=html_content,
    )

    try:
        result = api.send_transac_email(payload)
        logger.info(
            "Email sent | to=%s (intended=%s) | subject=%r | message_id=%s",
            final_email,
            recipient_email,
            subject,
            getattr(result, "message_id", None),
        )
        return result
    except ApiException as exc:
        logger.error(
            "Brevo API error | to=%s | subject=%r | status=%s | body=%s",
            recipient_email,
            subject,
            exc.status,
            exc.body,
        )
        raise
