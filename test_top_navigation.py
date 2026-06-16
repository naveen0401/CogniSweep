from pathlib import Path


APP = Path("app.py")


def source() -> str:
    return APP.read_text(encoding="utf-8")


def function_body(name: str, end_name: str) -> str:
    text = source()
    start = text.index(f"def {name}")
    end = text.index(f"def {end_name}", start)
    return text[start:end]


def test_topnav_uses_one_permission_ordered_renderer():
    body = function_body("render_navigation", "now_stamp")

    assert "nav_pages = topnav_page_order(pages)" in body
    assert "primary_nav_pages = [page for page in nav_pages if page in WORKSPACE_PAGES]" in body
    assert "owner_nav_pages = [page for page in OWNER_PAGES if page in pages] if is_owner() else []" in body
    assert "for page in primary_nav_pages" in body
    assert "for page in owner_nav_pages" in body
    assert "OWNER_PAGES if is_owner()" not in body
    assert "owner_strip" not in body


def test_platform_owner_navigation_uses_two_rows_without_scroll_strip():
    text = source()
    body = function_body("render_navigation", "now_stamp")

    assert "es-topnav-owner-row" in body
    assert "es-topnav-owner-links" in body
    assert "es-topnav-owner-link" in body
    assert "Owner tools" in body
    links_start = text.index(".es-topnav-links")
    link_start = text.index(".es-topnav-link", links_start + len(".es-topnav-links"))
    links_css = text[links_start:link_start]
    assert "overflow-x: auto" not in links_css
    assert "overflow: visible;" in links_css
    assert ".es-topnav-owner-row" in text
    assert ".es-topnav-owner-link" in text


def test_notes_and_language_tools_are_clickable_panels():
    text = source()
    body = function_body("render_navigation", "now_stamp")

    assert "def render_topnav_notes_panel" in text
    assert "def normalized_notification_note" in text
    assert "def notification_badge_count" in text
    assert "def render_topnav_language_panel" in text
    assert 'topnav_panel_link(active_page, "notes")' in body
    assert 'topnav_panel_link(active_page, "language")' in body
    assert 'href="{escape(notes_href)}"' in body
    assert 'href="{escape(language_href)}"' in body
    assert '>NOTES<span class="es-topnav-badge">{notification_count}</span></a>' in body
    assert '>{escape(language_code)}</a>' in body
    assert "notification_badge_count(normalized_notification_notes" in body


def test_team_billing_admin_visibility_comes_from_allowed_pages():
    body = function_body("render_navigation", "now_stamp")
    text = source()
    allowed_pages = function_body("allowed_pages", "is_owner")

    assert 'account_menu_pages = ["Jobs", "Team & Roles", "Billing", "Admin"' in body
    assert "if page in pages:" in body
    assert "Team & Roles" in body
    assert "Billing" in body
    assert "Admin" in body
    assert "ROLE_PAGE_ACCESS" not in body
    assert "ROLE_PERMISSION_MATRIX" in text
    assert "PAGE_PERMISSIONS" in text
    assert 'if not has_permission("team.manage")' in text
    assert 'if not has_permission("billing.access")' in text
    assert 'if not has_permission("admin.workspace")' in text
    assert "Update user permissions" in text
    assert '"permission_flags": ", ".join(updated_flags)' in text
    assert 'if "Talent Database" in pages and not can_access_talent_database()' in allowed_pages
    assert 'pages.remove("Talent Database")' in allowed_pages


def test_jobs_tool_is_hidden_without_permission():
    body = function_body("render_navigation", "now_stamp")

    assert 'if "Jobs" in pages else ""' in body
    assert 'href="#"' not in body


def test_job_history_page_is_registered_with_renderer_and_schema():
    text = source()
    persistence = Path("production_persistence.py").read_text(encoding="utf-8")
    schema = Path("supabase_v42_release_schema.sql").read_text(encoding="utf-8")

    assert '"Job History"' in text[text.index("WORKSPACE_PAGES"):text.index("ALL_APP_PAGES")]
    assert '"Job History": "page.jobs"' in text
    assert '"job-history": "Job History"' in text
    assert '"Job History": page_job_history' in text
    assert "def page_job_history()" in text
    assert "job_history_rows_for_user(user)" in text
    assert "render_job_history_table" in text
    assert "human_review_editor_link(editor_job_id)" in text
    for column in ["file_name", "review_job_id", "editor_job_id", "metadata_json"]:
        assert f'"{column}"' in persistence
        assert column in schema


def test_notes_drawer_has_professional_actions_and_sanitizer():
    text = source()
    start = text.index("def notification_time_value")
    end = text.index("def render_topnav_language_panel", start)
    body = text[start:end]

    assert 'aria-label="Notification drawer"' in body
    assert "Verify email" in body
    assert "Complete profile" in body
    assert "Mark as read" in body
    assert "Dismiss" in body
    assert "sanitize_notification_message" in body
    assert 're.sub(r"\\?public=(verify|reset)&token=' in body
    assert "notification_dedupe_key" in body
    assert "notification_dismissed_at(item)" in body


def test_notification_read_dismiss_columns_are_persisted():
    persistence = Path("production_persistence.py").read_text(encoding="utf-8")
    schema = Path("supabase_v42_release_schema.sql").read_text(encoding="utf-8")

    for column in ["read_at", "dismissed_at"]:
        assert f'"{column}"' in persistence
        assert column in schema


def test_permission_matrix_models_company_and_individual_access():
    text = source()
    matrix_start = text.index("ROLE_PERMISSION_MATRIX")
    matrix_end = text.index("VALID_USER_ROLES", matrix_start)
    matrix = text[matrix_start:matrix_end]

    assert '"Workspace Owner": WORKFLOW_PERMISSIONS | COMPANY_MANAGEMENT_PERMISSIONS' in matrix
    assert '"Company Admin": WORKFLOW_PERMISSIONS | COMPANY_MANAGEMENT_PERMISSIONS' in matrix
    assert '"Workspace Admin": WORKFLOW_PERMISSIONS | COMPANY_MANAGEMENT_PERMISSIONS' in matrix
    assert '"Project Manager": WORKFLOW_PERMISSIONS' in matrix
    assert '"Team Lead": WORKFLOW_PERMISSIONS' in matrix
    assert '"Individual Owner": WORKFLOW_PERMISSIONS | PERSONAL_WORKSPACE_OWNER_PERMISSIONS' in matrix
    assert '"Individual User": WORKFLOW_PERMISSIONS | {"billing.access", "billing.personal"}' in matrix
    assert '"Freelancer": WORKFLOW_PERMISSIONS | {"billing.access", "billing.personal"}' in matrix
    assert 'if account_type == "individual":' in text
    assert 'can_manage_personal_workspace = role == "Individual Owner"' in text
    assert 'permissions.discard(company_permission)' in text
    assert 'permissions.update(granted_permission_flags(candidate))' in text


if __name__ == "__main__":
    test_topnav_uses_one_permission_ordered_renderer()
    test_platform_owner_navigation_uses_two_rows_without_scroll_strip()
    test_notes_and_language_tools_are_clickable_panels()
    test_team_billing_admin_visibility_comes_from_allowed_pages()
    test_jobs_tool_is_hidden_without_permission()
    test_job_history_page_is_registered_with_renderer_and_schema()
    test_notes_drawer_has_professional_actions_and_sanitizer()
    test_notification_read_dismiss_columns_are_persisted()
    test_permission_matrix_models_company_and_individual_access()
    print("Top navigation checks passed.")
