"""HTML extract: main content only, one line per table row (phase 4 spec 5.4, AC-4)."""

from __future__ import annotations

from pathlib import Path

from pipeline.extract import extract, html_to_text

PAGE = """<html><head><title>t</title><script>var x = "JS_LEAK";</script><style>.a{}</style></head>
<body><header><nav><a href="/">Menu Item</a></nav></header>
<div id="wrapper"><div class="main-content"><div class="content">
<div class="page-title"><h2 class="captions">Fee Structure</h2>
<ol class="breadcrumb"><li><a href="/">Home</a></li><li>Admissions</li></ol></div>
<h2 class="underline">Tuition Fee (w.e.f. Fall 2026 semester) </h2>
<p>Fee per credit hour:</p>
<table><tr><th>Program</th><th>Fee</th></tr>
<tr><td>BBA / BS</td><td>Rs.&nbsp;12,000</td></tr>
<tr><td></td><td></td></tr>
<tr><td>Multi<br>line</td><td>  x   y </td></tr></table>
<h2>Refund</h2>
<table><caption>Refund timeline</caption><tr><td>Upto 20th day</td><td>60% Fee Refund</td></tr></table>
<p>Note: counted <b>including</b> holidays.</p>
</div></div></div>
<footer><p>FOOTER_LEAK Copyright</p></footer></body></html>"""


def test_rows_one_line_and_context_kept() -> None:
    t = html_to_text(PAGE)
    lines = t.split("\n")
    assert "Program | Fee" in lines
    assert "BBA / BS | Rs.\xa012,000" in lines or "BBA / BS | Rs. 12,000" in lines
    assert "Multi line | x y" in lines
    assert "Upto 20th day | 60% Fee Refund" in lines
    # heading stays directly above its table; the empty row is dropped
    i = lines.index("Program | Fee")
    assert lines[i - 2] == "Fee per credit hour:" or lines[i - 1] == "Fee per credit hour:"
    assert "Tuition Fee (w.e.f. Fall 2026 semester)" in lines
    assert lines.index("Refund timeline") + 1 == lines.index("Upto 20th day | 60% Fee Refund")
    assert "Note: counted including holidays." in lines
    assert not any(ln.strip(" |") == "" and ln for ln in lines)


def test_navigation_scripts_footer_dropped() -> None:
    t = html_to_text(PAGE)
    for leak in ("JS_LEAK", "Menu Item", "Home", "Admissions", "FOOTER_LEAK", "Copyright", "<"):
        assert leak not in t, leak
    assert t.startswith("Fee Structure")


def test_no_marker_falls_back_to_whole_body() -> None:
    t = html_to_text("<body><h1>Title</h1><p>text</p><nav>skip</nav></body>")
    assert t == "Title\ntext"


def test_unclosed_tags_do_not_crash() -> None:
    t = html_to_text('<div class="main-content"><p>one<p>two<table><tr><td>a<td>b</table>')
    assert "one" in t and "two" in t and "a | b" in t


def test_extract_html_file(tmp_path: Path) -> None:
    f = tmp_path / "fee-structure-page.html"
    f.write_text(PAGE, encoding="utf-8")
    doc = extract(str(f), "2026-27", False)
    assert doc.source == "fee-structure-page.html" and len(doc.pages) == 1
    assert doc.pages[0].page == 1 and doc.pages[0].ocr is False
    assert "Program | Fee" in doc.pages[0].text
