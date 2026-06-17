import qa_engine_global_v13 as v13
import qa_engine_global_v14 as v14
import qa_engine_global_v15 as v15


def test_legacy_qa_engine_shims_reexport_canonical_v15():
    assert v13.deterministic_checks_v2 is v15.deterministic_checks_v2
    assert v14.deterministic_checks_v2 is v15.deterministic_checks_v2
    assert v13.normalize_for_qa is v15.normalize_for_qa
    assert v14.normalize_for_qa is v15.normalize_for_qa
    assert v13.extract_placeholders is v15.extract_placeholders
    assert v14.extract_placeholders is v15.extract_placeholders


def test_legacy_qa_engine_shims_delegate_unknown_attributes():
    assert v13.__getattr__("deterministic_checks_v2") is v15.deterministic_checks_v2
    assert v14.__getattr__("deterministic_checks_v2") is v15.deterministic_checks_v2


def test_legacy_qa_engine_shims_expose_explicit_public_surface():
    assert "deterministic_checks_v2" in v13.__all__
    assert "deterministic_checks_v2" in v14.__all__
    assert "normalize_for_qa" in v13.__all__
    assert "normalize_for_qa" in v14.__all__
    assert all(not name.startswith("_") for name in v13.__all__)
    assert all(not name.startswith("_") for name in v14.__all__)


if __name__ == "__main__":
    test_legacy_qa_engine_shims_reexport_canonical_v15()
    test_legacy_qa_engine_shims_delegate_unknown_attributes()
    test_legacy_qa_engine_shims_expose_explicit_public_surface()
    print("QA engine shim regression checks passed.")
