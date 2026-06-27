from pathlib import Path


APP = Path(__file__).with_name("app.py")


def read_app() -> str:
    return APP.read_text(encoding="utf-8")


def function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"def {name}")
    end = source.index(f"def {next_name}", start)
    return source[start:end]


def test_projects_page_uses_clean_selector_and_compact_detail_frame() -> None:
    app = read_app()
    body = function_body(app, "page_projects", "page_jobs")

    assert 'st.columns([0.26, 0.74], gap="small")' in body
    assert 'key=f"project_workspace_nav_{idx}"' in body
    assert 'st.radio("Open project"' not in body
    assert "display_records(projects)" not in body
    assert "es-project-details-line" in app
    assert "target_summary = f\"{len(target_languages)} target languages\"" in body
    assert 'st.markdown("#### Create task in this project")' in body
    assert 'submit_label="Create task"' in body
    assert 'type_label="Task type"' in body
    assert 'st.markdown("#### Project tasks")' in body


if __name__ == "__main__":
    test_projects_page_uses_clean_selector_and_compact_detail_frame()
    print("Projects page layout checks passed.")
