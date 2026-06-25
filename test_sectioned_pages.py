from pathlib import Path


APP = Path("app.py")


def source() -> str:
    return APP.read_text(encoding="utf-8")


def function_body(name: str, next_name: str) -> str:
    text = source()
    start = text.index(f"def {name}")
    end_marker = f"def {next_name}" if next_name.startswith(("page_", "platform_", "render_", "sectioned_")) else next_name
    end = text.index(end_marker, start)
    return text[start:end]


def test_shared_sectioned_layout_helper_exists():
    text = source()
    helper = function_body("sectioned_page_layout", "page_memory_rules")
    assert "def sectioned_page_layout" in text
    assert "section_nav_panel" in helper
    assert "es-settings-nav-title" in helper
    assert "es-settings-nav-group" in helper
    assert "st.button(label" in helper
    assert "Current section:" in helper


def test_long_workspace_pages_use_sectioned_layout():
    expected = {
        "page_memory_rules": ("page_team_roles", '"memory_rules"', "Rules sections"),
        "page_team_roles": ("page_billing", '"team_roles"', "Team sections"),
        "page_billing": ("page_account", '"billing"', "Billing sections"),
        "page_account": ("page_admin", '"account"', "Account settings"),
        "page_admin": ("page_owner_console", '"admin"', "Admin sections"),
        "page_owner_console": ("page_payments_received", '"owner_console"', "Owner Console"),
        "page_payments_received": ("page_user_access_matrix", '"payments_received"', "Payments"),
        "page_user_access_matrix": ("page_talent_database", '"user_access_matrix"', "Access Matrix"),
        "page_talent_database": ("page_all_workspaces", '"talent_database"', "Talent"),
        "page_all_workspaces": ("platform_settings_workspaces", '"all_workspaces"', "Workspaces"),
        "page_platform_settings": ("page_platform_audit_logs", '"platform_settings"', "Settings"),
        "page_platform_audit_logs": ("PAGE_RENDERERS", '"platform_audit_logs"', "Audit Logs"),
    }
    for page_name, (next_name, page_key, nav_title) in expected.items():
        body = function_body(page_name, next_name)
        assert "sectioned_page_layout(" in body
        assert page_key in body
        assert nav_title in body


def test_section_labels_cover_required_long_pages():
    text = source()
    for label in [
        "Profile",
        "Professional Profile",
        "Account Overview",
        "AI Access",
        "Support Queue",
        "Plans & Checkout",
        "Cancel Subscription",
        "Invoices",
        "Records",
        "Rules ZIP Analyzer",
        "Translation Memory",
        "Glossary",
        "DNT",
        "Instructions",
        "Platform Overview",
        "Release Persistence",
        "Current Task",
        "Recent Editor Jobs",
        "Record Payment",
        "Payment Records",
        "Access Matrix",
        "Talent Search",
        "Management Status",
        "Workspace List",
        "Audit Overview",
        "Snapshot",
        "Audit Table",
    ]:
        assert label in text


def test_billing_opens_with_plans_before_overview():
    body = function_body("page_billing", "page_account")
    plans_index = body.index('("Plans & Checkout", "Choose a plan and open Razorpay checkout")')
    overview_index = body.index('("Overview", "Plan, usage, and allowance summary")')

    assert plans_index < overview_index


def test_pricing_cards_start_content_near_top():
    body = function_body("render_pricing_graphic", "billing_provider_label")

    assert "es-pricing-orb" not in body
    assert "plan graphic" not in body
    assert "display:flex;" in body
    assert "flex-direction:column;" in body
    assert "margin-top: auto;" in body


def test_account_professional_profile_uses_inline_edit_mode():
    body = function_body("page_account", "page_admin")
    assert "es-account-sidebar-card" in body
    assert "Professional Profile" in body
    assert "account_profile_edit_mode" in body
    assert "account_professional_profile_form" in body
    assert "render_profile_completion_prompt()" not in body
    assert "render_profile_completion_form(user, form_key=\"account_professional_profile_form\")" in body


def test_team_page_is_workspace_scoped_not_global():
    text = source()
    helper = function_body("workspace_user_records", "find_user_by_email")
    body = function_body("page_team_roles", "page_billing")

    assert "def workspace_user_records" in text
    assert "def team_workspace_options" in text
    assert 'workspace_key.lower() == "platform"' in helper
    assert 'load_saas_records("users", workspace=workspace_key' in helper
    assert "team_workspace_options(user)" in body
    assert 'st.selectbox("Workspace"' in body
    assert "workspace_user_records(workspace)" in body
    assert 'has_permission("platform.users")' not in body
    assert "all_user_records()" not in body
    assert "visible_users = all_visible_users" not in body
    assert "update_workspace_user(selected_email, workspace" in body
    assert "Platform-wide users belong in User Access Matrix, All Workspaces, Talent, or Owner Console." not in body


if __name__ == "__main__":
    test_shared_sectioned_layout_helper_exists()
    test_long_workspace_pages_use_sectioned_layout()
    test_section_labels_cover_required_long_pages()
    test_billing_opens_with_plans_before_overview()
    test_pricing_cards_start_content_near_top()
    test_account_professional_profile_uses_inline_edit_mode()
    test_team_page_is_workspace_scoped_not_global()
    print("Sectioned page layout checks passed.")
