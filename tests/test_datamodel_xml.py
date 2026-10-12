from __future__ import annotations

import difflib

from export.datamodel_xml import build_datamodel_xml, datamodel_namespace
from export.smartdb import SmartDb
from tests.conftest import CA_A, CA_B, ICONFILE_1, ICONFILE_2

GOLDEN = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<DataModel xmlns="http://www.smartconservationsoftware.org/xml/1.1/datamodel">
    <languages>
        <languages code="en"/>
        <languages code="fr"/>
    </languages>
    <attributes>
        <attribute key="armed" isrequired="false" type="BOOLEAN">
            <names language_code="en" value="Armed"/>
        </attribute>
        <attribute key="count" isrequired="false" type="NUMERIC">
            <aggregations aggregation="avg"/>
            <aggregations aggregation="sum"/>
            <qa_minmax>
                <MinValue>0.0</MinValue>
                <MaxValue>1.0E7</MaxValue>
            </qa_minmax>
            <names language_code="en" value="Count"/>
        </attribute>
        <attribute key="note" isrequired="false" type="TEXT">
            <qa_regex></qa_regex>
            <names language_code="en" value="Note"/>
        </attribute>
        <attribute key="seen" isrequired="false" type="DATE">
            <names language_code="en" value="Seen on"/>
        </attribute>
        <attribute key="species" isrequired="true" type="LIST" iconkey="species">
            <names language_code="en" value="Species"/>
            <names language_code="fr" value="Espèce"/>
            <values key="elephant" isactive="true">
                <names language_code="en" value="Elephant"/>
                <names language_code="fr" value="Éléphant"/>
            </values>
            <values key="lion" isactive="true">
                <names language_code="en" value="Lion"/>
            </values>
        </attribute>
        <attribute key="threattype" isrequired="true" type="TREE">
            <names language_code="en" value="Threat type"/>
            <tree key="snare" isactive="true">
                <names language_code="en" value="Snare"/>
                <children key="wire" isactive="true">
                    <names language_code="en" value="Wire snare"/>
                </children>
            </tree>
            <tree key="fire" isactive="true">
                <names language_code="en" value="Fire"/>
            </tree>
        </attribute>
        <attribute key="threat" isrequired="false" type="MLIST">
            <names language_code="en" value="Threats"/>
            <values key="snare" isactive="true">
                <names language_code="en" value="Snare"/>
            </values>
            <values key="fire" isactive="false">
                <names language_code="en" value="Fire"/>
            </values>
        </attribute>
    </attributes>
    <categories>
        <category key="threats" ismultiple="false" isactive="true">
            <names language_code="en" value="Threats &amp; &quot;risks&quot; &lt;all&gt;"/>
            <attributes isactive="true" attributekey="threattype"/>
            <attributes isactive="true" attributekey="threat"/>
            <attributes isactive="true" attributekey="armed"/>
            <attributes isactive="true" attributekey="seen"/>
        </category>
        <category key="animals" ismultiple="true" isactive="true" iconkey="species">
            <names language_code="en" value="Animals"/>
            <names language_code="fr" value="Animaux"/>
            <category key="liveanimals" ismultiple="true" isactive="true">
                <names language_code="en" value="Live animals"/>
                <attributes isactive="true" attributekey="species"/>
                <attributes isactive="true" attributekey="count"/>
                <attributes isactive="false" attributekey="note"/>
            </category>
        </category>
    </categories>
    <icons key="species" issystem="true">
        <icons iconset="line" file="{ICONFILE_1}.svg"/>
        <icons iconset="color" file="{ICONFILE_2}.svg"/>
        <names language_code="en" value="Species icon"/>
    </icons>
</DataModel>
'''


def assert_same(got: str, want: str) -> None:
    if got != want:
        raise AssertionError("\n" + "".join(difflib.unified_diff(
            want.splitlines(True), got.splitlines(True), "golden", "got")))


def test_namespace_by_version():
    assert datamodel_namespace("7.5.4") == ("http://www.smartconservationsoftware.org/xml/1.1/datamodel", [])
    ns, warns = datamodel_namespace("8.1.0")
    assert ns.endswith("/1.1/datamodel") and "8.1.0" in warns[0]


def test_golden_datamodel(smart_parquet):
    xml, warnings = build_datamodel_xml(SmartDb(smart_parquet), CA_A)
    assert_same(xml, GOLDEN)
    assert warnings == []


def test_xml_escaping(smart_parquet):
    xml, _ = build_datamodel_xml(SmartDb(smart_parquet), CA_A)
    assert 'value="Threats &amp; &quot;risks&quot; &lt;all&gt;"' in xml
    import xml.etree.ElementTree as ET
    ET.fromstring(xml.encode("utf-8"))  # well-formed


def test_icons_only_referenced_and_unique(smart_parquet):
    xml, _ = build_datamodel_xml(SmartDb(smart_parquet), CA_A)
    assert xml.count('<icons key="species"') == 1
    xml_b, warnings = build_datamodel_xml(SmartDb(smart_parquet), CA_B)
    assert "<icons key=" not in xml_b
    assert "<attributes>\n    </attributes>" in xml_b


from export.datamodel_xml import build_configurable_model_xml, list_configurable_models  # noqa: E402
from export.smartdb import hyphenate  # noqa: E402
from tests.conftest import (CM, NODE_GROUP, NODE_LIVE, CAT_LIVE, ATT_SPECIES, CMATT_SPECIES,  # noqa: E402
                            CMCONF_SPECIES, CMLIST_ELE, LIST_ELE)

GOLDEN_CM = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ConfigurableModel xmlns="http://www.smartconservationsoftware.org/xml/1.0/dataentry" displayMode="TEXT_IMAGE" instantGps="true" photoFirst="false" useEarthRanger="false" iconSet="color">
    <languages>
        <language code="en" is_default="true"/>
        <language code="fr" is_default="false"/>
    </languages>
    <name language_code="en" value="Alpha mobile model" source="CM"/>
    <nodes>
        <node id="{hyphenate(NODE_GROUP)}">
            <name language_code="en" value="Sightings" source="CM"/>
            <node categoryKey="liveanimals" categoryHkey="animals.liveanimals." dmUuid="{CAT_LIVE}" photoAllowed="true" photoRequired="false" displayMode="TEXT" id="{hyphenate(NODE_LIVE)}" collectMultipleObs="false" useSingleGpsPoint="false">
                <name language_code="en" value="Live animals" source="DM"/>
                <attribute attributeKey="species" dmUuid="{ATT_SPECIES}" id="{hyphenate(CMATT_SPECIES)}" configId="{hyphenate(CMCONF_SPECIES)}" type="LIST" required="true" isCustomImage="false">
                    <name language_code="en" value="Species" source="DM"/>
                    <name language_code="fr" value="Espèce" source="DM"/>
                    <option id="IS_VISIBLE" doubleValue="1.0"/>
                    <option id="ENTER_ONCE" stringValue="NONE"/>
                </attribute>
            </node>
        </node>
    </nodes>
    <attributeConfig id="{hyphenate(CMCONF_SPECIES)}" attributeKey="species" displayMode="TEXT" isDefault="true" attributeUuid="{ATT_SPECIES}">
        <name language_code="en" value="Species (curated)" source="CM"/>
        <listItem keyRef="elephant" dmUuid="{LIST_ELE}" isActive="true" id="{hyphenate(CMLIST_ELE)}" isCustomImage="false">
            <name language_code="en" value="Elephant" source="DM"/>
            <name language_code="fr" value="Éléphant" source="DM"/>
        </listItem>
    </attributeConfig>
</ConfigurableModel>
'''


def test_list_configurable_models(smart_parquet):
    assert list_configurable_models(SmartDb(smart_parquet), CA_A) == [{"uuid": CM, "label": "Alpha mobile model"}]
    assert list_configurable_models(SmartDb(smart_parquet), CA_B) == []


def test_golden_configurable_model(smart_parquet):
    xml, warnings = build_configurable_model_xml(SmartDb(smart_parquet), CM)
    assert_same(xml, GOLDEN_CM)
    assert warnings == ["useEarthRanger has no known source column; written as false"]
