"""CogniSweep transactional email dispatch worker.

Run this beside the Streamlit app in production so queued notification records
are delivered automatically through Resend, SendGrid, or SMTP.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import smtplib
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any, Dict, Iterable, Tuple

import requests

from email_templates import render_transactional_email
from production_persistence import fetch_saas_records, save_saas_record

LOGGER = logging.getLogger("errorsweep.email_worker")
DEFAULT_BATCH_LIMIT = 25
DEFAULT_INTERVAL_SECONDS = 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sanitize_header(value: Any, label: str, max_length: int = 320) -> str:
    text = _safe_text(value)
    if "\r" in text or "\n" in text:
        raise ValueError(f"{label} contains prohibited newline characters.")
    return text[:max(1, int(max_length))]


def _validate_email_address(value: Any, label: str) -> str:
    raw = _sanitize_header(value, label)
    parsed_name, parsed_email = parseaddr(raw)
    email = _safe_text(parsed_email or raw)
    if "\r" in email or "\n" in email or not email or "@" not in email:
        raise ValueError(f"{label} is missing or invalid.")
    if raw != email and parsed_name:
        _sanitize_header(parsed_name, f"{label} display name")
    return email


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value not in (None, ""):
        return str(value).strip()
    return default


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() not in {"0", "false", "no", "off"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except Exception:
        return default


def _metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    raw = record.get("metadata_json")
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def email_provider_label() -> str:
    return _env("ERRORSWEEP_EMAIL_PROVIDER").lower() or "not_configured"


def email_from_address() -> str:
    return (
        _env("ERRORSWEEP_EMAIL_FROM")
        or _env("SENDGRID_FROM_EMAIL")
        or _env("RESEND_FROM_EMAIL")
        or "no-reply@cognisweep.local"
    )


def email_sender_parts() -> Tuple[str, str, str]:
    raw = email_from_address()
    name, email = parseaddr(raw)
    return raw, _safe_text(email or raw), _safe_text(name)


def email_templates_enabled() -> bool:
    return _bool_env("ERRORSWEEP_EMAIL_HTML_ENABLED", True)


def notification_email_payload(record: Dict[str, Any]) -> Dict[str, str]:
    subject = _safe_text(record.get("subject"))
    body = _safe_text(record.get("body"))
    if not email_templates_enabled():
        return {
            "subject": subject,
            "text": body,
            "html": "",
            "preheader": "",
            "template_key": "text_only",
            "cta_label": "",
            "cta_url": "",
        }
    return render_transactional_email(
        subject=subject,
        body=body,
        event_type=_safe_text(record.get("event_type")),
        metadata=_metadata(record),
        app_base_url=_env("ERRORSWEEP_PUBLIC_BASE_URL"),
        brand_name="CogniSweep",
    )


def _send_resend(recipient: str, subject: str, text_body: str, html_body: str, sender: str) -> None:
    api_key = _env("RESEND_API_KEY") or _env("ERRORSWEEP_RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured.")
    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "from": sender,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            **({"html": html_body} if html_body else {}),
        },
        timeout=20,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Resend returned {response.status_code}: {response.text[:300]}")


def _send_sendgrid(recipient: str, subject: str, text_body: str, html_body: str, sender_email: str, sender_name: str) -> None:
    api_key = _env("SENDGRID_API_KEY") or _env("ERRORSWEEP_SENDGRID_API_KEY")
    if not api_key:
        raise RuntimeError("SENDGRID_API_KEY is not configured.")
    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "personalizations": [{"to": [{"email": recipient}]}],
            "from": {"email": sender_email, **({"name": sender_name} if sender_name else {})},
            "subject": subject,
            "content": (
                [{"type": "text/plain", "value": text_body}, {"type": "text/html", "value": html_body}]
                if html_body else
                [{"type": "text/plain", "value": text_body}]
            ),
        },
        timeout=20,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"SendGrid returned {response.status_code}: {response.text[:300]}")


def _send_smtp(recipient: str, subject: str, text_body: str, html_body: str, sender: str) -> None:
    host = _env("SMTP_HOST") or _env("ERRORSWEEP_SMTP_HOST")
    port = _int_env("SMTP_PORT", _int_env("ERRORSWEEP_SMTP_PORT", 587))
    username = _env("SMTP_USER") or _env("ERRORSWEEP_SMTP_USER")
    password = _env("SMTP_PASSWORD") or _env("ERRORSWEEP_SMTP_PASSWORD")
    if not host:
        raise RuntimeError("SMTP_HOST is not configured.")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(host, port, timeout=20) as client:
        if _bool_env("SMTP_TLS", _bool_env("ERRORSWEEP_SMTP_TLS", True)):
            client.starttls()
        if username:
            client.login(username, password)
        client.send_message(message)


def dispatch_notification(record: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    provider = email_provider_label()
    updated = dict(record or {})
    if provider in {"", "manual", "not_configured"}:
        updated["status"] = "provider_pending"
        updated["error"] = "Email provider is not configured."
        updated["updated_at"] = _now_iso()
        return updated

    recipient = _safe_text(updated.get("recipient"))
    try:
        recipient = _validate_email_address(recipient, "Notification recipient")
    except ValueError as exc:
        updated["status"] = "failed"
        updated["error"] = _safe_text(exc)
        updated["updated_at"] = _now_iso()
        return updated

    payload = notification_email_payload(updated)
    try:
        subject = _sanitize_header(payload.get("subject") or updated.get("subject"), "Email subject", max_length=240)
        sender, sender_email, sender_name = email_sender_parts()
        sender = _sanitize_header(sender, "Email sender")
        sender_email = _validate_email_address(sender_email, "Email sender")
        sender_name = _sanitize_header(sender_name, "Email sender display name", max_length=120)
    except ValueError as exc:
        updated["status"] = "failed"
        updated["error"] = _safe_text(exc)
        updated["updated_at"] = _now_iso()
        return updated
    text_body = _safe_text(payload.get("text") or updated.get("body"))
    html_body = _safe_text(payload.get("html"))

    try:
        if dry_run:
            LOGGER.info("Dry run: would send %s notification %s to %s", provider, updated.get("id"), recipient)
        elif provider == "resend":
            _send_resend(recipient, subject, text_body, html_body, sender)
        elif provider == "sendgrid":
            _send_sendgrid(recipient, subject, text_body, html_body, sender_email, sender_name)
        elif provider == "smtp":
            _send_smtp(recipient, subject, text_body, html_body, sender)
        else:
            raise RuntimeError(f"Unsupported email provider: {provider}. Use resend, sendgrid, smtp, or manual.")
        updated["status"] = "dry_run" if dry_run else "sent"
        updated["sent_at"] = _now_iso() if not dry_run else _safe_text(updated.get("sent_at"))
        updated["error"] = ""
    except Exception as exc:
        updated["status"] = "failed"
        updated["error"] = _safe_text(exc)[:700]
        LOGGER.warning("Failed to send notification %s: %s", updated.get("id"), exc)

    metadata = _metadata(updated)
    metadata.update({
        "email_template_key": payload.get("template_key", "text_only"),
        "email_preheader": payload.get("preheader", ""),
        "email_cta_label": payload.get("cta_label", ""),
        "email_cta_url": payload.get("cta_url", ""),
        "email_html_enabled": bool(html_body),
        "email_dispatch_worker": True,
        "email_dispatch_dry_run": bool(dry_run),
    })
    updated["metadata_json"] = metadata
    updated["provider"] = provider
    updated["updated_at"] = _now_iso()
    return updated


def _pending_notifications(records: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for record in records:
        if _safe_text(record.get("status")).lower() in {"queued", "failed"}:
            yield record


def persist_notification(record: Dict[str, Any]) -> Dict[str, Any]:
    workspace = _safe_text(record.get("workspace")) or "Platform"
    return save_saas_record(
        "notifications",
        record,
        user={"email": "email-dispatch-worker@cognisweep.local", "workspace": workspace},
    )


def dispatch_pending(limit: int = DEFAULT_BATCH_LIMIT, dry_run: bool = False) -> Dict[str, int]:
    records = fetch_saas_records(
        "notifications",
        limit=max(1, min(int(limit or 1), 1000)),
        include_all_workspaces=True,
        platform_scope_reason="email_dispatch_worker_queue",
    )
    summary = {"checked": len(records), "pending": 0, "sent": 0, "failed": 0, "provider_pending": 0, "dry_run": 0}
    for record in _pending_notifications(records):
        if summary["pending"] >= max(1, int(limit or 1)):
            break
        summary["pending"] += 1
        updated = dispatch_notification(record, dry_run=dry_run)
        status = _safe_text(updated.get("status")).lower()
        if not dry_run:
            persist_notification(updated)
        if status in summary:
            summary[status] += 1
        elif status == "sent":
            summary["sent"] += 1
        else:
            summary["failed"] += 1
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatch queued CogniSweep transactional emails.")
    parser.add_argument("--once", action="store_true", help="Run one dispatch pass and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Render/check pending emails without sending or persisting status.")
    parser.add_argument("--limit", type=int, default=_int_env("ERRORSWEEP_EMAIL_DISPATCH_BATCH_LIMIT", DEFAULT_BATCH_LIMIT))
    parser.add_argument("--interval", type=int, default=_int_env("ERRORSWEEP_EMAIL_WORKER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    args = parser.parse_args()

    logging.basicConfig(level=_env("ERRORSWEEP_EMAIL_WORKER_LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(message)s")
    run_once = args.once or _bool_env("ERRORSWEEP_EMAIL_WORKER_ONCE", False)
    LOGGER.info("Starting CogniSweep email worker provider=%s dry_run=%s", email_provider_label(), args.dry_run)
    while True:
        summary = dispatch_pending(limit=args.limit, dry_run=args.dry_run)
        LOGGER.info("Email dispatch summary: %s", json.dumps(summary, sort_keys=True))
        if run_once:
            return 0 if summary.get("failed", 0) == 0 else 1
        time.sleep(max(5, int(args.interval or DEFAULT_INTERVAL_SECONDS)))


if __name__ == "__main__":
    raise SystemExit(main())
