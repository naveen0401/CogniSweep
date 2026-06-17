import qa_engine_global_v15 as qa


def test_client_correction_patterns_are_cached_across_segments():
    qa._builtin_correction_entries.cache_clear()
    qa._parse_client_correction_lines_cached.cache_clear()
    original_compile = qa._compile_correction_pattern
    compiled_terms = []

    def counting_compile(wrong):
        compiled_terms.append(wrong)
        return original_compile(wrong)

    rules = {
        "chunks": [
            {
                "source": "client_rules.txt",
                "text": "wrnogterm -> rightterm\nbad tone -> better tone",
            }
        ]
    }
    first_segment = {"source": "A", "translation": "This is wrnogterm with bad tone."}
    second_segment = {"source": "B", "translation": "Fix wrnogterm now."}

    try:
        qa._compile_correction_pattern = counting_compile
        first_findings = qa.deterministic_checks_v2(first_segment, rules, target_language="English")
        second_findings = qa.deterministic_checks_v2(second_segment, rules, target_language="English")
    finally:
        qa._compile_correction_pattern = original_compile
        qa._builtin_correction_entries.cache_clear()
        qa._parse_client_correction_lines_cached.cache_clear()

    assert any(row["Wrong Part"] == "wrnogterm" for row in first_findings)
    assert any(row["Wrong Part"] == "wrnogterm" for row in second_findings)
    assert compiled_terms.count("wrnogterm") == 1
    assert compiled_terms.count("bad tone") == 1


if __name__ == "__main__":
    test_client_correction_patterns_are_cached_across_segments()
    print("QA correction cache tests passed.")
