from pathlib import Path


APP = Path(__file__).with_name("app.py")


def read_app() -> str:
    return APP.read_text(encoding="utf-8")


def function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"def {name}")
    end = source.index(f"def {next_name}", start)
    return source[start:end]


def test_job_history_uses_left_task_browser_and_right_task_frame() -> None:
    app = read_app()
    body = function_body(app, "page_job_history", "page_qa")

    assert 'st.columns([0.25, 0.75], gap="small")' in body
    assert "Task browser" in body
    assert 'st.expander("Project tasks"' in body
    assert 'st.expander("Individual tasks"' in body
    assert 'st.selectbox("Year"' in body
    assert 'job_history_selected_scope' in body
    assert 'project::' in body
    assert 'individual::' in body
    assert "render_job_history_table(selected_rows" in body
    assert "es-history-frame-title" in app
    assert "st-key-job_history_individual_year" in app
    assert "st-key-job_history_month_nav_" in app


if __name__ == "__main__":
    test_job_history_uses_left_task_browser_and_right_task_frame()
    print("Job history panel checks passed.")
