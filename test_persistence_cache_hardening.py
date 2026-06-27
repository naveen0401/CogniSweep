import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
PLATFORM_CONSTANTS = ROOT / "app_platform_constants.py"
RELEASE_CHECK = ROOT / "deploy" / "release_check.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_body(text: str, name: str) -> str:
    match = re.search(rf"^def {name}\(.*?^def ", text, re.S | re.M)
    if match:
        return match.group(0).rsplit("\ndef ", 1)[0]
    match = re.search(rf"^def {name}\(.*", text, re.S | re.M)
    assert match, f"Missing function {name}"
    return match.group(0)


def test_saas_reads_use_streamlit_cache_data_with_generation_key():
    app = source(APP)

    assert "SAAS_CACHE_TTL_SECONDS" in app
    assert "SAAS_CACHE_GENERATION_KEY" in app
    assert "SAAS_CACHEABLE_COLLECTIONS" in app
    assert "@st.cache_data(ttl=SAAS_CACHE_TTL_SECONDS, show_spinner=False)" in app
    assert "def _cached_fetch_saas_records" in app
    assert "cache_generation" in function_body(app, "_cached_fetch_saas_records")
    assert "_cached_fetch_saas_records.clear()" in function_body(app, "clear_saas_record_cache")


def test_auth_and_lifecycle_collections_are_not_cached():
    platform_constants = source(PLATFORM_CONSTANTS)
    match = re.search(r"SAAS_CACHEABLE_COLLECTIONS\s*=\s*\{(?P<body>.*?)\n\}", platform_constants, re.S)
    assert match, "Missing SAAS_CACHEABLE_COLLECTIONS block"
    cacheable = match.group("body")

    for unsafe_collection in ['"users"', '"auth_tokens"', '"task_queue"']:
        assert unsafe_collection not in cacheable


def test_saas_writes_and_deletes_clear_read_cache():
    app = source(APP)

    persist_body = function_body(app, "persist_saas_record")
    remove_body = function_body(app, "remove_saas_record")

    assert "clear_saas_record_cache()" in persist_body
    assert "clear_saas_record_cache()" in remove_body
    assert "except ValueError as exc:" in persist_body
    assert "except requests.RequestException as exc:" in persist_body
    assert "except ValueError as exc:" in remove_body
    assert "except requests.RequestException as exc:" in remove_body


def test_no_silent_exception_passes_remain():
    for path in [APP, ROOT / "production_persistence.py"]:
        text = source(path)
        silent_passes = re.findall(r"except(?:\s+\w+)?(?:\s+as\s+\w+)?:\s*\n\s*pass\b", text)
        assert not silent_passes, f"{path.name} still has silent exception passes"


def test_release_gate_runs_persistence_cache_hardening_check():
    workflow = source(WORKFLOW)
    release_check = source(RELEASE_CHECK)

    assert "python test_persistence_cache_hardening.py" in workflow
    assert "check_persistence_cache_hardening" in release_check
    assert "App persistence cache and exception hardening" in release_check


if __name__ == "__main__":
    test_saas_reads_use_streamlit_cache_data_with_generation_key()
    test_auth_and_lifecycle_collections_are_not_cached()
    test_saas_writes_and_deletes_clear_read_cache()
    test_no_silent_exception_passes_remain()
    test_release_gate_runs_persistence_cache_hardening_check()
    print("Persistence cache hardening checks passed.")
