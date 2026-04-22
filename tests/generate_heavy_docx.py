#!/usr/bin/env python3
"""Generate a 100-page .docx with tables for concurrency testing.

No dependencies — builds the Office Open XML by hand.
Output is deterministic (no randomness, no timestamps).
"""

import os
import zipfile

ROWS_PER_TABLE = 20
COLS = 5
TABLES_PER_PAGE = 2  # ~50 lines per page with a table + heading
PAGES = 100

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "gateway", "tests", "fixtures", "heavy.docx")


def make_table(table_num: int) -> str:
    rows = []
    # Header row
    cells = "".join(
        f"<w:tc><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Col {c+1}</w:t></w:r></w:p></w:tc>"
        for c in range(COLS)
    )
    rows.append(f"<w:tr>{cells}</w:tr>")
    # Data rows
    for r in range(ROWS_PER_TABLE):
        cells = "".join(
            f"<w:tc><w:p><w:r><w:t>T{table_num}R{r}C{c}</w:t></w:r></w:p></w:tc>"
            for c in range(COLS)
        )
        rows.append(f"<w:tr>{cells}</w:tr>")
    return f"<w:tbl>{''.join(rows)}</w:tbl>"


def make_page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def make_heading(text: str) -> str:
    return (
        f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
        f"<w:r><w:t>{text}</w:t></w:r></w:p>"
    )


def build_body() -> str:
    parts = []
    table_num = 0
    for page in range(PAGES):
        if page > 0:
            parts.append(make_page_break())
        parts.append(make_heading(f"Page {page + 1}"))
        for _ in range(TABLES_PER_PAGE):
            parts.append(make_table(table_num))
            table_num += 1
    return "".join(parts)


CONTENT_TYPES = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELS = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>"""


def main() -> None:
    body = build_body()
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", document)

    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"Created {OUTPUT} ({size_kb:.0f} KB, {PAGES} pages, {PAGES * TABLES_PER_PAGE} tables)")


if __name__ == "__main__":
    main()
