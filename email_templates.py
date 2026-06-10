"""Transactional email templates for ErrorSweep.

The app stores notification records in the outbox, then renders provider-ready
plain text and HTML at dispatch time. Templates stay deterministic and local so
email delivery does not need another service beyond Resend, SendGrid, or SMTP.
"""
from __future__ import annotations

import re
from html import escape
from typing import Any, Dict, Iterable, Tuple

URL_RE = re.compile(r"https?://[^\s)>\"]+", re.IGNORECASE)

FACT_LABELS = {
    "workspace": "Workspace",
    "plan": "Plan",
    "billing_cycle": "Billing cycle",
    "amount": "Amount",
    "currency": "Currency",
    "status": "Status",
    "priority": "Priority",
    "category": "Category",
    "job_type": "Job type",
    "language": "Language",
    "segments": "Segments",
    "score": "Score",
    "result": "Result",
    "trial_days": "Trial days",
    "post_trial_plan": "Post-trial plan",
    "attachment_count": "Attachments",
}

TEMPLATE_META = {
    "auth.email_verification": {
        "key": "verification",
        "eyebrow": "Account security",
        "headline": "Verify your ErrorSweep email",
        "preheader": "Confirm your email address to secure workspace access.",
        "cta_label": "Verify email",
        "url_keys": ("verify_url", "url", "action_url"),
    },
    "auth.password_reset": {
        "key": "password_reset",
        "eyebrow": "Account recovery",
        "headline": "Reset your ErrorSweep password",
        "preheader": "Use the secure reset link to choose a new password.",
        "cta_label": "Reset password",
        "url_keys": ("reset_url", "url", "action_url"),
    },
    "signup.welcome": {
        "key": "welcome",
        "eyebrow": "Workspace ready",
        "headline": "Welcome to ErrorSweep",
        "preheader": "Your trial workspace is ready for localization QA.",
        "cta_label": "Open workspace",
        "url_keys": ("verify_url", "workspace_url", "url", "action_url"),
    },
    "job.assigned": {
        "key": "job_assigned",
        "eyebrow": "New assignment",
        "headline": "A job was assigned to you",
        "preheader": "Review the task details and attached files in ErrorSweep.",
        "cta_label": "Open jobs",
        "url_keys": ("job_url", "workspace_url", "url", "action_url"),
    },
    "qa.completed": {
        "key": "qa_completed",
        "eyebrow": "QA completed",
        "headline": "Your QA report is ready",
        "preheader": "Review findings, score, and delivery gate details.",
        "cta_label": "Open QA",
        "url_keys": ("qa_url", "report_url", "workspace_url", "url", "action_url"),
    },
    "pro.completed": {
        "key": "pro_completed",
        "eyebrow": "Pro workflow completed",
        "headline": "Your Pro translation workflow is ready",
        "preheader": "Open the Human Review editor to check final output.",
        "cta_label": "Open review",
        "url_keys": ("job_url", "review_url", "workspace_url", "url", "action_url"),
    },
    "billing.checkout_intent": {
        "key": "billing_checkout",
        "eyebrow": "Billing setup",
        "headline": "Your monthly mandate setup has started",
        "preheader": "Complete checkout to activate the selected ErrorSweep plan.",
        "cta_label": "Open checkout",
        "url_keys": ("checkout_url", "payment_url", "url", "action_url"),
    },
    "billing.subscription_updated": {
        "key": "subscription_updated",
        "eyebrow": "Subscription updated",
        "headline": "Your ErrorSweep plan changed",
        "preheader": "The selected workspace subscription has been updated.",
        "cta_label": "View billing",
        "url_keys": ("billing_url", "workspace_url", "url", "action_url"),
    },
    "billing.subscription_cancelled": {
        "key": "subscription_cancelled",
        "eyebrow": "Subscription cancelled",
        "headline": "Your subscription cancellation is recorded",
        "preheader": "The cancellation has been saved for the workspace.",
        "cta_label": "View billing",
        "url_keys": ("billing_url", "workspace_url", "url", "action_url"),
    },
    "billing.trial_mandate_cancelled": {
        "key": "trial_cancelled",
        "eyebrow": "Trial mandate cancelled",
        "headline": "Your trial mandate was cancelled",
        "preheader": "No monthly mandate will continue from this pending checkout.",
        "cta_label": "View billing",
        "url_keys": ("billing_url", "workspace_url", "url", "action_url"),
    },
    "billing.payment_recorded": {
        "key": "payment_recorded",
        "eyebrow": "Payment recorded",
        "headline": "A payment record was added",
        "preheader": "The billing record is now available in ErrorSweep.",
        "cta_label": "View payments",
        "url_keys": ("billing_url", "payment_url", "workspace_url", "url", "action_url"),
    },
    "support.ticket_opened": {
        "key": "support_opened",
        "eyebrow": "Support",
        "headline": "Your support ticket is open",
        "preheader": "The ErrorSweep support queue has received your ticket.",
        "cta_label": "Open support",
        "url_keys": ("support_url", "workspace_url", "url", "action_url"),
    },
    "support.ticket_updated": {
        "key": "support_updated",
        "eyebrow": "Support update",
        "headline": "Your support ticket was updated",
        "preheader": "Review the latest support status and reply.",
        "cta_label": "Open support",
        "url_keys": ("support_url", "workspace_url", "url", "action_url"),
    },
    "status.incident_created": {
        "key": "status_notice",
        "eyebrow": "Service status",
        "headline": "ErrorSweep status notice",
        "preheader": "A platform status or maintenance notice was published.",
        "cta_label": "Open ErrorSweep",
        "url_keys": ("status_url", "workspace_url", "url", "action_url"),
    },
    "privacy_request_opened": {
        "key": "privacy_request",
        "eyebrow": "Privacy workflow",
        "headline": "Privacy request opened",
        "preheader": "Track the due date and owner notes in ErrorSweep.",
        "cta_label": "Open privacy tracker",
        "url_keys": ("privacy_url", "workspace_url", "url", "action_url"),
    },
    "email.deliverability_test": {
        "key": "deliverability_test",
        "eyebrow": "Deliverability test",
        "headline": "ErrorSweep email delivery test",
        "preheader": "This confirms provider, sender, HTML template, and plain-text fallback delivery.",
        "cta_label": "Open ErrorSweep",
        "url_keys": ("workspace_url", "url", "action_url"),
    },
}


def template_catalog() -> Dict[str, Dict[str, str]]:
    return {key: {k: str(v) for k, v in meta.items() if isinstance(v, str)} for key, meta in TEMPLATE_META.items()}


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _metadata(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _template_for_event(event_type: str) -> Dict[str, Any]:
    event_type = _safe_text(event_type)
    if event_type in TEMPLATE_META:
        return TEMPLATE_META[event_type]
    if event_type.startswith("billing."):
        return TEMPLATE_META["billing.subscription_updated"]
    if event_type.startswith("support."):
        return TEMPLATE_META["support.ticket_updated"]
    if event_type.startswith("auth."):
        return TEMPLATE_META["auth.email_verification"]
    return {
        "key": "generic",
        "eyebrow": "Notification",
        "headline": "ErrorSweep notification",
        "preheader": "A workspace notification is ready for review.",
        "cta_label": "Open ErrorSweep",
        "url_keys": ("workspace_url", "url", "action_url"),
    }


def _first_url_from_text(text: str) -> str:
    match = URL_RE.search(text or "")
    return match.group(0).rstrip(".,") if match else ""


def _cta(meta: Dict[str, Any], template: Dict[str, Any], body: str, app_base_url: str) -> Tuple[str, str]:
    for key in template.get("url_keys", ()):
        url = _safe_text(meta.get(key))
        if url:
            return _safe_text(template.get("cta_label")) or "Open ErrorSweep", url
    body_url = _first_url_from_text(body)
    if body_url:
        return _safe_text(template.get("cta_label")) or "Open ErrorSweep", body_url
    if app_base_url:
        return "Open ErrorSweep", app_base_url
    return "", ""


def _fact_rows(meta: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    emitted = 0
    for key, label in FACT_LABELS.items():
        value = meta.get(key)
        if value in (None, "", [], {}):
            continue
        emitted += 1
        yield label, _safe_text(value)
        if emitted >= 8:
            break


def _html_paragraphs(body: str) -> str:
    body = _safe_text(body)
    if not body:
        return "<p>No additional details were provided.</p>"
    parts = [part.strip() for part in body.replace("\r\n", "\n").split("\n\n") if part.strip()]
    if not parts:
        parts = [body]
    return "\n".join(f"<p>{escape(part).replace(chr(10), '<br>')}</p>" for part in parts)


def render_transactional_email(
    subject: str,
    body: str,
    event_type: str,
    metadata: Any = None,
    app_base_url: str = "",
    brand_name: str = "ErrorSweep",
) -> Dict[str, str]:
    meta = _metadata(metadata)
    template = _template_for_event(event_type)
    subject = _safe_text(subject) or _safe_text(template.get("headline")) or f"{brand_name} notification"
    body = _safe_text(body)
    preheader = _safe_text(meta.get("preheader") or template.get("preheader"))
    headline = _safe_text(meta.get("headline") or template.get("headline") or subject)
    eyebrow = _safe_text(template.get("eyebrow") or "Notification")
    cta_label, cta_url = _cta(meta, template, body, _safe_text(app_base_url))
    workspace = _safe_text(meta.get("workspace"))

    fact_html = ""
    fact_text_lines = []
    for label, value in _fact_rows(meta):
        fact_text_lines.append(f"{label}: {value}")
        fact_html += (
            "<tr>"
            f"<td style=\"padding:8px 0;color:#64748b;font-size:13px;\">{escape(label)}</td>"
            f"<td style=\"padding:8px 0;color:#0f172a;font-size:13px;text-align:right;font-weight:700;\">{escape(value)}</td>"
            "</tr>"
        )
    fact_table = (
        "<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" "
        "style=\"margin:18px 0;border-top:1px solid #dbeafe;border-bottom:1px solid #dbeafe;\">"
        f"{fact_html}</table>"
        if fact_html else ""
    )
    cta_html = (
        f"<a href=\"{escape(cta_url)}\" style=\"display:inline-block;background:#0fbc9f;color:#03111f;"
        "text-decoration:none;font-weight:800;border-radius:10px;padding:13px 18px;"
        "box-shadow:0 10px 24px rgba(15,188,159,.25);\">"
        f"{escape(cta_label)}</a>"
        if cta_url else ""
    )
    cta_text = f"\n\n{cta_label}: {cta_url}" if cta_url else ""
    facts_text = "\n".join(fact_text_lines)
    text = (
        f"{subject}\n\n"
        f"{preheader}\n\n"
        f"{body or headline}\n"
        f"{chr(10) + facts_text if facts_text else ''}"
        f"{cta_text}\n\n"
        f"{brand_name}"
    ).strip()
    html = f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#07111f;font-family:Inter,Segoe UI,Arial,sans-serif;color:#0f172a;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(preheader)}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#07111f;padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:#f8fbff;border:1px solid #bde9ff;border-radius:18px;overflow:hidden;">
            <tr>
              <td style="background:#0b1228;padding:24px 28px;border-bottom:4px solid #0fbc9f;">
                <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#17f5d0;font-weight:800;">{escape(eyebrow)}</div>
                <div style="font-size:28px;line-height:1.15;color:#ffffff;font-weight:900;margin-top:10px;">{escape(headline)}</div>
                <div style="font-size:14px;line-height:1.6;color:#b8c7e6;margin-top:10px;">{escape(preheader)}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;">
                <div style="font-size:15px;line-height:1.7;color:#243044;">{_html_paragraphs(body)}</div>
                {fact_table}
                {cta_html}
                <div style="margin-top:26px;padding-top:18px;border-top:1px solid #dbeafe;font-size:12px;line-height:1.6;color:#64748b;">
                  Sent by {escape(brand_name)}{f" for {escape(workspace)}" if workspace else ""}. This message relates to your workspace, account, billing, support, or service status activity.
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return {
        "subject": subject,
        "preheader": preheader,
        "text": text,
        "html": html,
        "template_key": _safe_text(template.get("key") or "generic"),
        "cta_label": cta_label,
        "cta_url": cta_url,
    }
