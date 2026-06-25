from pathlib import Path


APP = Path("app.py")
PERSISTENCE = Path("production_persistence.py")
SCHEMA = Path("supabase_v42_release_schema.sql")


def source() -> str:
    return APP.read_text(encoding="utf-8")


def function_body(name: str, end_name: str) -> str:
    text = source()
    start = text.index(f"def {name}(")
    end = text.index(f"def {end_name}(", start)
    return text[start:end]


def test_login_is_unified_without_role_tabs():
    body = function_body("render_login", "render_signup")

    assert 'st.form("unified_login"' in body
    assert "st.tabs" not in body
    assert '["Platform owner", "Workspace user", "Demo access"]' not in body
    assert "Enter demo workspace" not in body
    assert "render_sso_login_controls" not in body
    assert 'form_submit_button("Login"' in body


def test_signup_collects_basic_account_fields_only():
    body = function_body("render_signup", "render_public_document")

    for label in [
        "Full name",
        "Email",
        "Password",
        "Account type",
        "Enterprise / Company",
        "Individual Contractor",
        "Workspace name",
        "Create account",
    ]:
        assert label in body
    for label in [
        "Phone / WhatsApp",
        "Profile type",
        "Services offered",
        "Target languages",
        "Hourly rate",
        "Per-word rate",
        "Short professional summary",
    ]:
        assert label not in body
    assert '"full_name": clean_name' in body
    assert '"account_type": account_type' in body
    assert 'role = "Workspace Owner" if account_type == "company" else "Individual Owner"' in body
    assert '"profile_completion_status": "pending"' in body
    assert '"signup_source": "basic_signup"' in body
    assert "talent_search_text" in body


def test_profile_completion_prompt_routes_to_account_profile_editor():
    text = source()
    start = text.index("def render_profile_completion_form")
    end = text.index("def render_signup", start)
    body = text[start:end]

    for label in [
        "Complete profile now",
        "Skip for now",
        "attract employers",
    ]:
        assert label in body
    for label in [
        "Profile type",
        "Primary role",
        "Services offered",
        "Source languages",
        "Target languages",
        "Specialized domains",
        "Weekly capacity (hours)",
        "Per-word rate",
        "Short professional summary",
    ]:
        assert label in body
    prompt = body[body.index("def render_profile_completion_prompt"):]
    assert "render_profile_completion_form(user)" not in prompt
    assert "open_account_professional_profile_editor()" in body
    assert 'st.session_state["account_active_section"] = "Professional Profile"' in body
    assert 'st.session_state["account_profile_edit_mode"] = True' in body
    assert 'set_route_query({"es_page": "Account"})' in body
    assert '"profile_completion_status": "completed"' in body
    assert '"profile_completion_status": "skipped"' in body
    assert "PROFILE_COMPLETION_PROMPT_DISMISSED_SESSION_KEY" in body

    due = function_body("profile_completion_prompt_due", "stored_metadata_dict")
    assert 'normalized_profile_completion_status(user) != "completed"' in due
    assert '"skipped"' not in due


def test_dashboard_uses_full_name_display():
    text = source()
    dashboard = function_body("page_dashboard", "page_projects")
    navigation = function_body("render_navigation", "now_stamp")

    assert "def display_name_from_user" in text
    assert 'safe_text(user.get("full_name"))' in text
    assert "display_name_from_user(user)" in dashboard
    assert "first_name_from_user(user)" not in dashboard
    assert "user_name = display_name_from_user(user)" in navigation


def test_talent_database_page_and_route_are_registered():
    text = source()
    page = function_body("page_talent_database", "page_all_workspaces")
    render_app_start = text.index("def render_app")
    render_app_end = text.index('if __name__ == "__main__"', render_app_start)
    render_app = text[render_app_start:render_app_end]

    assert "def page_talent_database()" in text
    assert '"Talent Database": page_talent_database' in text
    assert '"Talent Database"' in text[text.index("OWNER_PAGES"):text.index("WORKSPACE_PAGES")]
    assert '"Talent Manager": {"page.jobs", "talent.search"}' in text
    assert "PREMIUM_TALENT_PLANS" in text
    assert "def has_active_premium_entitlement" in text
    assert "def can_access_talent_database" in text
    assert "def render_talent_premium_required_page" in text
    assert "Premium Required" in text
    assert "Talent Database is a Premium feature" in text
    assert "if page == \"Talent Database\" and not has_active_premium_entitlement()" in render_app
    assert "render_root_app_shell(render_talent_premium_required_page)" in render_app
    assert "if not has_active_premium_entitlement()" in page
    assert "render_talent_premium_required_page()" in page
    assert 'if not has_permission("talent.search")' in text


def test_user_profile_columns_persist_to_database_contract():
    persistence = PERSISTENCE.read_text(encoding="utf-8")
    schema = SCHEMA.read_text(encoding="utf-8")

    for column in [
        "full_name",
        "account_type",
        "permission_flags",
        "phone",
        "profile_type",
        "primary_role",
        "services",
        "languages",
        "domains",
        "availability",
        "weekly_capacity",
        "hourly_rate",
        "per_word_rate",
        "profile_completion_status",
        "profile_completed_at",
        "profile_prompt_dismissed_at",
        "talent_status",
        "talent_search_text",
        "metadata_json",
    ]:
        assert f'"{column}"' in persistence
        assert column in schema
    assert "idx_errorsweep_users_talent_search" in schema


def test_public_signup_defaults_open_in_production():
    defaults = function_body("feature_flag_defaults", "parse_bool_flag")

    assert '"public_registration": True' in defaults
    assert '"demo_access": local_mode' in defaults
    assert '"billing_collection": local_mode' in defaults


def test_forgot_password_reports_dispatch_status():
    login = function_body("render_login", "profile_language_defaults")
    reset = function_body("queue_password_reset_email", "hydrate_saas_state_for_user")

    assert "return_record: bool = False" in reset
    assert "dispatched = dispatch_queued_email_if_configured(record)" in reset
    assert "return link, dispatched" in reset
    assert "reset_url, reset_record = queue_password_reset_email" in login
    assert 'reset_status == "sent"' in login
    assert 'reset_status == "failed"' in login
    assert "has been sent or queued" in login


if __name__ == "__main__":
    test_login_is_unified_without_role_tabs()
    test_signup_collects_basic_account_fields_only()
    test_profile_completion_prompt_routes_to_account_profile_editor()
    test_dashboard_uses_full_name_display()
    test_talent_database_page_and_route_are_registered()
    test_user_profile_columns_persist_to_database_contract()
    test_public_signup_defaults_open_in_production()
    test_forgot_password_reports_dispatch_status()
    print("Auth talent upgrade checks passed.")
