#!/usr/bin/env python3
"""Render docs/smart-data-quirks.md to work/site/quirks.html with stable
heading ids, so the browser, the runbook and export warnings can deep-link
to sections. Run by `./smart-able browse`.

The page wears the browser's theme: its design tokens (light and dark) and
acorn mark are read from browse/index.html at build time, so the two pages
cannot drift apart.

Usage: build_quirks.py <markdown file> <output html>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import markdown

APP = Path(__file__).with_name("index.html")

CSS = """
html { scroll-padding-top: 16px; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 14.5px/1.6 var(--sans); }
header { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 18px;
  padding: 10px 16px; background: var(--brand); color: var(--brand-ink); }
.brand { display: flex; align-items: center; gap: 9px; }
.brand svg { width: 22px; height: 22px; display: block; flex: none; }
.brand .acorn { color: #0fcb8c; }
header h1 { font-family: var(--head); font-size: 17px; font-weight: 700; margin: 0; letter-spacing: -0.1px; }
header h1 span { opacity: 0.6; font-weight: 400; font-family: var(--sans); }
a.back { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; color: var(--brand-ink);
  text-decoration: none; font: 500 13.5px var(--sans); padding: 7px 11px; border-radius: 7px; opacity: 0.85; }
a.back:hover { background: rgba(255,255,255,0.12); opacity: 1; }
.mi { font-family: "Material Symbols Outlined"; font-weight: normal; font-style: normal; font-size: 18px;
  line-height: 1; display: inline-block; vertical-align: middle; -webkit-font-feature-settings: "liga";
  font-feature-settings: "liga"; -webkit-font-smoothing: antialiased; user-select: none; }
.layout { max-width: 1200px; margin: 0 auto; padding: 18px 16px 60px;
  display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 24px; align-items: start; }
nav.toc { position: sticky; top: 16px; max-height: calc(100vh - 32px); overflow: auto;
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; font-size: 13px; }
nav.toc::before { content: "On this page"; display: block; color: var(--ink-3); font-weight: 600; font-size: 11.5px;
  text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
nav.toc ul { list-style: none; margin: 0; padding: 0; }
nav.toc ul ul { padding-left: 12px; }
nav.toc li { margin: 3px 0; }
nav.toc a { color: var(--ink-2); text-decoration: none; }
nav.toc a:hover { color: var(--accent); text-decoration: underline; }
article { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 8px 28px 28px; }
article h1 { font-family: var(--head); font-size: 24px; margin: 18px 0 8px; }
article h2 { font-family: var(--head); font-size: 18px; margin: 30px 0 8px; padding-top: 18px;
  border-top: 1px solid var(--line); }
article h3 { font-family: var(--head); font-size: 15px; margin: 20px 0 6px; }
article a { color: var(--accent); }
code { font-family: var(--mono); font-size: 12.5px; background: var(--chip); padding: 1px 5px; border-radius: 5px; }
pre { background: var(--chip); padding: 10px 12px; border-radius: 8px; overflow: auto; }
pre code { padding: 0; background: none; }
table { border-collapse: collapse; width: 100%; font-size: 13px; margin: 10px 0; }
th { text-align: left; color: var(--ink-3); font-weight: 600; font-size: 11.5px; text-transform: uppercase;
  letter-spacing: 0.05em; padding: 6px 10px 6px 0; border-bottom: 1px solid var(--line); }
td { padding: 7px 10px 7px 0; border-bottom: 1px solid var(--line); vertical-align: top; }
blockquote { margin: 12px 0; padding: 4px 14px; border-left: 3px solid var(--accent); color: var(--ink-2); }
:target { scroll-margin-top: 16px; }
h2:target, h3:target { color: var(--accent); box-shadow: inset 3px 0 var(--accent); padding-left: 10px; }
@media (max-width: 820px) {
  .layout { grid-template-columns: 1fr; }
  nav.toc { position: static; max-height: none; }
  article { padding: 4px 16px 20px; }
}
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SMART data quirks · smart-able</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Roboto+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..24,400,0..1,0&display=block">
<style>
{tokens}
{css}
</style></head>
<body>
<header>
  <div class="brand">{acorn}<h1>smart-able <span>SMART data quirks</span></h1></div>
  <a class="back" href="./"><span class="mi" aria-hidden="true">arrow_back</span>Back to the browser</a>
</header>
<div class="layout">
{toc}
<article>
{body}
</article>
</div>
</body></html>
"""


def app_theme(app_html: str) -> tuple[str, str]:
    """The browser's design-token blocks (light, dark media query, explicit
    theme overrides) and its acorn mark."""
    tokens = re.search(r"(:root \{.*?)\nhtml, body \{", app_html, re.S)
    acorn = re.search(r'<svg class="acorn".*?</svg>', app_html, re.S)
    if not tokens or not acorn:
        raise SystemExit(f"{APP}: design tokens or acorn mark not found; update app_theme()")
    return tokens.group(1), acorn.group(0)


def render(md_text: str) -> str:
    m = markdown.Markdown(extensions=["toc", "tables", "fenced_code"], extension_configs={"toc": {"toc_depth": "2-3"}})
    body = m.convert(md_text)
    tokens, acorn = app_theme(APP.read_text(encoding="utf-8"))
    toc = m.toc.replace('<div class="toc">', '<nav class="toc" aria-label="On this page">', 1)
    toc = toc[: toc.rfind("</div>")] + "</nav>" if toc.rstrip().endswith("</div>") else toc
    return PAGE.format(tokens=tokens, css=CSS, acorn=acorn, toc=toc, body=body)


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.write_text(render(src.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"  {dst}")
