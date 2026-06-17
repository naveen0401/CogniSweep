from pathlib import Path


WORKFLOW = Path(".github/workflows/release-gate.yml")
RELEASE_CHECK = Path("deploy/release_check.py")
README = Path("README.md")
RUNBOOK = Path("deploy/LAUNCH_RUNBOOK.md")
DEPLOY_README = Path("deploy/README_DEPLOYMENT.md")
IMPLEMENTATION = Path("implementation.md")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_github_actions_release_gate_contract():
    workflow = source(WORKFLOW)

    for token in [
        "name: CogniSweep Release Gate",
        "pull_request:",
        "push:",
        "release/**",
        "workflow_dispatch:",
        "actions/checkout@v4",
        "actions/setup-python@v5",
        'python-version: "3.11"',
        "python -m pip install -r requirements.txt",
        "python -m py_compile",
        "python test_auth_talent_upgrade.py",
        "python test_launch_public_lock.py",
        "python test_launch_rehearsal.py",
        "python test_backup_check.py",
        "python test_billing_check.py",
        "python test_email_check.py",
        "python test_legal_check.py",
        "python test_persistence_tenant_scope.py",
        "python test_supabase_rls_policies.py",
        "python test_production_persistence_fail_closed.py",
        "python test_editor_job_security.py",
        "python test_mt_server_hardening.py",
        "python test_async_fail_closed.py",
        "python test_dependency_locking.py",
        "python test_persistence_cache_hardening.py",
        "python test_release_gate_workflow.py",
        "deploy/backup_check.py",
        "deploy/billing_check.py",
        "deploy/email_check.py",
        "deploy/legal_check.py",
        "python deploy/release_check.py --strict",
        "python deploy/launch_rehearsal.py",
        "--base-url http://localhost:8501",
        "--skip-release-check",
        "--skip-launch-env-check",
        "--skip-smoke-test",
    ]:
        assert token in workflow

    for endpoint_test in [
        "test_opus_mt_endpoint.py",
        "test_indictrans2_worker.py",
        "test_madlad_endpoint.py",
    ]:
        assert endpoint_test not in workflow


def test_release_gate_is_required_by_release_docs_and_checks():
    for path in [RELEASE_CHECK, README, RUNBOOK, DEPLOY_README, IMPLEMENTATION]:
        text = source(path)
        assert ".github/workflows/release-gate.yml" in text
        assert "release gate" in text.lower()


if __name__ == "__main__":
    test_github_actions_release_gate_contract()
    test_release_gate_is_required_by_release_docs_and_checks()
    print("Release gate workflow checks passed.")
