"""Strict fidelity check against SMART Desktop's own export.

Set SMART_ABLE_REFERENCE_DIR to a directory holding reference/datamodel.xml
and work/ (a smart-able work dir for the same CA) to enable. Icon file names
are ignored: they are the exporting install's iconfile row UUIDs, so a
reference made on another install names the same icons differently.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from export.verify_xml import compare

REF = os.environ.get("SMART_ABLE_REFERENCE_DIR")
pytestmark = pytest.mark.skipif(not REF, reason="SMART_ABLE_REFERENCE_DIR not set")


def test_datamodel_matches_reference():
    base = Path(REF)
    ours = next((base / "work" / "export").glob("*/datamodel.xml"))
    diffs = compare((base / "reference" / "datamodel.xml").read_text(), ours.read_text(), ignore_icon_files=True)
    assert diffs == []
