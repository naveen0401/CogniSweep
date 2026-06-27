"""Billing and internal-access configuration for CogniSweep."""
from __future__ import annotations

from app_runtime_config import runtime_env


PLAN_CATALOG = [
    {
        "name": "Trial",
        "monthly": 0,
        "annual": 0,
        "currency": "INR",
        "trial_days": 14,
        "seats": 2,
        "segments": 500,
        "characters": 100_000,
        "label": "Free trial with mandate",
        "description": "Validate QA, Pro review, scorecards, and workspace setup. Card or UPI mandate required; cancel anytime before trial ends.",
    },
    {
        "name": "Pro",
        "monthly": 3999,
        "annual": 39990,
        "currency": "INR",
        "seats": 5,
        "segments": 10_000,
        "characters": 2_000_000,
        "label": "Growing teams",
        "description": "Production localization QA, Pro translation routing, and reviewer workflows.",
    },
    {
        "name": "Agency",
        "monthly": 11999,
        "annual": 119990,
        "currency": "INR",
        "seats": 20,
        "segments": 50_000,
        "characters": 10_000_000,
        "label": "Multi-client delivery",
        "description": "Higher-volume project, QA, subtitle, scorecard, and team management workflows.",
    },
    {
        "name": "Enterprise",
        "monthly": 0,
        "annual": 0,
        "currency": "INR",
        "seats": 100,
        "segments": 250_000,
        "characters": 50_000_000,
        "label": "Custom plan",
        "description": "Custom usage, SSO, security review, dedicated deployment, and guided onboarding.",
    },
    {
        "name": "Unlimited",
        "monthly": 0,
        "annual": 0,
        "currency": "INR",
        "seats": 1_000_000,
        "segments": 1_000_000_000,
        "characters": 1_000_000_000_000,
        "label": "Unlimited internal access",
        "description": "Unlimited workspace access for authorized internal use.",
    },
]
PUBLIC_BILLING_PLAN_NAMES = {"Trial", "Pro", "Agency", "Enterprise"}
EMAIL_DISPATCH_BATCH_LIMIT = int(runtime_env("ERRORSWEEP_EMAIL_DISPATCH_BATCH_LIMIT", "25"))
AUTH_TOKEN_TTL_SECONDS = int(runtime_env("ERRORSWEEP_AUTH_TOKEN_TTL_SECONDS", str(60 * 60 * 24)))
COMPLIANCE_ACK_LABEL = "I accept the Terms of Service, Privacy Policy, and NDA/confidentiality obligations for this workspace."
UNLIMITED_ACCESS_WORKSPACE = (
    runtime_env("ERRORSWEEP_UNLIMITED_ACCESS_WORKSPACE")
    or runtime_env("COGNISWEEP_UNLIMITED_ACCESS_WORKSPACE")
    or "CogniSweep Unlimited Workspace"
).strip() or "CogniSweep Unlimited Workspace"
UNLIMITED_ACCESS_EMAIL_SECRET = "ERRORSWEEP_UNLIMITED_ACCESS_EMAIL"
UNLIMITED_ACCESS_PASSWORD_HASH_SECRET = "ERRORSWEEP_UNLIMITED_ACCESS_PASSWORD_HASH"
