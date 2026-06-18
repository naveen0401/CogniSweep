from pathlib import Path


APP = Path(__file__).with_name("app.py")


def read_app() -> str:
    return APP.read_text(encoding="utf-8")


def test_session_token_preserves_user_timezone() -> None:
    source = read_app()
    assert 'SESSION_TOKEN_USER_FIELDS = ("email", "role", "account_type", "workspace", "plan", "status", "email_verified", "timezone")' in source


def test_browser_timezone_is_synced_before_routing() -> None:
    source = read_app()
    assert 'BROWSER_TIMEZONE_QUERY_PARAM = "es_tz"' in source
    assert "def sync_browser_timezone() -> None:" in source
    assert "def install_local_time_render_bridge() -> None:" in source
    assert "Intl.DateTimeFormat().resolvedOptions().timeZone" in source
    assert 'time[data-es-local-time]' in source
    main_start = source.index('if __name__ == "__main__":')
    main_body = source[main_start : source.index("if query_get(\"es_logout\")", main_start)]
    assert "sync_browser_timezone()" in main_body
    assert "install_local_time_render_bridge()" in main_body


def test_dashboard_greeting_uses_local_timezone_not_server_hour() -> None:
    source = read_app()
    start = source.index("def page_dashboard")
    end = source.index("def project_identity", start)
    body = source[start:end]
    assert "local_hour = datetime.now(local_timezone()).hour" in body
    assert "datetime.now().hour" not in body


def test_history_uses_shared_utc_to_local_formatter() -> None:
    source = read_app()
    formatter_start = source.index("def format_local_time")
    formatter_end = source.index("def display_records", formatter_start)
    formatter_body = source[formatter_start:formatter_end]
    assert "parse_datetime_value(value, naive_tz=timezone.utc)" in formatter_body
    assert "local_dt = dt.astimezone(local_timezone())" in formatter_body
    assert "def local_time_html(value: Any) -> str:" in formatter_body
    assert 'data-es-local-time datetime=' in formatter_body

    parser_start = source.index("def parse_record_datetime")
    parser_end = source.index("def retention_cutoff", parser_start)
    parser_body = source[parser_start:parser_end]
    assert "parse_datetime_value(value, naive_tz=timezone.utc)" in parser_body

    history_start = source.index("def render_job_history_table")
    history_end = source.index("def page_projects", history_start)
    history_body = source[history_start:history_end]
    assert "value_html=local_time_html(updated_value)" in history_body


def test_display_records_handles_title_case_time_columns() -> None:
    source = read_app()
    start = source.index("def display_records")
    end = source.index("def display_dataframe", start)
    body = source[start:end]
    assert "key.lower() in cols" in body
