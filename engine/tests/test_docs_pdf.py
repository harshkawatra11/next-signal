import pymupdf

from next_signal.docs.pdf import extract_pages, extract_table, page_count


def make_pdf(pages_text: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_page_count_matches_number_of_pages():
    pdf = make_pdf(["page one", "page two", "page three"])
    assert page_count(pdf) == 3


def test_extract_pages_returns_text_in_order():
    pdf = make_pdf(["North America revenue was USD 162 million.", "Second page text."])
    pages = extract_pages(pdf)
    assert len(pages) == 2
    assert "North America revenue was USD 162 million." in pages[0]
    assert "Second page text." in pages[1]


def test_extract_pages_normalises_excess_whitespace():
    pdf = make_pdf(["Line with  double   spaces"])
    pages = extract_pages(pdf)
    assert "  " not in pages[0]


def test_extract_table_returns_none_for_out_of_range_page():
    pdf = make_pdf(["only one page"])
    assert extract_table(pdf, 5) == None
    assert extract_table(pdf, 0) == None


def test_extract_table_returns_none_when_no_table_present():
    pdf = make_pdf(["plain prose, no table structure here"])
    assert extract_table(pdf, 1) is None
