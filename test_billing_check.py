import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(".")
CHECK = ROOT / "deploy" / "billing_check.py"
RELEASE_CHECK = ROOT / "deploy" / "release_check.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"
README = ROOT / "deploy" / "README_DEPLOYMENT.md"
RUNBOOK = ROOT / "deploy" / "LAUNCH_RUNBOOK.md"
IMPLEMENTATION = ROOT / "implementation.md"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_billing_check_script_contract():
    text = source(CHECK)

    for token in [
        "Validate ErrorSweep billing and webhook launch readiness",
        "def validate_receiver_contract",
        "def validate_env_config",
        "def run_local_smoke",
        "def probe_receiver_health",
        "billing_webhook_receiver.py",
        "ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL",
        "ERRORSWEEP_WEBHOOK_APPLY_UPDATES",
        "Stripe/Razorpay",
        "--probe-health",
    ]:
        assert token in text


def test_billing_check_is_wired_into_release_docs_and_ci():
    for path in [RELEASE_CHECK, WORKFLOW, README, RUNBOOK, IMPLEMENTATION]:
        assert "deploy/billing_check.py" in source(path)


def test_billing_check_offline_json_has_no_blockers():
    completed = subprocess.run(
        [sys.executable, "deploy/billing_check.py", "--json", "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["summary"]["counts"]["Blocker"] == 0
    assert any(row["Check"] == "Signature enforcement coverage" for row in payload["results"])


if __name__ == "__main__":
    test_billing_check_script_contract()
    test_billing_check_is_wired_into_release_docs_and_ci()
    test_billing_check_offline_json_has_no_blockers()
    print("Billing check tests passed.")
