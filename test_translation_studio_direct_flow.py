import re
from pathlib import Path


APP = Path("app.py")
ASYNC_WORKER = Path("async_workflow_processor.py")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_body(text: str, name: str, next_name: str) -> str:
    start = text.index(f"def {name}")
    end = text.index(f"\ndef {next_name}", start)
    return text[start:end]


def test_direct_translation_tasks_stay_on_translation_page_until_editor_submit():
    app = source(APP)
    page_pro = function_body(app, "page_pro", "render_assist_panel")
    history_rows = function_body(app, "job_history_rows_for_user", "job_history_status_class")
    submit_sync = function_body(app, "mark_related_editor_records_submitted", "submit_external_editor_payload")

    assert "render_translation_studio_task_panel()" in page_pro
    assert "Track it on this Translation page." in app
    assert "def is_direct_translation_studio_record" in app
    assert "def direct_translation_studio_record_is_submitted" in app
    assert "def active_direct_translation_studio_tasks_for_user" in app
    assert "is_direct_translation_studio_record(job)" in history_rows
    assert "is_direct_translation_studio_record(editor_job)" in history_rows
    assert "is_direct_translation_studio_record(task)" in history_rows
    assert "not direct_translation_studio_record_is_submitted" in history_rows
    assert 'st.session_state.get("task_queue", [])' in submit_sync
    assert 'persist_saas_record("task_queue", dict(task))' in submit_sync


def test_async_pro_translation_does_not_create_project_job_record():
    worker = source(ASYNC_WORKER)
    pro = function_body(worker, "process_pro_task", "process_task_payload")

    assert 'save_saas_record(\n        "jobs",' not in pro
    assert "result_ref=review_job_id" in pro
    assert '"review_job_id": review_job_id' in pro
    assert '"editor_job_id": review_job_id' in pro


if __name__ == "__main__":
    test_direct_translation_tasks_stay_on_translation_page_until_editor_submit()
    test_async_pro_translation_does_not_create_project_job_record()
    print("Translation Studio direct-flow checks passed.")
