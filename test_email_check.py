import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(".")
CHECK = ROOT / "deploy" / "email_check.py"
RELEASE_CHECK = ROOT / "deploy" / "release_check.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"
README = ROOT / "deploy" / "README_DEPLOYMENT.md"
RUNBOOK = ROOT / "deploy" / "LAUNCH_RUNBOOK.md"
IMPLEMENTATION = ROOT / "implementation.md"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_email_check_script_contract():
    text = source(CHECK)

    for token in [
        "Validate CogniSweep transactional email launch readiness",
        "def validate_worker_contract",
        "def validate_env_config",
        "def run_local_smoke",
        "email_dispatch_worker.py",
        "email_templates.py",
        "ERRORSWEEP_EMAIL_PROVIDER",
        "ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED",
        "Resend, SendGrid, SMTP",
        "--run-smoke",
    ]:
        assert token in text


def test_email_check_is_wired_into_release_docs_and_ci():
    for path in [RELEASE_CHECK, WORKFLOW, README, RUNBOOK, IMPLEMENTATION]:
        assert "deploy/email_check.py" in source(path)


def test_email_check_offline_json_has_no_blockers():
    completed = subprocess.run(
        [sys.executable, "deploy/email_check.py", "--json", "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["summary"]["counts"]["Blocker"] == 0
    assert any(row["Check"] == "Template event coverage" for row in payload["results"])


if __name__ == "__main__":
    test_email_check_script_contract()
    test_email_check_is_wired_into_release_docs_and_ci()
    test_email_check_offline_json_has_no_blockers()
    print("Email check tests passed.")
