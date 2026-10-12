"""Compare our DataModel/ConfigurableModel XML with SMART's own export.

Strict mode reports element order, attribute order and values, and text.
Loose mode ignores attribute order and whitespace so semantic differences
stand out while byte fidelity is still being chased.

    uv run python -m export.verify_xml reference.xml ours.xml [--loose] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from typing import List


def _tag(el: ET.Element) -> str:
    return el.tag.split("}", 1)[-1]


def _walk(ref: ET.Element, got: ET.Element, path: str, loose: bool, out: List[str], limit: int) -> None:
    if len(out) >= limit:
        return
    if _tag(ref) != _tag(got):
        out.append(f"{path}: element {_tag(ref)} != {_tag(got)}")
        return
    rk, gk = list(ref.attrib), list(got.attrib)
    if not loose and rk != gk:
        out.append(f"{path}: attribute order {rk} != {gk}")
    for k in rk:
        if k not in got.attrib:
            out.append(f"{path}: attribute {k} missing")
        elif ref.attrib[k] != got.attrib[k]:
            out.append(f"{path}: attribute {k} {ref.attrib[k]!r} != {got.attrib[k]!r}")
    for k in gk:
        if k not in ref.attrib:
            out.append(f"{path}: attribute {k} unexpected")
    rt, gt = (ref.text or "").strip(), (got.text or "").strip()
    if rt != gt:
        out.append(f"{path}: text {rt!r} != {gt!r}")
    rc, gc = list(ref), list(got)
    if len(rc) != len(gc):
        out.append(f"{path}: child count {len(rc)} != {len(gc)}")
    counts: dict = {}
    for r, g in zip(rc, gc):
        n = counts[_tag(r)] = counts.get(_tag(r), 0) + 1
        _walk(r, g, f"{path}/{_tag(r)}[{n}]", loose, out, limit)
    del out[limit:]


def compare(reference, candidate, loose: bool = False, limit: int = 20) -> List[str]:
    ref = ET.fromstring(reference.encode("utf-8") if isinstance(reference, str) else reference)
    got = ET.fromstring(candidate.encode("utf-8") if isinstance(candidate, str) else candidate)
    out: List[str] = []
    _walk(ref, got, "/" + _tag(ref), loose, out, limit)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("reference")
    p.add_argument("candidate")
    p.add_argument("--loose", action="store_true")
    p.add_argument("--limit", type=int, default=20)
    a = p.parse_args(argv)
    try:
        ref = open(a.reference, encoding="utf-8").read()
        got = open(a.candidate, encoding="utf-8").read()
        diffs = compare(ref, got, loose=a.loose, limit=a.limit)
    except (OSError, ET.ParseError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not diffs and not a.loose and ref != got:
        diffs = ["documents are structurally equal but differ in bytes (whitespace, declaration or escaping)"]
    for d in diffs:
        print(d)
    print("identical" if not diffs else f"{len(diffs)} difference(s) shown")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
