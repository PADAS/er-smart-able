from __future__ import annotations

from export.xmlwriter import Xml, java_double, xml_escape


def test_java_double():
    assert java_double(0.0) == "0.0"
    assert java_double(3.0) == "3.0"
    assert java_double(0.5) == "0.5"
    assert java_double(120.0) == "120.0"
    assert java_double(10000000.0) == "1.0E7"
    assert java_double(12345678.9) == "1.23456789E7"
    assert java_double(0.001) == "0.001"
    assert java_double(0.0001) == "1.0E-4"
    assert java_double(-2.5) == "-2.5"


def test_escape():
    assert xml_escape('a & b < c > "d"') == "a &amp; b &lt; c &gt; &quot;d&quot;"
    assert xml_escape("Éléphant") == "Éléphant"


def test_writer_layout():
    x = Xml()
    x.open("DataModel", [("xmlns", "urn:x")])
    x.open("attributes", [])
    x.empty("names", [("language_code", "en"), ("value", 'Q & "A"')])
    x.text("MinValue", "0.0")
    x.text("qa_regex", "")
    x.close("attributes")
    x.close("DataModel")
    assert x.render() == (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<DataModel xmlns="urn:x">\n'
        '    <attributes>\n'
        '        <names language_code="en" value="Q &amp; &quot;A&quot;"/>\n'
        '        <MinValue>0.0</MinValue>\n'
        '        <qa_regex></qa_regex>\n'
        '    </attributes>\n'
        '</DataModel>\n'
    )
