from pathlib import Path


APP = Path("app.py")


def source() -> str:
    return APP.read_text(encoding="utf-8")


def function_body(text: str, name: str, next_name: str) -> str:
    start = text.index(f"def {name}")
    end = text.index(f"def {next_name}", start)
    return text[start:end]


def test_scorecard_generates_translator_scorecard_and_reviewer_final_qa_report():
    text = source()
    page = function_body(text, "page_scorecards", "sectioned_page_layout")

    assert "Translator file" in page
    assert "Reviewer/final file" in page
    assert "Translator scorecard is generated from reviewer recorded edits/issues against the translator file" in page
    assert "Optional QA report checks the reviewer/final file" in page
    assert "Download Translator Scorecard Excel" in page
    assert "Download Reviewer Final QA Excel" in page
    assert "CogniSweep_Translator_Scorecard.xlsx" in page
    assert "if scorecard_quality_state.get(\"has_any\"):" in page
    assert "create_qa_excel_report(qa_rows, qa_findings, scorecard_quality_state)" in page
    assert "Reviewer final QA report was not generated" in page


def test_scorecard_qa_rows_use_reviewer_file_as_final_deliverable():
    text = source()
    helper = function_body(text, "scorecard_reviewer_rows_for_qa", "build_scorecard_qa_rows")

    assert 'r = rev_rows[idx] if idx < len(rev_rows or []) else {}' in helper
    assert 'reviewer_target = safe_text(r.get("target") or r.get("translation") or r.get("source", ""))' in helper
    assert '"target": reviewer_target' in helper
    assert '"translation": reviewer_target' in helper
    assert '"match": "Reviewer final"' in helper


if __name__ == "__main__":
    test_scorecard_generates_translator_scorecard_and_reviewer_final_qa_report()
    test_scorecard_qa_rows_use_reviewer_file_as_final_deliverable()
    print("Scorecard flow checks passed.")
