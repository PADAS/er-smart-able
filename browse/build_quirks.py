#!/usr/bin/env python3
"""Render docs/smart-data-quirks.md to work/site/quirks.html with stable
heading ids, so the browser, the runbook and export warnings can deep-link
to sections. Run by `./smart-able browse`.

Usage: build_quirks.py <markdown file> <output html>
"""
from __future__ import annotations

import sys
from pathlib import Path

import markdown

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SMART data quirks · smart-able</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font: 15px/1.55 system-ui, sans-serif; margin: 0; color: #1d2b36; background: #fff; }}
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 24px 20px 60px; }}
  nav {{ background: #f3f6f8; border: 1px solid #dde3e8; border-radius: 10px; padding: 10px 16px; margin-bottom: 24px; }}
  nav ul {{ margin: 0; padding-left: 18px; }} h1 {{ margin-top: 0; }}
  h2 {{ margin-top: 32px; border-top: 1px solid #dde3e8; padding-top: 16px; }}
  code {{ background: #f3f6f8; padding: 1px 4px; border-radius: 4px; }}
  table {{ border-collapse: collapse; }} td, th {{ border: 1px solid #dde3e8; padding: 4px 8px; }}
  a.back {{ font-size: 13px; }}
  :target {{ background: #fff6d6; }}
</style></head>
<body><div class="wrap"><a class="back" href="./">&larr; back to the browser</a>
{toc}
{body}
</div></body></html>
"""


def render(md_text: str) -> str:
    m = markdown.Markdown(extensions=["toc", "tables", "fenced_code"], extension_configs={"toc": {"toc_depth": "2-3"}})
    body = m.convert(md_text)
    return PAGE.format(toc="<nav>" + m.toc + "</nav>", body=body)


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.write_text(render(src.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"  {dst}")
