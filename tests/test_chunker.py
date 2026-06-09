# tests/test_chunker.py
from itkb.ingestion.chunker import chunk_text

SHORT_TEXT = "This is a short note about restarting nginx."

LONG_TEXT = "\n\n".join([f"Paragraph {i}: " + "word " * 80 for i in range(10)])

MARKDOWN_TEXT = """# Section One

First paragraph about DNS configuration.

# Section Two

Second paragraph about firewall rules and how to configure them properly.
"""

PDF_TEXT = "[Page 1]\nContent on page one.\n\n[Page 2]\nContent on page two."

def test_short_text_produces_single_chunk():
    chunks = chunk_text(SHORT_TEXT, "/notes/test.md")
    assert len(chunks) == 1
    assert chunks[0].content == SHORT_TEXT

def test_long_text_produces_multiple_chunks():
    chunks = chunk_text(LONG_TEXT, "/notes/long.md")
    assert len(chunks) > 1

def test_chunks_have_sequential_indices():
    chunks = chunk_text(LONG_TEXT, "/notes/long.md")
    for i, c in enumerate(chunks):
        assert c.chunk_index == i

def test_markdown_headings_captured_in_metadata():
    chunks = chunk_text(MARKDOWN_TEXT, "/notes/config.md")
    headings = [c.section_heading for c in chunks if c.section_heading]
    assert "Section One" in headings
    assert "Section Two" in headings

def test_pdf_page_numbers_captured():
    chunks = chunk_text(PDF_TEXT, "/docs/manual.pdf")
    pages = [c.page_number for c in chunks if c.page_number is not None]
    assert 1 in pages
    assert 2 in pages

def test_overlap_content_present_in_consecutive_chunks():
    chunks = chunk_text(LONG_TEXT, "/notes/overlap.md")
    if len(chunks) >= 2:
        last_words_of_first = chunks[0].content.split()[-10:]
        start_of_second = chunks[1].content
        assert any(w in start_of_second for w in last_words_of_first)
