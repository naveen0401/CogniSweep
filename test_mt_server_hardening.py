from pathlib import Path


WORKERS = [
    Path("opus_mt_server_v45.py"),
    Path("indictrans2_worker.py"),
    Path("madlad_mt_server.py"),
]
WORKFLOW = Path(".github/workflows/release-gate.yml")
MT_CHECK = Path("deploy/mt_endpoint_check.py")
LIVE_ENDPOINT_TESTS = [
    Path("test_indictrans2_worker.py"),
    Path("test_madlad_endpoint.py"),
    Path("test_opus_mt_endpoint.py"),
]


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_mt_workers_fail_closed_without_api_keys():
    for path in WORKERS:
        text = source(path)
        assert "SERVER_API_KEY = os.getenv" in text
        assert "def require_server_api_key_configured" in text
        assert "raise RuntimeError" in text
        assert '@app.on_event("startup")' in text
        assert "if not SERVER_API_KEY:\n        return" not in text
        assert "HTTPException(status_code=503" in text


def test_mt_workers_cap_request_size_and_generation():
    for path in WORKERS:
        text = source(path)
        for token in [
            "MAX_SEGMENTS",
            "MAX_CHARS_PER_TEXT",
            "MAX_TOTAL_CHARS",
            "MAX_INPUT_LENGTH",
            "MAX_NEW_TOKENS",
            "MAX_BATCH_SIZE",
            "RATE_LIMIT_REQUESTS",
            "RATE_LIMIT_WINDOW_SECONDS",
            "def enforce_rate_limit",
            "def validate_translate_request",
            "HTTPException(status_code=413",
            "HTTPException(status_code=429",
            "max_new_tokens=MAX_NEW_TOKENS",
        ]:
            assert token in text, f"{path} missing {token}"


def test_release_gate_includes_mt_hardening_check():
    workflow = source(WORKFLOW)
    mt_check = source(MT_CHECK)
    assert "python test_mt_server_hardening.py" in workflow
    assert "require_server_api_key_configured" in mt_check
    assert "validate_translate_request" in mt_check
    assert "MAX_NEW_TOKENS" in mt_check
    assert "enforce_rate_limit" in mt_check
    assert "RATE_LIMIT_REQUESTS" in mt_check


def test_live_endpoint_probes_are_opt_in():
    for path in LIVE_ENDPOINT_TESTS:
        text = source(path)
        assert "RUN_LIVE_MT_TESTS" in text
        assert "raise SystemExit(0)" in text


if __name__ == "__main__":
    test_mt_workers_fail_closed_without_api_keys()
    test_mt_workers_cap_request_size_and_generation()
    test_release_gate_includes_mt_hardening_check()
    test_live_endpoint_probes_are_opt_in()
    print("MT server hardening checks passed.")
