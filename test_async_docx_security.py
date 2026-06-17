import io
import zipfile

import async_workflow_processor as worker


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(document_xml: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def test_async_docx_parser_extracts_tables_and_body_paragraphs():
    data = make_docx(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{WORD_NS}">
  <w:body>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Source text</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Target text</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:p><w:r><w:t>Standalone paragraph</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    )

    rows = worker.parse_docx(data)

    assert rows[0]["location"] == "Table 1 Row 1"
    assert rows[0]["source"] == "Source text"
    assert rows[0]["target"] == "Target text"
    assert rows[1]["location"] == "Paragraph 1"
    assert rows[1]["source"] == "Standalone paragraph"


def test_async_docx_parser_rejects_dtd_entities():
    data = make_docx(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE w:document [<!ENTITY boom "boom">]>
<w:document xmlns:w="{WORD_NS}">
  <w:body><w:p><w:r><w:t>&boom;</w:t></w:r></w:p></w:body>
</w:document>"""
    )

    try:
        worker.parse_docx(data)
    except ValueError as exc:
        assert "DTD/entity" in str(exc)
    else:
        raise AssertionError("Expected DOCX DTD/entity payload to be rejected.")


if __name__ == "__main__":
    test_async_docx_parser_extracts_tables_and_body_paragraphs()
    test_async_docx_parser_rejects_dtd_entities()
    print("Async DOCX security tests passed.")
