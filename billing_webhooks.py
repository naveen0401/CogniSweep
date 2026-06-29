"""Billing webhook normalization helpers for CogniSweep.

The Streamlit app can use these helpers for owner-side webhook reconciliation
today, and a deployed API worker can reuse the same logic for live provider
webhooks later.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _dig(data: Any, *path: str) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _money_minor_to_major(value: Any) -> float:
    try:
        return round(float(value or 0) / 100, 2)
    except (TypeError, ValueError):
        return 0.0


def _metadata_from(entity: Dict[str, Any]) -> Dict[str, Any]:
    metadata = entity.get("metadata") if isinstance(entity.get("metadata"), dict) else {}
    notes = entity.get("notes") if isinstance(entity.get("notes"), dict) else {}
    return {**notes, **metadata}


def _epoch_seconds(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else 0
    text = _safe_text(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except (TypeError, ValueError):
        pass
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except ValueError:
        return 0


def _first_epoch(*values: Any) -> int:
    for value in values:
        epoch = _epoch_seconds(value)
        if epoch:
            return epoch
    return 0


def verify_stripe_signature(raw_payload: str, signature_header: str, webhook_secret: str, tolerance_seconds: int = 300) -> bool:
    if not raw_payload or not signature_header or not webhook_secret:
        return False
    parts = {}
    for item in signature_header.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts.setdefault(key, []).append(value)
    timestamp = (parts.get("t") or [""])[0]
    signatures = parts.get("v1") or []
    if not timestamp or not signatures:
        return False
    try:
        if tolerance_seconds > 0 and abs(time.time() - int(timestamp)) > tolerance_seconds:
            return False
    except (TypeError, ValueError):
        return False
    signed_payload = f"{timestamp}.{raw_payload}".encode("utf-8")
    expected = hmac.new(webhook_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in signatures)


def verify_razorpay_signature(raw_payload: str, signature_header: str, webhook_secret: str) -> bool:
    if not raw_payload or not signature_header or not webhook_secret:
        return False
    expected = hmac.new(webhook_secret.encode("utf-8"), raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def verify_billing_webhook_signature(provider: str, raw_payload: str, signature_header: str, webhook_secret: str) -> bool:
    provider = _safe_text(provider).lower()
    if provider == "stripe":
        return verify_stripe_signature(raw_payload, signature_header, webhook_secret)
    if provider == "razorpay":
        return verify_razorpay_signature(raw_payload, signature_header, webhook_secret)
    return False


def parse_webhook_json(raw_payload: str) -> Dict[str, Any]:
    data = json.loads(raw_payload or "{}")
    if not isinstance(data, dict):
        raise ValueError("Webhook payload must be a JSON object.")
    return data


def infer_provider(payload: Dict[str, Any], provider: str = "") -> str:
    explicit = _safe_text(provider).lower()
    if explicit and explicit != "auto":
        return explicit
    if _safe_text(payload.get("event")).startswith(("payment.", "subscription.", "invoice.")) and "payload" in payload:
        return "razorpay"
    if _safe_text(payload.get("object")) == "event" and _safe_text(payload.get("type")):
        return "stripe"
    return "manual"


def _normalise_razorpay(payload: Dict[str, Any]) -> Dict[str, Any]:
    event_type = _safe_text(payload.get("event") or "razorpay.event")
    payment = _dig(payload, "payload", "payment", "entity") or {}
    subscription = _dig(payload, "payload", "subscription", "entity") or {}
    order = _dig(payload, "payload", "order", "entity") or {}
    entity = payment or subscription or order
    metadata = _metadata_from(entity)
    amount = _money_minor_to_major(payment.get("amount") or subscription.get("current_end_amount") or order.get("amount"))
    status = _safe_text(entity.get("status"))
    if event_type in {"payment.captured", "order.paid"} or status in {"captured", "paid", "authenticated", "authorized", "active"}:
        mapped_status = "paid"
    elif "activated" in event_type or status == "active":
        mapped_status = "active"
    elif "failed" in event_type or status == "failed":
        mapped_status = "failed"
    elif "cancel" in event_type or status in {"cancelled", "canceled"}:
        mapped_status = "cancelled"
    else:
        mapped_status = status or "received"
    return {
        "provider": "razorpay",
        "event_id": _safe_text(payload.get("id") or entity.get("id") or hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]),
        "event_type": event_type,
        "status": mapped_status,
        "workspace": _safe_text(metadata.get("workspace") or metadata.get("workspace_id")),
        "user_email": _safe_text(metadata.get("user_email") or metadata.get("email") or payment.get("email")),
        "plan": _safe_text(metadata.get("plan")),
        "currency": _safe_text(payment.get("currency") or order.get("currency") or "INR"),
        "amount": amount,
        "provider_payment_id": _safe_text(payment.get("id")),
        "provider_subscription_id": _safe_text(subscription.get("id") or payment.get("subscription_id")),
        "provider_order_id": _safe_text(order.get("id") or payment.get("order_id")),
        "provider_customer_id": _safe_text(entity.get("customer_id")),
        "checkout_id": _safe_text(metadata.get("checkout_id") or metadata.get("checkout_session_id")),
        "event_created_at": _first_epoch(payload.get("created_at"), entity.get("created_at")),
        "metadata": metadata,
    }


def _normalise_stripe(payload: Dict[str, Any]) -> Dict[str, Any]:
    event_type = _safe_text(payload.get("type") or "stripe.event")
    entity = _dig(payload, "data", "object") or {}
    metadata = _metadata_from(entity)
    amount = _money_minor_to_major(
        entity.get("amount_paid")
        or entity.get("amount_total")
        or entity.get("amount_received")
        or entity.get("amount")
    )
    raw_status = _safe_text(entity.get("status"))
    if event_type in {"checkout.session.completed", "invoice.paid", "payment_intent.succeeded"} or raw_status in {"paid", "complete", "succeeded", "active"}:
        mapped_status = "paid"
    elif "failed" in event_type or raw_status in {"failed", "requires_payment_method"}:
        mapped_status = "failed"
    elif "cancel" in event_type or raw_status in {"canceled", "cancelled"}:
        mapped_status = "cancelled"
    else:
        mapped_status = raw_status or "received"
    return {
        "provider": "stripe",
        "event_id": _safe_text(payload.get("id") or entity.get("id") or hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]),
        "event_type": event_type,
        "status": mapped_status,
        "workspace": _safe_text(metadata.get("workspace") or metadata.get("workspace_id") or entity.get("client_reference_id")),
        "user_email": _safe_text(metadata.get("user_email") or metadata.get("email") or _dig(entity, "customer_details", "email")),
        "plan": _safe_text(metadata.get("plan")),
        "currency": _safe_text(entity.get("currency") or "INR").upper(),
        "amount": amount,
        "provider_payment_id": _safe_text(entity.get("payment_intent") or entity.get("id")),
        "provider_subscription_id": _safe_text(entity.get("subscription")),
        "provider_order_id": "",
        "provider_customer_id": _safe_text(entity.get("customer")),
        "checkout_id": _safe_text(metadata.get("checkout_id") or entity.get("id")),
        "event_created_at": _first_epoch(payload.get("created"), entity.get("created")),
        "metadata": metadata,
    }


def normalize_billing_webhook(provider: str, raw_payload: str) -> Dict[str, Any]:
    payload = parse_webhook_json(raw_payload)
    resolved_provider = infer_provider(payload, provider)
    if resolved_provider == "razorpay":
        normalized = _normalise_razorpay(payload)
    elif resolved_provider == "stripe":
        normalized = _normalise_stripe(payload)
    else:
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        normalized = {
            "provider": resolved_provider,
            "event_id": _safe_text(payload.get("id") or payload.get("event_id") or hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()[:24]),
            "event_type": _safe_text(payload.get("type") or payload.get("event_type") or "manual.billing_event"),
            "status": _safe_text(payload.get("status") or "received"),
            "workspace": _safe_text(payload.get("workspace") or metadata.get("workspace")),
            "user_email": _safe_text(payload.get("user_email") or payload.get("email") or metadata.get("user_email")),
            "plan": _safe_text(payload.get("plan") or metadata.get("plan")),
            "currency": _safe_text(payload.get("currency") or "INR"),
            "amount": float(payload.get("amount") or 0),
            "provider_payment_id": _safe_text(payload.get("provider_payment_id") or payload.get("payment_id")),
            "provider_subscription_id": _safe_text(payload.get("provider_subscription_id") or payload.get("subscription_id")),
            "provider_order_id": _safe_text(payload.get("provider_order_id") or payload.get("order_id")),
            "provider_customer_id": _safe_text(payload.get("provider_customer_id") or payload.get("customer_id")),
            "checkout_id": _safe_text(payload.get("checkout_id") or metadata.get("checkout_id")),
            "event_created_at": _first_epoch(
                payload.get("created_at"),
                payload.get("created"),
                payload.get("timestamp"),
                metadata.get("created_at"),
                metadata.get("timestamp"),
            ),
            "metadata": metadata,
        }
    normalized["raw_sha256"] = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
    return normalized
