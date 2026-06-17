from pathlib import Path


ROOT = Path(".")
SCRIPT = ROOT / "download_models.ps1"
EXAMPLE = ROOT / "model_checksums.sha256.example"
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"
RELEASE_CHECK = ROOT / "deploy" / "release_check.py"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_download_models_requires_checksum_manifest_by_default():
    text = source(SCRIPT)
    for token in [
        "[string]$ChecksumManifest",
        "[switch]$SkipChecksumVerification",
        "Read-ChecksumManifest",
        "Assert-ModelChecksums",
        "Get-FileHash",
        "Algorithm SHA256",
        "Checksum manifest is missing or empty",
    ]:
        assert token in text


def test_download_models_example_manifest_documents_format():
    text = source(EXAMPLE)
    assert "Copy this file to model_checksums.sha256" in text
    assert "<sha256>" in text
    assert "path relative to the models directory" in text


def test_model_download_integrity_is_in_release_gate():
    assert "python test_model_download_integrity.py" in source(WORKFLOW)
    assert "python test_model_download_integrity.py" in source(RELEASE_CHECK)


if __name__ == "__main__":
    test_download_models_requires_checksum_manifest_by_default()
    test_download_models_example_manifest_documents_format()
    test_model_download_integrity_is_in_release_gate()
    print("Model download integrity tests passed.")
