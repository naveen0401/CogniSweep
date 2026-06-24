import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIREMENT_FILES = [
    "requirements.txt",
]
LOCK_FILE = "requirements.lock.txt"
PINNED_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[A-Za-z0-9_.!+*-]+(?:\s*;.+)?$"
)
DOCKER_BASE_DIGEST = "python:3.11-slim@sha256:"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def active_lines(path: str) -> list[str]:
    return [
        line.strip()
        for line in read(path).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def requirement_name(line: str) -> str:
    text = line.split(";", 1)[0].strip()
    text = re.split(r"\s*(?:===|==|~=|>=|<=|>|<|!=)\s*", text, maxsplit=1)[0]
    return text.split("[", 1)[0].strip().lower().replace("_", "-")


def assert_exact_pins(path: str) -> None:
    unpinned = [line for line in active_lines(path) if not PINNED_REQUIREMENT.fullmatch(line)]
    assert not unpinned, f"{path} contains non-exact requirement pins: {unpinned}"


def test_all_requirements_are_exactly_pinned():
    for path in REQUIREMENT_FILES + [LOCK_FILE]:
        assert_exact_pins(path)


def test_lockfile_covers_main_direct_dependencies():
    direct = {requirement_name(line) for line in active_lines("requirements.txt")}
    locked = {requirement_name(line) for line in active_lines(LOCK_FILE)}
    missing = sorted(direct - locked)
    assert not missing, f"{LOCK_FILE} is missing direct requirements: {missing}"
    assert len(locked) > len(direct)


def test_dockerfiles_use_digest_pinned_base_and_lockfile():
    dockerfile = read("Dockerfile")

    assert f"FROM {DOCKER_BASE_DIGEST}" in dockerfile
    assert "python -m pip install --upgrade pip==26.1.2" in dockerfile
    assert "python -m pip install -r requirements.lock.txt" in dockerfile


def test_release_gate_runs_dependency_locking_check():
    workflow = read(".github/workflows/release-gate.yml")
    release_check = read("deploy/release_check.py")

    assert "python test_dependency_locking.py" in workflow
    assert "requirements.lock.txt" in release_check
    assert DOCKER_BASE_DIGEST in release_check


if __name__ == "__main__":
    test_all_requirements_are_exactly_pinned()
    test_lockfile_covers_main_direct_dependencies()
    test_dockerfiles_use_digest_pinned_base_and_lockfile()
    test_release_gate_runs_dependency_locking_check()
    print("Dependency locking checks passed.")
