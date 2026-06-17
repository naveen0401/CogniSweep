"""Standalone billing webhook receiver for CogniSweep.

Run this beside the Streamlit app when Stripe/Razorpay live billing is enabled:

    python billing_webhook_receiver.py

Provider webhook URLs:

    /webhooks/billing/stripe
    /webhooks/billing/razorpay

The receiver verifies provider signatures, normalizes events, persists billing
event records, and applies small subscription/payment lifecycle updates through
the shared production persistence layer.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

from billing_webhooks import normalize_billing_webhook, verify_billing_webhook_signature
from production_persistence import fetch_saas_records, save_saas_record

LOGGER = logging.getLogger("errorsweep.billing_webhook_receiver")

APP_NAME = "errorsweep-billing-webhook-receiver"
SUCCESS_STATUSES = {"paid", "active", "authorized", "authenticated", "captured", "complete", "completed", "succeeded"}
FAILED_STATUSES = {"failed", "failure", "declined", "requires_payment_method"}
CANCELLED_STATUSES = {"cancelled", "canceled", "cancel_at_period_end"}
TERMINAL_CHECKOUT_STATUSES = {"cancelled", "canceled", "expired", "paid", "completed", "failed", "mandate_active"}
DEFAULT_REPLAY_WINDOW_SECONDS = 300
DEFAULT_FUTURE_SKEW_SECONDS = 60

PLAN_CATALOG: Dict[str, Dict[str, Any]] = {
    "trial": {
        "name": "Trial",
        "monthly": 0,
        "annual": 0,
        "currency": "INR",
        "trial_days": 14,
        "seats": 2,
        "segments": 500,
        "characters": 100_000,
    },
    "pro": {
        "name": "Pro",
        "monthly": 3999,
        "annual": 39990,
        "currency": "INR",
        "seats": 5,
        "segments": 10_000,
        "characters": 2_000_000,
    },
    "agency": {
        "name": "Agency",
        "monthly": 11999,
        "annual": 119990,
        "currency": "INR",
        "seats": 20,
        "segments": 50_000,
        "characters": 10_000_000,
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly": 0,
        "annual": 0,
        "currency": "INR",
        "seats": 100,
        "segments": 250_000,
        "characters": 50_000_000,
    },
}


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    value = safe_text(os.getenv(name)).lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(safe_text(os.getenv(name)))
    except Exception:
        value = default
    return max(minimum, value)


def plan_record(plan_name: str) -> Dict[str, Any]:
    requested = safe_text(plan_name).lower()
    return dict(PLAN_CATALOG.get(requested) or PLAN_CATALOG["pro"])


def parse_metadata(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            data = json.loads(value)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def money_value(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def webhook_secret_for_provider(provider: str) -> str:
    provider_key = safe_text(provider).upper()
    candidates = [
        f"ERRORSWEEP_{provider_key}_WEBHOOK_SECRET",
        f"{provider_key}_WEBHOOK_SECRET",
        "ERRORSWEEP_BILLING_WEBHOOK_SECRET",
    ]
    for key in candidates:
        value = safe_text(os.getenv(key))
        if value:
            return value
    return ""


def signature_header_for_provider(provider: str, headers: Mapping[str, str]) -> str:
    provider = safe_text(provider).lower()
    if provider == "stripe":
        return safe_text(headers.get("Stripe-Signature"))
    if provider == "razorpay":
        return safe_text(headers.get("X-Razorpay-Signature"))
    return safe_text(headers.get("X-CogniSweep-Signature") or headers.get("Stripe-Signature") or headers.get("X-Razorpay-Signature"))


def verify_signature(provider: str, raw_payload: str, headers: Mapping[str, str]) -> str:
    resolved_provider = safe_text(provider).lower()
    signature_header = signature_header_for_provider(resolved_provider, headers)
    secret_value = webhook_secret_for_provider(resolved_provider)
    if resolved_provider in {"stripe", "razorpay"} and not secret_value:
        return "secret_missing"
    if secret_value and not signature_header and resolved_provider in {"stripe", "razorpay"}:
        return "missing"
    if signature_header and secret_value:
        try:
            return "verified" if verify_billing_webhook_signature(resolved_provider, raw_payload, signature_header, secret_value) else "invalid"
        except Exception as exc:
            LOGGER.warning("Webhook signature verification failed for %s: %s", resolved_provider, exc)
            return "unavailable"
    return "not_checked"


def billing_workspace(normalized: Dict[str, Any], checkout: Optional[Dict[str, Any]] = None) -> str:
    return safe_text(normalized.get("workspace")) or safe_text((checkout or {}).get("workspace")) or "Unassigned Billing"


def fetch_collection(collection: str, workspace: str = "") -> List[Dict[str, Any]]:
    return fetch_saas_records(
        collection,
        workspace=workspace,
        limit=1000,
        include_all_workspaces=not bool(workspace),
        platform_scope_reason="billing_webhook_reconciliation" if not workspace else "",
    )


def event_replay_status(normalized: Dict[str, Any], now_seconds: Optional[float] = None) -> str:
    raw_timestamp = normalized.get("event_created_at")
    try:
        event_seconds = int(float(raw_timestamp or 0))
    except Exception:
        event_seconds = 0
    if event_seconds <= 0:
        return "not_available"

    now_value = float(now_seconds if now_seconds is not None else time.time())
    replay_window = env_int("ERRORSWEEP_BILLING_WEBHOOK_REPLAY_WINDOW_SECONDS", DEFAULT_REPLAY_WINDOW_SECONDS, minimum=60)
    future_skew = env_int("ERRORSWEEP_BILLING_WEBHOOK_FUTURE_SKEW_SECONDS", DEFAULT_FUTURE_SKEW_SECONDS, minimum=1)
    if event_seconds < now_value - replay_window:
        return "too_old"
    if event_seconds > now_value + future_skew:
        return "future"
    return "valid"


def find_existing_billing_event(normalized: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    provider = safe_text(normalized.get("provider")).lower()
    event_id = safe_text(normalized.get("event_id"))
    if not provider or not event_id:
        return None
    workspace = safe_text(normalized.get("workspace"))
    for item in fetch_collection("billing_events", workspace=workspace):
        if provider == safe_text(item.get("provider")).lower() and event_id == safe_text(item.get("event_id")):
            return item
    return None


def persist(collection: str, record: Dict[str, Any], workspace: str = "", user_email: str = "") -> Dict[str, Any]:
    actor = {
        "email": safe_text(user_email) or "billing-webhook@cognisweep.local",
        "workspace": safe_text(workspace) or safe_text(record.get("workspace")) or "Platform",
    }
    return save_saas_record(collection, record, user=actor)


def find_checkout_for_event(normalized: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    workspace = safe_text(normalized.get("workspace"))
    checkout_id = safe_text(normalized.get("checkout_id"))
    provider_subscription_id = safe_text(normalized.get("provider_subscription_id"))
    provider_payment_id = safe_text(normalized.get("provider_payment_id"))
    provider_order_id = safe_text(normalized.get("provider_order_id"))
    plan_name = safe_text(normalized.get("plan"))
    candidates = fetch_collection("checkout_sessions", workspace=workspace)

    for item in candidates:
        metadata = parse_metadata(item.get("metadata_json"))
        identity_values = {
            safe_text(item.get("id")),
            safe_text(item.get("provider_session_id")),
            safe_text(metadata.get("checkout_id")),
            safe_text(metadata.get("provider_checkout_id")),
        }
        if checkout_id and checkout_id in identity_values:
            return item
        if provider_subscription_id and provider_subscription_id == safe_text(metadata.get("provider_subscription_id")):
            return item
        if provider_payment_id and provider_payment_id == safe_text(metadata.get("provider_payment_id")):
            return item
        if provider_order_id and provider_order_id == safe_text(metadata.get("provider_order_id")):
            return item

    active_candidates = [
        item for item in candidates
        if safe_text(item.get("status")).lower() not in TERMINAL_CHECKOUT_STATUSES
    ]
    if plan_name and workspace:
        for item in active_candidates:
            metadata = parse_metadata(item.get("metadata_json"))
            if plan_name in {safe_text(item.get("plan")), safe_text(metadata.get("post_trial_plan"))}:
                return item
    if workspace and active_candidates:
        return active_candidates[0]
    return None


def checkout_update_status(status: str, fallback: str = "received") -> str:
    status = safe_text(status).lower()
    if status in SUCCESS_STATUSES:
        return "mandate_active"
    if status in FAILED_STATUSES:
        return "failed"
    if status in CANCELLED_STATUSES:
        return "cancelled"
    return status or fallback


def update_checkout_from_event(normalized: Dict[str, Any], checkout: Dict[str, Any]) -> Dict[str, Any]:
    workspace = billing_workspace(normalized, checkout)
    metadata = parse_metadata(checkout.get("metadata_json"))
    updated = dict(checkout)
    updated["workspace"] = workspace
    updated["status"] = checkout_update_status(normalized.get("status"), fallback=safe_text(updated.get("status")) or "received")
    updated["provider"] = safe_text(normalized.get("provider")) or safe_text(updated.get("provider"))
    updated["provider_session_id"] = safe_text(
        normalized.get("checkout_id")
        or normalized.get("provider_subscription_id")
        or normalized.get("provider_payment_id")
        or updated.get("provider_session_id")
    )
    updated["metadata_json"] = {
        **metadata,
        "last_billing_event_id": safe_text(normalized.get("event_id")),
        "last_billing_event_status": safe_text(normalized.get("status")),
        "provider_payment_id": safe_text(normalized.get("provider_payment_id")),
        "provider_subscription_id": safe_text(normalized.get("provider_subscription_id")),
        "provider_order_id": safe_text(normalized.get("provider_order_id")),
        "provider_customer_id": safe_text(normalized.get("provider_customer_id")),
    }
    return persist("checkout_sessions", updated, workspace=workspace, user_email=safe_text(normalized.get("user_email")))


def subscription_plan_from_event(normalized: Dict[str, Any], checkout: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], bool, Dict[str, Any]]:
    checkout_metadata = parse_metadata((checkout or {}).get("metadata_json"))
    checkout_plan = safe_text((checkout or {}).get("plan"))
    normalized_plan = safe_text(normalized.get("plan"))
    is_trial_checkout = checkout_plan.lower() == "trial"
    plan_name = normalized_plan or checkout_plan or "Pro"
    if is_trial_checkout:
        plan_name = safe_text(checkout_metadata.get("post_trial_plan")) or "Pro"
    return plan_record(plan_name), is_trial_checkout, checkout_metadata


def activate_subscription_from_event(normalized: Dict[str, Any], checkout: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    workspace = billing_workspace(normalized, checkout)
    plan, is_trial_checkout, checkout_metadata = subscription_plan_from_event(normalized, checkout)
    now = datetime.now(timezone.utc)
    billing_cycle = safe_text((checkout or {}).get("billing_cycle") or checkout_metadata.get("billing_cycle") or "monthly").lower()
    if billing_cycle not in {"monthly", "annual"}:
        billing_cycle = "monthly"
    period_days = int(checkout_metadata.get("trial_days") or plan.get("trial_days") or 14) if is_trial_checkout else 365 if billing_cycle == "annual" else 30
    amount = money_value(normalized.get("amount"), fallback=0.0)
    if amount <= 0 and not is_trial_checkout:
        amount = money_value(plan.get("annual" if billing_cycle == "annual" else "monthly"), fallback=0.0)
    subscription = {
        "workspace": workspace,
        "user_email": safe_text(normalized.get("user_email")),
        "plan": plan["name"],
        "status": "Trialing" if is_trial_checkout else "Active",
        "billing_cycle": billing_cycle,
        "currency": safe_text(normalized.get("currency")) or plan["currency"],
        "base_amount": 0.0 if is_trial_checkout else amount,
        "included_segments": plan["segments"],
        "included_characters": plan["characters"],
        "included_seats": plan["seats"],
        "provider": safe_text(normalized.get("provider")),
        "provider_customer_id": safe_text(normalized.get("provider_customer_id")),
        "provider_subscription_id": safe_text(normalized.get("provider_subscription_id")),
        "current_period_start": now.isoformat(),
        "current_period_end": (now + timedelta(days=period_days)).isoformat(),
        "cancel_at_period_end": False,
        "cancelled_at": "",
        "cancellation_reason": "",
        "metadata_json": {
            **checkout_metadata,
            "activated_from_billing_event": safe_text(normalized.get("event_id")),
            "source_checkout_id": safe_text((checkout or {}).get("id")),
            "mandate_type": "card_or_upi_monthly",
            "trial_checkout": is_trial_checkout,
            "monthly_mandate_amount": checkout_metadata.get("monthly_mandate_amount") or plan.get("monthly", 0),
        },
    }
    return persist("subscriptions", subscription, workspace=workspace, user_email=safe_text(normalized.get("user_email")))


def record_payment_from_event(normalized: Dict[str, Any], checkout: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    amount = money_value(normalized.get("amount"), fallback=0.0)
    if amount <= 0:
        return None
    workspace = billing_workspace(normalized, checkout)
    plan_name = safe_text(normalized.get("plan")) or safe_text((checkout or {}).get("plan"))
    payment = {
        "date": now_iso(),
        "workspace": workspace,
        "user_email": safe_text(normalized.get("user_email")),
        "user": safe_text(normalized.get("user_email")),
        "plan": plan_name,
        "amount": amount,
        "currency": safe_text(normalized.get("currency")) or "INR",
        "status": "Recorded from webhook",
    }
    return persist("payments", payment, workspace=workspace, user_email=safe_text(normalized.get("user_email")))


def cancel_subscriptions_from_event(normalized: Dict[str, Any], checkout: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    workspace = billing_workspace(normalized, checkout)
    cancelled: List[Dict[str, Any]] = []
    for item in fetch_collection("subscriptions", workspace=workspace):
        if safe_text(item.get("status")).lower() not in {"active", "trialing", "past_due"}:
            continue
        updated = dict(item)
        updated["status"] = "Cancelled"
        updated["cancel_at_period_end"] = False
        updated["cancelled_at"] = now_iso()
        updated["cancellation_reason"] = f"Provider event {safe_text(normalized.get('event_id'))}"
        metadata = parse_metadata(updated.get("metadata_json"))
        updated["metadata_json"] = {
            **metadata,
            "cancelled_from_billing_event": safe_text(normalized.get("event_id")),
            "provider_status": safe_text(normalized.get("status")),
        }
        cancelled.append(persist("subscriptions", updated, workspace=workspace, user_email=safe_text(normalized.get("user_email"))))
    return cancelled


def apply_billing_event(normalized: Dict[str, Any]) -> List[str]:
    status = safe_text(normalized.get("status")).lower()
    checkout = find_checkout_for_event(normalized)
    workspace = safe_text(normalized.get("workspace")) or safe_text((checkout or {}).get("workspace"))
    messages: List[str] = []

    if checkout:
        updated_checkout = update_checkout_from_event(normalized, checkout)
        messages.append(f"Checkout updated to {updated_checkout.get('status')}.")

    if status in (SUCCESS_STATUSES | CANCELLED_STATUSES) and not workspace:
        messages.append("Lifecycle update skipped because the event did not include a workspace or matching checkout.")
    elif status in SUCCESS_STATUSES:
        subscription = activate_subscription_from_event(normalized, checkout)
        messages.append(f"Subscription recorded as {subscription.get('status')}: {subscription.get('plan')}.")
        payment = record_payment_from_event(normalized, checkout)
        if payment:
            messages.append(f"Payment recorded: {payment.get('amount')} {payment.get('currency')}.")
    elif status in CANCELLED_STATUSES:
        cancelled = cancel_subscriptions_from_event(normalized, checkout)
        messages.append(f"Cancelled subscriptions: {len(cancelled)}.")
    elif status in FAILED_STATUSES:
        messages.append("Billing event recorded as failed.")
    else:
        messages.append("Billing event stored; no lifecycle change was applied.")
    return messages


def billing_event_record(normalized: Dict[str, Any], signature_status: str, replay_status: str) -> Dict[str, Any]:
    return {
        "workspace": billing_workspace(normalized),
        "user_email": safe_text(normalized.get("user_email")),
        "provider": safe_text(normalized.get("provider")),
        "event_id": safe_text(normalized.get("event_id")),
        "event_type": safe_text(normalized.get("event_type")),
        "status": safe_text(normalized.get("status")),
        "plan": safe_text(normalized.get("plan")),
        "amount": money_value(normalized.get("amount"), fallback=0.0),
        "currency": safe_text(normalized.get("currency") or "INR"),
        "provider_payment_id": safe_text(normalized.get("provider_payment_id")),
        "provider_subscription_id": safe_text(normalized.get("provider_subscription_id")),
        "provider_order_id": safe_text(normalized.get("provider_order_id")),
        "provider_customer_id": safe_text(normalized.get("provider_customer_id")),
        "checkout_id": safe_text(normalized.get("checkout_id")),
        "signature_status": signature_status,
        "applied": False,
        "raw_sha256": safe_text(normalized.get("raw_sha256")),
        "metadata_json": {
            "provider_metadata": normalized.get("metadata") or {},
            "normalized": normalized,
            "receiver": APP_NAME,
            "event_replay_status": replay_status,
        },
    }


def process_webhook(provider: str, raw_payload: str, headers: Mapping[str, str], apply_updates: bool = True) -> Tuple[int, Dict[str, Any]]:
    normalized = normalize_billing_webhook(provider, raw_payload)
    resolved_provider = safe_text(normalized.get("provider") or provider or "manual").lower()
    signature_status = verify_signature(resolved_provider, raw_payload, headers)
    replay_status = event_replay_status(normalized)
    existing_event = find_existing_billing_event(normalized)
    duplicate_applied_event = bool(existing_event and existing_event.get("applied"))
    new_event_record = billing_event_record(normalized, signature_status, replay_status)
    new_event_record["provider"] = resolved_provider
    if existing_event and duplicate_applied_event:
        event_record = dict(existing_event)
        existing_metadata = parse_metadata(existing_event.get("metadata_json"))
        event_record["metadata_json"] = {
            **existing_metadata,
            "duplicate_event_seen_at": now_iso(),
            "duplicate_signature_status": signature_status,
            "duplicate_replay_status": replay_status,
            "duplicate_raw_sha256": safe_text(normalized.get("raw_sha256")),
            "duplicate_was_already_applied": True,
        }
    else:
        event_record = new_event_record
    if existing_event and not duplicate_applied_event:
        if safe_text(existing_event.get("id")):
            event_record["id"] = safe_text(existing_event.get("id"))
        existing_metadata = parse_metadata(existing_event.get("metadata_json"))
        event_record["applied"] = bool(existing_event.get("applied"))
        event_record["metadata_json"] = {
            **existing_metadata,
            **parse_metadata(new_event_record.get("metadata_json")),
            "duplicate_event_seen_at": now_iso(),
            "duplicate_was_already_applied": False,
        }
    event_record = persist(
        "billing_events",
        event_record,
        workspace=safe_text(event_record.get("workspace")),
        user_email=safe_text(event_record.get("user_email")),
    )

    applied_messages: List[str] = []
    blocked_signatures = {"invalid", "missing", "secret_missing", "unavailable"}
    blocked_replays = {"too_old", "future"}
    if duplicate_applied_event:
        applied_messages = ["Duplicate billing event ignored because it was already applied."]
    elif replay_status in blocked_replays:
        applied_messages = [f"Event stored but not applied because replay status is {replay_status}."]
    elif apply_updates and signature_status not in blocked_signatures:
        applied_messages = apply_billing_event(normalized)
        event_record["applied"] = True
        event_record["metadata_json"] = {
            **parse_metadata(event_record.get("metadata_json")),
            "applied_messages": applied_messages,
        }
        event_record = persist(
            "billing_events",
            event_record,
            workspace=safe_text(event_record.get("workspace")),
            user_email=safe_text(event_record.get("user_email")),
        )
    elif signature_status in blocked_signatures:
        applied_messages = [f"Event stored but not applied because signature status is {signature_status}."]
    else:
        applied_messages = ["Event stored without applying lifecycle updates."]

    status_code = HTTPStatus.OK
    if signature_status in {"invalid", "missing", "secret_missing"}:
        status_code = HTTPStatus.UNAUTHORIZED
    elif replay_status in {"too_old", "future"}:
        status_code = HTTPStatus.BAD_REQUEST

    response = {
        "ok": signature_status not in {"invalid", "missing", "secret_missing"} and replay_status not in {"too_old", "future"},
        "provider": resolved_provider,
        "event_id": safe_text(normalized.get("event_id")),
        "event_type": safe_text(normalized.get("event_type")),
        "status": safe_text(normalized.get("status")),
        "signature_status": signature_status,
        "event_replay_status": replay_status,
        "applied": bool(event_record.get("applied")),
        "duplicate": duplicate_applied_event,
        "messages": applied_messages,
    }
    return int(status_code), response


def provider_from_path(path: str) -> str:
    parts = [part for part in urlparse(path).path.strip("/").split("/") if part]
    if len(parts) >= 3 and parts[0] == "webhooks" and parts[1] == "billing":
        return parts[2]
    if len(parts) >= 2 and parts[0] == "billing" and parts[1] in {"stripe", "razorpay", "manual", "auto"}:
        return parts[1]
    if parts and parts[-1] in {"stripe", "razorpay", "manual", "auto"}:
        return parts[-1]
    return "auto"


class BillingWebhookHandler(BaseHTTPRequestHandler):
    server_version = "CogniSweepBillingWebhook/1.0"

    def send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if urlparse(self.path).path.rstrip("/") in {"", "/health"}:
            self.send_json(HTTPStatus.OK, {"ok": True, "service": APP_NAME, "time": now_iso()})
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Unknown route."})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        max_bytes = int(os.getenv("ERRORSWEEP_BILLING_WEBHOOK_MAX_BYTES", str(1024 * 1024)))
        content_length = int(self.headers.get("Content-Length") or 0)
        if content_length <= 0:
            self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Empty webhook payload."})
            return
        if content_length > max_bytes:
            self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "Webhook payload exceeds configured size limit."})
            return

        raw_payload = self.rfile.read(content_length).decode("utf-8", errors="replace")
        provider = provider_from_path(self.path)
        try:
            status_code, response = process_webhook(
                provider,
                raw_payload,
                self.headers,
                apply_updates=env_bool("ERRORSWEEP_WEBHOOK_APPLY_UPDATES", True),
            )
        except json.JSONDecodeError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"Invalid JSON payload: {exc}"})
            return
        except Exception as exc:
            LOGGER.exception("Webhook processing failed")
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": safe_text(exc)})
            return
        self.send_json(status_code, response)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - BaseHTTPRequestHandler API
        LOGGER.info("%s - %s", self.address_string(), format % args)


def run_server(host: str = "", port: int = 8300) -> None:
    logging.basicConfig(level=os.getenv("ERRORSWEEP_WEBHOOK_LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = ThreadingHTTPServer((host, port), BillingWebhookHandler)
    LOGGER.info("Starting %s on %s:%s", APP_NAME, host or "0.0.0.0", port)
    server.serve_forever()


if __name__ == "__main__":
    run_server(
        host=os.getenv("ERRORSWEEP_BILLING_WEBHOOK_HOST", ""),
        port=int(os.getenv("ERRORSWEEP_BILLING_WEBHOOK_PORT", "8300")),
    )
