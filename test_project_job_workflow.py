from pathlib import Path


APP = Path(__file__).with_name("app.py")


def read_app() -> str:
    return APP.read_text(encoding="utf-8")


def function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"def {name}")
    end = source.index(f"def {next_name}", start)
    return source[start:end]


def test_project_job_form_supports_multi_language_assignees_and_ai_choice() -> None:
    app = read_app()
    form = function_body(app, "render_project_job_form", "render_project_job_details")
    creator = function_body(app, "create_project_tasks_for_project", "create_job_for_project")

    assert "PROJECT_TASK_TYPES" in app
    assert "AI_TRANSLATION_TASK_TYPES" in app
    assert "NO_AI_TASK_NOTE" in app
    assert "c2.multiselect(" in form
    assert '"Target languages"' in form
    assert '"Assignee emails"' in form
    assert "assignee_count_key" in form
    assert "st.container(border=True)" in form
    assert "st.form_submit_button(\"+ Add email\"" in form
    assert "assignee_values.append(st.text_input(" in form
    assert "split_assignee_emails(\" \".join(assignee_values))" in form
    assert "deadline_enabled = st.checkbox(\"Add deadline\"" in form
    assert "date_input(\"Deadline date\"" in form
    assert "time_input(\"Deadline time\"" in form
    assert "deadline_iso_from_parts(deadline_date, deadline_time)" in form
    assert "deadline_at=deadline_at" in form
    assert "project_assignment_source_from_uploads" in form
    assert "ai_translation_choice" in form
    assert "NO_AI_TASK_NOTE" in form
    assert "create_project_tasks_for_project(" in form

    assert "for language in languages:" in creator
    assert "bool(parsed_source_rows)" in creator
    assert "notify_project_task_assignees(record, assignees)" in creator
    assert '"assignees": assignees' in creator
    assert '"deadline_at": deadline_at' in creator
    assert '"assignees_json"' not in creator
    assert "NO_AI_TASK_NOTE if ai_mode == \"manual_no_key\"" in creator
    assert "assignment_email_error_messages" in app
    assert "config_value_is_placeholder" in app


def test_jobs_page_uses_clean_task_list_not_status_lanes() -> None:
    app = read_app()
    body = function_body(app, "page_jobs", "page_job_history")

    assert 'st.columns([0.24, 0.76], gap="small")' in body
    assert 'key=f"jobs_project_nav_{idx}"' in body
    assert 'render_jobs_kanban(jobs)' not in body
    assert "display_records(jobs)" not in body
    assert "metrics([" not in body
    assert "render_job_history_table([job_history_row_from_job(job) for job in jobs]" in body
    assert 'st.expander("Create task in this project"' not in body
    assert "render_project_job_form(" not in body
    assert '"Workflow task monitor"' not in body
    assert "render_task_queue_panel()" not in body
    assert "active_project_jobs(selected_project)" in body
    assert "Submitted tasks are available in History." in body


def test_multi_assignee_display_is_blank_except_single_recipient() -> None:
    app = read_app()
    row = function_body(app, "job_history_row_from_job", "job_history_row_from_editor_job")
    table = function_body(app, "render_job_history_table", "page_projects")

    assert "def split_assignee_emails" in app
    assert "def job_single_assignee_display" in app
    assert "def ensure_project_job_editor_session" in app
    assert "def active_project_jobs" in app
    assert "candidates.extend(job_assignee_list(record))" in app
    assert "review_job_id = ensure_project_job_editor_session(job)" in row
    assert '"assignee": job_single_assignee_display(job)' in row
    assert '"no_ai_note": safe_text(metadata.get("no_ai_note"))' in row
    assert '"deadline_at": safe_text(metadata.get("deadline_at"))' in row
    assert 'job_history_detail_item("Assigned to"' in table
    assert 'job_history_detail_item("Deadline"' in table
    assert "es-history-note" in table
    assert 'div[class*="st-key-jobs_project_nav_"] button' in app


if __name__ == "__main__":
    test_project_job_form_supports_multi_language_assignees_and_ai_choice()
    test_jobs_page_uses_clean_task_list_not_status_lanes()
    test_multi_assignee_display_is_blank_except_single_recipient()
    print("Project job workflow checks passed.")
