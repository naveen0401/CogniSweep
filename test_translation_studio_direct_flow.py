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


def test_direct_translation_tasks_route_to_history_with_delivery_downloads():
    app = source(APP)
    page_pro = function_body(app, "page_pro", "render_assist_panel")
    history_rows = function_body(app, "job_history_rows_for_user", "job_history_status_class")
    history_table = function_body(app, "render_job_history_table", "page_projects")
    submit_sync = function_body(app, "mark_related_editor_records_submitted", "submit_external_editor_payload")

    assert "render_translation_studio_task_panel()" not in page_pro
    assert "Track it from History when processing is complete." in app
    assert "def job_history_is_direct_workflow_record" in app
    assert "direct_workflow_record = job_history_is_direct_workflow_record(record)" in app
    assert "is_direct_translation_studio_record" not in history_rows
    assert "direct_translation_studio_record_is_submitted" not in app
    assert "translation_delivery_zip(" in page_pro
    assert "Download delivery ZIP" in page_pro
    assert "result_file" in history_table
    assert "Download result" in history_table
    assert 'st.session_state.get("task_queue", [])' in submit_sync
    assert 'persist_saas_record("task_queue", dict(task))' in submit_sync


def test_async_pro_translation_returns_delivery_zip_without_project_job_record():
    worker = source(ASYNC_WORKER)
    pro = function_body(worker, "process_pro_task", "process_task_payload")

    assert 'save_saas_record(\n        "jobs",' not in pro
    assert "create_translation_delivery_zip(review_rows, primary, review_workbook=workbook)" in pro
    assert "result_ref=review_job_id" in pro
    assert '"result_file": delivery_manifest' in pro
    assert '"result_files": [review_manifest]' in pro


def test_media_studio_subtitling_offers_download_and_human_editor():
    app = source(APP)
    setup = function_body(app, "render_subtitle_transcription_setup", "render_focused_subtitle_workspace")

    assert "CogniSweep_Subtitling_Delivery.zip" in setup
    assert "media_subtitling_delivery" in setup
    assert "Download delivery ZIP" in setup
    assert "Open Human Editor" in setup
    assert "an AI or managed MT route is available" in setup


if __name__ == "__main__":
    test_direct_translation_tasks_route_to_history_with_delivery_downloads()
    test_async_pro_translation_returns_delivery_zip_without_project_job_record()
    test_media_studio_subtitling_offers_download_and_human_editor()
    print("Translation Studio direct-flow checks passed.")
