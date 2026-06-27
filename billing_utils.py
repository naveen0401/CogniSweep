"""Pure billing calculation and formatting helpers."""
from __future__ import annotations

from typing import Any, Dict

from billing_config import PLAN_CATALOG
from text_utils import safe_text


def plan_record(name: str) -> Dict[str, Any]:
    requested = safe_text(name).lower()
    return next((plan for plan in PLAN_CATALOG if plan["name"].lower() == requested), PLAN_CATALOG[0])


def format_money(amount: Any, currency: str = "INR", decimals: bool = False) -> str:
    try:
        value = float(amount or 0)
    except Exception:
        value = 0.0
    precision = 2 if decimals and value != int(value) else 0
    return f"{safe_text(currency or 'INR')} {value:,.{precision}f}"


def money_value(amount: Any) -> float:
    try:
        return max(0.0, float(amount or 0))
    except Exception:
        return 0.0


def invoice_amounts(total_amount: Any, tax_rate_percent: Any) -> Dict[str, float]:
    total = money_value(total_amount)
    try:
        tax_rate = max(0.0, float(tax_rate_percent or 0))
    except Exception:
        tax_rate = 0.0
    subtotal = total / (1 + tax_rate / 100) if tax_rate else total
    tax_amount = max(0.0, total - subtotal)
    return {
        "subtotal": round(subtotal, 2),
        "tax_rate_percent": round(tax_rate, 2),
        "tax_amount": round(tax_amount, 2),
        "total": round(total, 2),
    }
