import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(".")
REHEARSAL = ROOT / "deploy" / "launch_rehearsal.py"
RELEASE_CHECK = ROOT / "deploy" / "release_check.py"
APP = ROOT / "app.py"
SMOKE = ROOT / "production_smoke_test.py"
README = ROOT / "deploy" / "README_DEPLOYMENT.md"
RUNBOOK = ROOT / "deploy" / "LAUNCH_RUNBOOK.md"
IMPLEMENTATION = ROOT / "implementation.md"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_launch_rehearsal_script_contract():
    text = source(REHEARSAL)

    assert "Run a repeatable CogniSweep launch rehearsal" in text
    assert "def run_public_route_probes" in text
    assert "billing_success" in text
    assert "billing_cancel" in text
    assert "def run_worker_probes" in text
    assert "ERRORSWEEP_ASYNC_WORKER_URL" in text
    assert "ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL" in text
    assert "production_smoke_test.py" in text
    assert "deploy/launch_env_check.py" in text
    assert "deploy/release_check.py" in text
    assert "--probe-public" in text
    assert "--probe-workers" in text


def test_launch_rehearsal_is_in_release_and_operator_docs():
    for path in [RELEASE_CHECK, APP, SMOKE, README, RUNBOOK, IMPLEMENTATION]:
        assert "deploy/launch_rehearsal.py" in source(path)


def test_launch_rehearsal_json_smoke_without_external_probes():
    completed = subprocess.run(
        [
            sys.executable,
            "deploy/launch_rehearsal.py",
            "--env-file",
            "deploy/.env.production.example",
            "--skip-release-check",
            "--skip-launch-env-check",
            "--skip-smoke-test",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["summary"]["checks"] == 3
    assert any(row["Check"] == "Environment file" for row in payload["results"])
    assert any(row["Check"] == "Public base URL" for row in payload["results"])


def test_smoke_test_rejects_todo_secret_placeholders():
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = "TODO_openai_api_key"
    env["ERRORSWEEP_MANAGED_AI_ENABLED"] = "false"
    env["ERRORSWEEP_EMAIL_PROVIDER"] = "resend"
    env["ERRORSWEEP_EMAIL_FROM"] = "TODO_verified_sender_email"
    env["RESEND_API_KEY"] = "TODO_resend_api_key"

    completed = subprocess.run(
        [sys.executable, "production_smoke_test.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    ai_row = next(row for row in payload["results"] if row["Check"] == "Production AI fallback route")
    sender_row = next(row for row in payload["results"] if row["Check"] == "Verified sender")
    assert ai_row["Status"] == "Blocker"
    assert sender_row["Status"] == "Blocker"


if __name__ == "__main__":
    test_launch_rehearsal_script_contract()
    test_launch_rehearsal_is_in_release_and_operator_docs()
    test_launch_rehearsal_json_smoke_without_external_probes()
    test_smoke_test_rejects_todo_secret_placeholders()
    print("Launch rehearsal checks passed.")
