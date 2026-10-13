"""A small XML text writer that reproduces SMART's JAXB output layout:
4-space indent, attributes in the order given, self-closed empty elements,
and `<x></x>` for empty text elements.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Iterable, Tuple

DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def xml_escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("\r", "&#13;"))


def java_double(x: float) -> str:
    """Java's Double.toString: plain decimal for 1e-3 <= |x| < 1e7, else d.dddE±n."""
    if x != x:
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0.0"
    d = Decimal(repr(float(x)))          # shortest round-tripping digits
    sign, digits, exp = d.as_tuple()
    digits = list(digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exp += 1
    e10 = exp + len(digits) - 1          # scientific exponent
    neg = "-" if sign else ""
    if 1e-3 <= abs(x) < 1e7:
        ds = "".join(str(c) for c in digits)       # shortest digits, trailing zeros stripped
        if exp >= 0:
            return f"{neg}{ds}{'0' * exp}.0"
        k = len(ds) + exp                         # digits before the decimal point
        return f"{neg}{ds[:k]}.{ds[k:]}" if k > 0 else f"{neg}0.{'0' * -k}{ds}"
    mant = str(digits[0]) + "." + ("".join(str(c) for c in digits[1:]) or "0")
    return f"{neg}{mant}E{e10}"


class Xml:
    def __init__(self):
        self.lines = []
        self.depth = 0

    def _attrs(self, attrs: Iterable[Tuple[str, str]]) -> str:
        return "".join(f' {k}="{xml_escape(v)}"' for k, v in attrs)

    def open(self, tag: str, attrs: Iterable[Tuple[str, str]] = ()) -> None:
        self.lines.append(f"{'    ' * self.depth}<{tag}{self._attrs(attrs)}>")
        self.depth += 1

    def close(self, tag: str) -> None:
        self.depth -= 1
        self.lines.append(f"{'    ' * self.depth}</{tag}>")

    def empty(self, tag: str, attrs: Iterable[Tuple[str, str]] = ()) -> None:
        self.lines.append(f"{'    ' * self.depth}<{tag}{self._attrs(attrs)}/>")

    def text(self, tag: str, text: str, attrs: Iterable[Tuple[str, str]] = ()) -> None:
        self.lines.append(f"{'    ' * self.depth}<{tag}{self._attrs(attrs)}>{xml_escape(text)}</{tag}>")

    def render(self) -> str:
        return DECL + "\n".join(self.lines) + "\n"
