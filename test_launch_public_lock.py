from pathlib import Path


APP = Path("app.py")
ENV_TEMPLATE = Path("deploy/.env.production.example")
STREAMLIT_TEMPLATE = Path(".streamlit/secrets.toml.example")
LAUNCH_ENV_CHECK = Path("deploy/launch_env_check.py")
RELEASE_CHECK = Path("deploy/release_check.py")
SMOKE_TEST = Path("production_smoke_test.py")


def source(path: Path = APP) -> str:
    return path.read_text(encoding="utf-8")


def function_body(name: str, end_name: str) -> str:
    text = source()
    start = text.index(f"def {name}")
    end = text.index(f"def {end_name}", start)
    return text[start:end]


def test_public_signup_is_locked_by_launch_preflight():
    text = source()
    signup = function_body("render_signup", "render_public_document")

    assert "def public_launch_preflight_enforced" in text
    assert 'secret("ERRORSWEEP_ENFORCE_PUBLIC_LAUNCH_PREFLIGHT", "true")' in text
    assert "def public_signup_launch_gate" in text
    assert "include_live_checks=False" in text
    assert "def render_public_signup_launch_locked" in text
    assert 'launch_gate = public_signup_launch_gate()' in signup
    assert 'if launch_gate.get("locked")' in signup
    assert "render_public_signup_launch_locked(launch_gate)" in signup
    assert signup.index('launch_gate = public_signup_launch_gate()') < signup.index('if not feature_flag("public_registration")')


def test_platform_settings_exposes_launch_lock_and_preflight_report():
    body = function_body("render_platform_launch_readiness_section", "render_platform_launch_configuration_section")

    assert "preflight_rows = launch_preflight_rows(health)" in body
    assert "preflight_blockers = launch_preflight_blockers(rows=preflight_rows)" in body
    assert "launch_gate = public_signup_launch_gate(health=health, rows=preflight_rows)" in body
    assert '("Launch lock", lock_state' in body
    assert "Production preflight details" in body
    assert "launch_preflight_report(preflight_rows)" in body


def test_launch_lock_is_in_deploy_templates_and_checks():
    key = "ERRORSWEEP_ENFORCE_PUBLIC_LAUNCH_PREFLIGHT"

    assert f"{key}=true" in source(ENV_TEMPLATE)
    assert f'{key} = "true"' in source(STREAMLIT_TEMPLATE)
    assert key in source(RELEASE_CHECK)
    assert "Public launch preflight lock" in source(LAUNCH_ENV_CHECK)
    assert "Public launch preflight lock" in source(SMOKE_TEST)


if __name__ == "__main__":
    test_public_signup_is_locked_by_launch_preflight()
    test_platform_settings_exposes_launch_lock_and_preflight_report()
    test_launch_lock_is_in_deploy_templates_and_checks()
    print("Public launch lock checks passed.")
