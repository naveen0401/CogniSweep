import qa_engine_global_v15 as qa


def _malformed_telugu_findings(target):
    rows = qa.deterministic_checks_v2(
        {"source": "", "translation": target, "location": "1"},
        rules={},
        target_language="Telugu",
    )
    return [row for row in rows if row["Rule ID"].startswith("telugu.unicode.malformed_cluster_hint")]


def test_telugu_malformed_cluster_rule_flags_dangling_virama():
    findings = _malformed_telugu_findings("\u0c15\u0c4d ")

    assert any(row["Rule ID"].endswith(".dangling_virama") for row in findings)


def test_telugu_malformed_cluster_rule_flags_orphan_dependent_sign():
    findings = _malformed_telugu_findings("\u0c3f\u0c15")

    assert any(row["Rule ID"].endswith(".orphan_dependent_sign") for row in findings)


def test_telugu_malformed_cluster_rule_flags_repeated_virama():
    findings = _malformed_telugu_findings("\u0c15\u0c4d\u0c4d\u0c37")

    assert any(row["Rule ID"].endswith(".repeated_virama") for row in findings)


def test_telugu_malformed_cluster_rule_allows_valid_cluster():
    findings = _malformed_telugu_findings("\u0c15\u0c4d\u0c37\u0c3f")

    assert findings == []


if __name__ == "__main__":
    test_telugu_malformed_cluster_rule_flags_dangling_virama()
    test_telugu_malformed_cluster_rule_flags_orphan_dependent_sign()
    test_telugu_malformed_cluster_rule_flags_repeated_virama()
    test_telugu_malformed_cluster_rule_allows_valid_cluster()
    print("Telugu QA rule regression checks passed.")
