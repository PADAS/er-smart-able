"""Parse SMART track geometries: (extended) WKB in hex, LineString or
MultiLineString, optionally with a Z coordinate (SMART puts the point's
epoch-millisecond timestamp there).
"""
from __future__ import annotations

import struct
from typing import List, Optional, Tuple

Point = Tuple[float, float, Optional[float]]

LINESTRING, MULTILINESTRING = 2, 5
Z_FLAG, M_FLAG, SRID_FLAG = 0x80000000, 0x40000000, 0x20000000


class _Reader:
    def __init__(self, data: bytes):
        self.b = data
        self.pos = 0

    def take(self, fmt: str):
        v = struct.unpack_from(fmt, self.b, self.pos)
        self.pos += struct.calcsize(fmt)
        return v


def _geometry(r: _Reader) -> Tuple[int, bool, str]:
    (order,) = r.take("B")
    if order not in (0, 1):
        raise ValueError(f"bad WKB byte order {order}")
    bo = ">" if order == 0 else "<"
    (t,) = r.take(bo + "I")
    if t & M_FLAG:
        raise ValueError("WKB with an M coordinate is not supported")
    has_z = bool(t & Z_FLAG)
    if t & SRID_FLAG:            # EWKB: a 4-byte SRID follows the type word
        r.take(bo + "I")
    base = t & 0xFFFF
    if base >= 3000:
        raise ValueError("ISO WKB with an M coordinate is not supported")
    if base >= 1000:            # ISO WKB encodes Z as type + 1000
        base -= 1000
        has_z = True
    return base, has_z, bo


def _line(r: _Reader, has_z: bool, bo: str) -> List[Point]:
    (n,) = r.take(bo + "I")
    if has_z:
        vals = r.take(bo + f"{3 * n}d")
        return [(vals[i], vals[i + 1], vals[i + 2]) for i in range(0, 3 * n, 3)]
    vals = r.take(bo + f"{2 * n}d")
    return [(vals[i], vals[i + 1], None) for i in range(0, 2 * n, 2)]


def parse_track_wkb(hexstr: str) -> List[List[Point]]:
    if not hexstr:
        raise ValueError("no geometry")
    r = _Reader(bytes.fromhex(hexstr))
    base, has_z, bo = _geometry(r)
    if base == LINESTRING:
        return [_line(r, has_z, bo)]
    if base == MULTILINESTRING:
        (n,) = r.take(bo + "I")
        parts = []
        for _ in range(n):
            pb, pz, pbo = _geometry(r)
            if pb != LINESTRING:
                raise ValueError(f"MultiLineString part has type {pb}")
            parts.append(_line(r, pz, pbo))
        return parts
    raise ValueError(f"unsupported WKB geometry type {base}")
