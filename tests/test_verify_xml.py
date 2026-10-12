from __future__ import annotations

from export.verify_xml import compare

A = '<?xml version="1.0"?>\n<r xmlns="u"><a k="1" j="2"><n v="x"/></a><b>t</b></r>'


def test_equal():
    assert compare(A, A) == []


def test_attribute_order_strict_vs_loose():
    b = A.replace('k="1" j="2"', 'j="2" k="1"')
    assert compare(A, b) == ["/r/a[1]: attribute order ['k', 'j'] != ['j', 'k']"]
    assert compare(A, b, loose=True) == []


def test_value_text_and_child_count():
    b = A.replace('v="x"', 'v="y"').replace("<b>t</b>", "<b>u</b><c/>")
    diffs = compare(A, b)
    assert "/r/a[1]/n[1]: attribute v 'x' != 'y'" in diffs
    assert "/r/b[1]: text 't' != 'u'" in diffs
    assert "/r: child count 2 != 3" in diffs


def test_limit():
    b = A.replace('v="x"', 'v="y"').replace("<b>t</b>", "<b>u</b>")
    assert len(compare(A, b, limit=1)) == 1
