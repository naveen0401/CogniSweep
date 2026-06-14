import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(".")
CHECK = ROOT / "deploy" / "legal_check.py"
RELEASE_CHECK = ROOT / "deploy" / "release_check.py"
REHEARSAL = ROOT / "deploy" / "launch_rehearsal.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"
README = ROOT / "deploy" / "README_DEPLOYMENT.md"
RUNBOOK = ROOT / "deploy" / "LAUNCH_RUNBOOK.md"
IMPLEMENTATION = ROOT / "implementation.md"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_legal_check_script_contract():
    text = source(CHECK)

    for token in [
        "Validate ErrorSweep legal and compliance launch readiness",
        "def validate_app_contract",
        "def validate_env_config",
        "def probe_public_routes",
        "Terms of Service",
        "Privacy Policy",
        "Cookie Notice",
        "Data Processing Addendum",
        "ERRORSWEEP_LEGAL_REVIEWED",
        "--probe-public",
    ]:
        assert token in text


def test_legal_check_is_wired_into_release_docs_ci_and_rehearsal():
    for path in [RELEASE_CHECK, WORKFLOW, README, RUNBOOK, IMPLEMENTATION]:
        assert "deploy/legal_check.py" in source(path)

    rehearsal = source(REHEARSAL)
    for token in ['"public": "security"', '"public": "cookies"', '"public": "dpa"']:
        assert token in rehearsal


def test_legal_check_offline_json_has_no_blockers():
    completed = subprocess.run(
        [sys.executable, "deploy/legal_check.py", "--json", "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["summary"]["counts"]["Blocker"] == 0
    assert any(row["Check"] == "Public legal document coverage" for row in payload["results"])


if __name__ == "__main__":
    test_legal_check_script_contract()
    test_legal_check_is_wired_into_release_docs_ci_and_rehearsal()
    test_legal_check_offline_json_has_no_blockers()
    print("Legal check tests passed.")
