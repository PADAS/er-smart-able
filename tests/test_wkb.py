from __future__ import annotations

import struct

import pytest

from export.wkb import parse_track_wkb
from tests.conftest import T0, TRACK_WKB, wkb_line_z


def test_linestring_z():
    parts = parse_track_wkb(TRACK_WKB)
    assert parts == [[(123.72, 13.06, T0), (123.73, 13.07, T0 + 3600000)]]


def test_multilinestring_z():
    a = wkb_line_z([(1.0, 2.0, 10.0)])
    b = wkb_line_z([(3.0, 4.0, 20.0), (5.0, 6.0, 30.0)])
    multi = "00" + "80000005" + struct.pack(">I", 2).hex() + a + b
    assert parse_track_wkb(multi) == [[(1.0, 2.0, 10.0)], [(3.0, 4.0, 20.0), (5.0, 6.0, 30.0)]]


def test_plain_2d_linestring():
    pts = [(1.0, 2.0), (3.0, 4.0)]
    wkb = "00" + "00000002" + struct.pack(">I", 2).hex() + b"".join(struct.pack(">dd", *p) for p in pts).hex()
    assert parse_track_wkb(wkb) == [[(1.0, 2.0, None), (3.0, 4.0, None)]]


def test_little_endian_and_bad_type():
    pts = [(1.0, 2.0, 5.0)]
    wkb = "01" + struct.pack("<I", 0x80000002).hex() + struct.pack("<I", 1).hex() + struct.pack("<ddd", *pts[0]).hex()
    assert parse_track_wkb(wkb) == [[(1.0, 2.0, 5.0)]]
    with pytest.raises(ValueError):
        parse_track_wkb("00" + "00000001" + "00")


def test_null_geometry_is_a_value_error():
    with pytest.raises(ValueError):
        parse_track_wkb(None)
    with pytest.raises(ValueError):
        parse_track_wkb("")
