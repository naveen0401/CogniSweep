from pathlib import Path

from pro_reconstruction import sentence_segment_rows_for_pro, split_text_into_sentence_units


def test_pro_sentence_split_preserves_reconstruction_map():
    rows = [
        {
            "id": 7,
            "location": "Paragraph 1",
            "source": "This is sentence one. This is sentence two. This is sentence three.",
            "target": "",
            "status": "Untranslated",
            "match": "",
            "export_ref": {"kind": "docx_paragraph", "paragraph_index": 0},
        }
    ]

    segmented = sentence_segment_rows_for_pro(rows)

    assert [row["source"] for row in segmented] == [
        "This is sentence one.",
        "This is sentence two.",
        "This is sentence three.",
    ]
    assert len({row["reconstruction_map"]["segment_group_id"] for row in segmented}) == 1
    assert [row["reconstruction_map"]["sentence_index"] for row in segmented] == [0, 1, 2]
    assert all(row["export_ref"]["kind"] == "docx_paragraph" for row in segmented)
    assert all(row["export_ref"]["paragraph_index"] == 0 for row in segmented)
    assert all(row["reconstruction_map"]["original_source"] == rows[0]["source"] for row in segmented)


def test_sentence_split_avoids_common_abbreviations():
    units = split_text_into_sentence_units("See e.g. this example. Then continue.")

    assert [unit["text"] for unit in units] == ["See e.g. this example.", "Then continue."]


def test_cat_editor_has_same_container_sentence_export_hooks():
    html = Path("assets/cat_editor_reference.html").read_text(encoding="utf-8")

    assert "function finalTargetForExport(row)" in html
    assert "function originalSourceForExport(row)" in html
    assert "function docxParagraphExportRows()" in html
    assert "segment_group_id" in html


if __name__ == "__main__":
    test_pro_sentence_split_preserves_reconstruction_map()
    test_sentence_split_avoids_common_abbreviations()
    test_cat_editor_has_same_container_sentence_export_hooks()
