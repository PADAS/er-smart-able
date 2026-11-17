"""The getting-started site (GitHub Pages): scripts/build_pages.py renders web/guide and the in-app
help to static pages. The build's structure and links, then the guide's content, then the workflow."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture
def site(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    spec = importlib.util.spec_from_file_location("build_pages", ROOT / "scripts" / "build_pages.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "build_pages", mod)   # the dataclass looks its module up while it is defined
    spec.loader.exec_module(mod)
    return mod


def tree(tmp_path, monkeypatch, mod, guide: dict, help: dict, langs: list = None, words: dict = None):
    """A stand-in repository under tmp_path: web/guide and web/help with the given files, and the
    two repository files the link tests point at. A file name may sit in a language's folder
    ("fr/01-a.md"). langs and words stand in for the registry and the shell's words; without them
    the real ones are used."""
    root = tmp_path / "repo"
    for folder, files in (("guide", guide), ("help", help)):
        d = root / "web" / folder
        d.mkdir(parents=True)
        for name, text in files.items():
            (d / name).parent.mkdir(exist_ok=True)
            (d / name).write_text(text, encoding="utf-8")
    if langs is not None:
        (root / "locales").mkdir()
        (root / "locales" / "languages.json").write_text(json.dumps(langs), encoding="utf-8")
        monkeypatch.setattr(mod, "LOCALES_DIR", root / "locales")
    if words is not None:
        (root / "words").mkdir()
        for code, w in words.items():
            (root / "words" / f"{code}.json").write_text(json.dumps(w), encoding="utf-8")
        monkeypatch.setattr(mod, "WORDS_DIR", root / "words")
    (root / "docs").mkdir()
    (root / "README.md").write_text("# readme")
    (root / "docs" / "smart-data-quirks.md").write_text("# quirks")
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "GUIDE_DIR", root / "web" / "guide")
    monkeypatch.setattr(mod, "HELP_DIR", root / "web" / "help")


def test_the_real_site_builds_a_page_per_source_with_index_first(site, tmp_path):
    out = tmp_path / "_site"
    written = site.build(out)
    names = [p.name for p in written if p.parent == out]   # the English pages, at the top; each language adds a folder of the same
    assert names[0] == "index.html" and len(written) == len(names) * len(site.languages())
    assert {"overview.html", "sites.html", "loading.html", "statuses.html", "stops.html"} <= set(names)
    assert len(names) == len(list(site.GUIDE_DIR.glob("*.md"))) + len(list(site.HELP_DIR.glob("*.md")))
    for f in ("static/er-tokens.css", "static/site.css", "static/fonts/roboto.css", "static/fonts/roboto.woff2", "static/img/er-lockup-white-h-short.svg"):
        assert (out / f).is_file(), f


def test_each_page_has_its_title_nav_groups_current_mark_and_neighbours(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# Alpha\n\nx", "02-b.md": "# Beta\n\ny"}, {"01-c.md": "# Gamma\n\nz"})
    out = tmp_path / "o"; site.build(out)
    b = (out / "b.html").read_text()
    assert "<title>Beta · SMART migration</title>" in b and "<h1>Beta</h1>" in b
    assert "Get started" in b and "Reference" in b
    assert re.search(r'<a[^>]*href="b\.html"[^>]*aria-current="page"', b)
    assert not re.search(r'<a[^>]*href="index\.html"[^>]*aria-current', b)
    assert re.search(r'class="prev"[^>]*href="index\.html"|href="index\.html"[^>]*class="prev"', b)
    assert re.search(r'class="next"[^>]*href="c\.html"|href="c\.html"[^>]*class="next"', b)
    assert 'class="prev"' not in (out / "index.html").read_text() and 'class="next"' not in (out / "c.html").read_text()


def test_links_between_sources_become_pages_and_keep_their_anchor(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n[s](../help/02-sites.md#which-user) [b](02-b.md) [h](#here)", "02-b.md": "# B\n\n[a](01-a.md)"},
         {"02-sites.md": "# Sites\n\nx"})
    out = tmp_path / "o"; site.build(out)
    a = (out / "index.html").read_text()
    assert 'href="sites.html#which-user"' in a and 'href="b.html"' in a and 'href="#here"' in a
    assert 'href="index.html"' in (out / "b.html").read_text()


def test_a_link_to_another_repository_file_goes_to_github_and_outside_links_open_a_new_tab(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n[r](../../README.md) [q](../../docs/smart-data-quirks.md#patrol-times) [e](https://earthranger.com)"}, {})
    out = tmp_path / "o"; site.build(out)
    a = (out / "index.html").read_text()
    assert 'href="https://github.com/PADAS/er-smart-able/blob/main/README.md"' in a
    assert 'href="https://github.com/PADAS/er-smart-able/blob/main/docs/smart-data-quirks.md#patrol-times"' in a
    assert re.search(r'<a target="_blank" rel="noopener"[^>]*href="https://earthranger\.com"', a)


def test_a_broken_relative_link_fails_the_build_naming_file_and_link(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n[x](nope.md)"}, {})
    with pytest.raises(site.BuildError, match=r"01-a\.md.*nope\.md"):
        site.build(tmp_path / "o")


def test_a_source_without_a_title_fails_the_build_naming_the_file(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "no heading here"}, {})
    with pytest.raises(site.BuildError, match=r"01-a\.md"):
        site.build(tmp_path / "o")


def test_titles_are_escaped_everywhere(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A", "02-b.md": '# R&D <fast> "now"\n\nx'}, {})
    out = tmp_path / "o"; site.build(out)
    for name in ("index.html", "b.html"):
        h = (out / name).read_text()
        assert "<fast>" not in h and "R&amp;D &lt;fast&gt;" in h


def test_no_link_or_asset_is_root_relative_or_from_a_cdn(site, tmp_path):
    out = tmp_path / "_site"; site.build(out)
    for p in out.glob("*.html"):
        h = p.read_text()
        assert not re.search(r'(?:href|src)="/', h), p.name
        assert "fonts.googleapis.com" not in h and "gstatic.com" not in h and "cdn" not in h.lower(), p.name
        assert 'href="static/er-tokens.css"' in h and 'href="static/fonts/roboto.css"' in h and 'href="static/site.css"' in h
        assert "prefers-color-scheme" in h and "dataset.theme" in h, "the theme is set in the head"


def test_a_rebuild_leaves_no_stale_page(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A"}, {})
    out = tmp_path / "o"; site.build(out); (out / "gone.html").write_text("old")
    site.build(out)
    assert not (out / "gone.html").exists()


def test_the_reference_pages_carry_the_apps_own_rendering(site, tmp_path):
    import help_pages
    out = tmp_path / "_site"; site.build(out)
    bare = lambda h: re.sub(r"<a\b[^>]*>", "<a>", h)
    for s in help_pages.sections():
        if s["id"] == "quirks":
            continue
        assert bare(s["html"]).strip() in bare((out / f'{s["id"]}.html').read_text()), s["id"]


def test_the_site_stylesheet_takes_its_colours_from_tokens():
    css = (ROOT / "web" / "site" / "site.css").read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", css)
    assert "var(--er-ui-" in css and ".unverified" in css and "max-width: 700px" in css


# ---- the guide's content
def _guide(site, tmp_path):
    out = tmp_path / "_site"; site.build(out)
    return {n: (out / f"{n}.html").read_text() for n in ("index", "get-your-inputs", "your-first-migration")}


def test_before_you_start_says_where_the_app_is_who_signs_in_and_what_migrates(site, tmp_path):
    h = _guide(site, tmp_path)["index"]
    assert "<h1>Before you start</h1>" in h
    assert 'href="https://smart-able-977100970772.us-central1.run.app/"' in h
    assert "This email is not allowed" in h and "EarthRanger engineering team" in h
    assert "Profiles" in h and "7.5" in h and "8.0" in h and "not yet proven" in h
    assert 'href="get-your-inputs.html"' in h


def test_get_your_inputs_covers_the_backup_the_export_and_the_token(site, tmp_path):
    h = _guide(site, tmp_path)["get-your-inputs"]
    assert "Export Conservation Area" in h and ".zip" in h and not re.search(r"\.bak(?!\.zip)", h)
    assert 'class="unverified"' not in h, "every SMART step on the page has been walked in SMART Desktop or signed off"
    assert "superuser" in h and "administrator" in h and 'href="sites.html' in h
    assert "example.pamdas.org" in h


def test_your_first_migration_walks_the_steps_in_order_and_links_the_reference(site, tmp_path):
    h = _guide(site, tmp_path)["your-first-migration"]
    order = [h.index(w) for w in ("Sign in", "Upload", "Browse", "Add a site", "Make the plan", "Confirm and load")]
    assert order == sorted(order)
    for ref in ("overview.html", "sites.html", "loading.html", "statuses.html", "stops.html"):
        assert f'href="{ref}' in h, ref


def test_the_guide_names_no_real_site_and_no_token(site, tmp_path):
    for name, h in _guide(site, tmp_path).items():
        hosts = set(re.findall(r"[a-z0-9-]+\.pamdas\.org", h))
        assert hosts <= {"example.pamdas.org"}, (name, hosts)
        assert not re.search(r"\b[0-9a-f]{32,}\b", h), name


# ---- publishing
def test_the_workflow_builds_and_deploys_on_main_for_the_sites_sources():
    y = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    for path in ("web/guide/**", "web/help/**", "web/site/**", "web/static/**", "scripts/build_pages.py", "browse/build_quirks.py", "web/help_pages.py", ".github/workflows/pages.yml"):
        assert path in y, path
    assert "workflow_dispatch" in y and "branches: [main]" in y
    assert "pages: write" in y and "id-token: write" in y and "contents: read" in y
    assert "scripts/build_pages.py --out _site" in y and "actions/upload-pages-artifact" in y and "actions/deploy-pages" in y
    assert "/_site/" in (ROOT / ".gitignore").read_text()


# ---- review fixes
def test_the_build_refuses_to_empty_a_folder_it_did_not_write(site, tmp_path, monkeypatch):
    # against a stand-in repository only: a regression here must never reach the real one
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A"}, {})
    root = site.ROOT
    (root / "precious.txt").write_text("keep")
    for target in (root, root / "web", site.GUIDE_DIR):
        with pytest.raises(site.BuildError, match="refusing"):
            site.build(target)
    other = tmp_path / "docs"; other.mkdir(); (other / "precious.txt").write_text("keep")
    with pytest.raises(site.BuildError, match="refusing"):
        site.build(other)
    assert (root / "precious.txt").read_text() == "keep" and (other / "precious.txt").read_text() == "keep"
    assert (site.GUIDE_DIR / "01-a.md").is_file()


def test_a_heading_mark_alone_is_not_a_title(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "#\nBody para\n"}, {})
    with pytest.raises(site.BuildError, match=r"01-a\.md"):
        site.build(tmp_path / "o")


def test_two_sources_with_one_slug_fail_the_build_naming_both(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A", "02-overview.md": "# Mine"}, {"01-overview.md": "# Overview"})
    with pytest.raises(site.BuildError, match=r"02-overview\.md.*01-overview\.md|01-overview\.md.*02-overview\.md"):
        site.build(tmp_path / "o")


def test_the_guide_says_only_what_the_app_does(site, tmp_path):
    g = _guide(site, tmp_path)
    assert "icons" in g["index"] and "warns" in g["index"], "a missing patrol type icon is a warning, not a stop"
    assert "A plan takes a few minutes" not in g["index"]
    assert "quickest to extract" not in g["get-your-inputs"]
    m = g["your-first-migration"]
    assert re.search(r"<strong>uploading</strong>, then <strong>queued</strong>, then <strong>running</strong>, then <strong>ready</strong>", m)
    assert "until it closes" in m


def _contrast(a: str, b: str) -> float:
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_link_text_meets_wcag_aa_in_both_themes():
    """Links are body-size text, so each theme's link colour needs 4.5:1 on the page and on the
    navigation's current-page highlight."""
    tokens = (ROOT / "web" / "static" / "er-tokens.css").read_text()
    css = (ROOT / "web" / "site" / "site.css").read_text()
    split = tokens.index('[data-theme="dark"]')
    for theme, block in (("light", tokens[:split]), ("dark", tokens[split:])):
        value = dict(re.findall(r"--(er-ui-[\w-]+):\s*(#[0-9a-fA-F]{6})", block))
        link = re.search(r'\[data-theme="%s"\][^{]*\{[^}]*--link:\s*var\(--(er-ui-[\w-]+)\)' % theme, css)
        assert link, f"site.css sets --link for the {theme} theme"
        for bg in ("er-ui-background-secondary-background", "er-ui-background-elevated-component"):
            assert _contrast(value[link.group(1)], value[bg]) >= 4.5, (theme, link.group(1), bg)
    assert "var(--er-ui-cta-primary)" not in re.sub(r"\[data-theme=\"dark\"\][^}]*\}", "", css).replace(":focus-visible { outline: 2px solid var(--er-ui-cta-primary)", ""), \
        "outside the dark theme's --link, text is never the low-contrast primary green"


def test_the_header_fits_a_320px_phone():
    css = (ROOT / "web" / "site" / "site.css").read_text()
    phone = css[css.index("@media (max-width: 700px)"):]
    assert re.search(r"\.brand\s*\{[^}]*flex-wrap:\s*wrap", phone), "the lockup and the name wrap instead of overflowing"
    assert re.search(r"\.brand img\s*\{[^}]*max-width:\s*100%", phone), "the lockup shrinks to the band"


# ---- images (screenshots in the guide)
PNG = bytes.fromhex("89504e470d0a1a0a")


def test_an_image_is_copied_and_its_src_points_at_the_copy(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n![The export menu](img/smart-export-1.png)"}, {})
    (site.GUIDE_DIR / "img").mkdir(); (site.GUIDE_DIR / "img" / "smart-export-1.png").write_bytes(PNG)
    out = tmp_path / "o"; site.build(out)
    a = (out / "index.html").read_text()
    assert 'src="img/smart-export-1.png"' in a and 'alt="The export menu"' in a
    assert (out / "img" / "smart-export-1.png").read_bytes() == PNG


def test_a_missing_image_fails_the_build_naming_file_and_image(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n![x](img/nope.png)"}, {})
    with pytest.raises(site.BuildError, match=r"01-a\.md.*nope\.png"):
        site.build(tmp_path / "o")


def test_an_image_needs_alt_text(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n![](img/p.png)"}, {})
    (site.GUIDE_DIR / "img").mkdir(); (site.GUIDE_DIR / "img" / "p.png").write_bytes(PNG)
    with pytest.raises(site.BuildError, match=r"01-a\.md.*p\.png.*alt"):
        site.build(tmp_path / "o")


def test_two_different_images_with_one_name_fail_the_build(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n![g](img/p.png)"}, {"01-h.md": "# H\n\n![h](img/p.png)"})
    for d, data in ((site.GUIDE_DIR, PNG), (site.HELP_DIR, PNG + b"x")):
        (d / "img").mkdir(); (d / "img" / "p.png").write_bytes(data)
    with pytest.raises(site.BuildError, match=r"p\.png"):
        site.build(tmp_path / "o")


def test_images_fit_the_page():
    css = (ROOT / "web" / "site" / "site.css").read_text()
    assert re.search(r"main img\s*\{[^}]*max-width:\s*100%[^}]*height:\s*auto", css)


# ---- tabs (alternatives in the guide)
def test_headings_marked_as_tabs_become_one_choice_with_a_panel_each(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\nintro\n\n### One {: .tab }\n\nfirst\n\n### Two {: .tab }\n\nsecond\n\n## After\n\nrest"}, {})
    out = tmp_path / "o"; site.build(out)
    a = (out / "index.html").read_text()
    tabs = a[a.index('<div class="tabs">'):a.index("<h2>After</h2>")]
    assert re.findall(r'<input type="radio" name="tabs-1" id="(tabs-1-\d)"( checked)?><label for="\1">(\w+)</label>', tabs) == \
        [("tabs-1-1", " checked", "One"), ("tabs-1-2", "", "Two")], "radio buttons, so the tabs need no script; the first is open"
    panels = re.findall(r'<section class="tab-panel">\s*<h3>(\w+)</h3>(.*?)</section>', tabs, re.S)
    assert [p[0] for p in panels] == ["One", "Two"] and "first" in panels[0][1] and "second" in panels[1][1]
    assert "intro" in a[:a.index('<div class="tabs">')] and "rest" in a[a.index("<h2>After</h2>"):], "what surrounds the tabs stays outside them"


def test_a_lone_tab_fails_the_build(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n### One {: .tab }\n\nfirst\n\n### Plain\n\n### Two {: .tab }\n\nsecond"}, {})
    with pytest.raises(site.BuildError, match=r"01-a\.md.*One.*alone"):
        site.build(tmp_path / "o")


def test_the_stylesheet_shows_only_the_chosen_tabs_panel_and_all_of_them_on_paper():
    css = (ROOT / "web" / "site" / "site.css").read_text()
    assert re.search(r"\.tab-panel\s*\{[^}]*display:\s*none", css)
    assert re.search(r"input:nth-of-type\(3\):checked ~ \.tab-panel:nth-of-type\(3\)", css), "the guide's three-way choice"
    assert re.search(r"input:focus-visible \+ label\s*\{[^}]*outline", css), "the hidden button's focus shows on its tab"
    assert re.search(r"\.tab-panel\s*\{\s*display:\s*block", css[css.index("@media print"):])


def test_get_your_inputs_offers_the_three_smart_files_as_one_choice(site, tmp_path):
    h = _guide(site, tmp_path)["get-your-inputs"]
    assert re.findall(r'<label for="tabs-1-\d">([^<]+)</label>', h) == ["Conservation Area export", "System backup", "Zipped SMART folder"]
    assert h.count('<section class="tab-panel">') == 3 and h.index("</div>", h.rindex("</section>")) < h.index("From EarthRanger")


def test_a_tables_first_column_is_never_broken_mid_word():
    css = (ROOT / "web" / "site" / "site.css").read_text()
    assert re.search(r"td:first-child\s*\{[^}]*white-space:\s*nowrap", css), "main wraps anywhere, which split 'planning' across lines"


def test_the_zipped_folder_steps_insist_that_smart_is_closed(site, tmp_path):
    h = _guide(site, tmp_path)["get-your-inputs"]
    panel = h[h.rindex('<section class="tab-panel">'):]
    assert re.search(r'<p class="important"><strong>SMART Desktop must be closed', panel), "said before the steps, and set apart"
    assert panel.index('class="important"') < panel.index("<ol>")
    assert ".important {" in (ROOT / "web" / "site" / "site.css").read_text()


# ---- languages: the registry, a folder per language, the switcher, and what a translation must keep
# ---- languages
def test_the_registry_lists_the_five_languages_english_first(site):
    langs = site.languages()
    assert [(l.code, l.name) for l in langs] == [("en", "English"), ("fr", "Français"), ("es", "Español"), ("pt", "Português"), ("sw", "Kiswahili")]
    assert langs[0].reviewed is True and all(isinstance(l.reviewed, bool) for l in langs)


def test_every_language_has_every_shell_word_with_its_placeholders(site):
    en = site.words("en")
    assert {"site_name", "subtitle", "pages_label", "group_guide", "group_reference", "previous", "next", "footer",
            "language_label", "not_translated", "machine_translated", "english_page"} == set(en)
    for l in site.languages():
        w = site.words(l.code)
        assert set(w) == set(en), l.code
        for k in en:
            assert re.findall(r"\{\{\w+\}\}", w[k]) == re.findall(r"\{\{\w+\}\}", en[k]), (l.code, k)
            assert w[k].strip(), (l.code, k)


def test_a_words_file_missing_a_key_fails_the_build_naming_it(site, tmp_path, monkeypatch):
    d = tmp_path / "words"; d.mkdir()
    (d / "en.json").write_text('{"next": "Next", "previous": "Previous"}')
    (d / "fr.json").write_text('{"next": "Suivant"}')
    monkeypatch.setattr(site, "WORDS_DIR", d)
    with pytest.raises(site.BuildError, match=r"fr\.json.*previous"):
        site.words("fr")

def test_each_language_gets_a_folder_with_every_page_and_english_keeps_its_addresses(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# Alpha\n\nx", "02-b.md": "# Beta\n\ny", "fr/02-b.md": "# Bêta\n\nmot"}, {"01-c.md": "# Gamma\n\nz"})
    out = tmp_path / "o"; written = site.build(out)
    assert [p.name for p in written if p.parent == out] == ["index.html", "b.html", "c.html"]
    for code in ("fr", "es", "pt", "sw"):
        assert sorted(p.name for p in (out / code).glob("*.html")) == ["b.html", "c.html", "index.html"], code
    assert not (out / "en").exists()


def test_a_translated_page_is_in_its_language_and_its_shell_is_too(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# Alpha\n\nx", "fr/01-a.md": "# Alpha en français\n\nmot"}, {})
    out = tmp_path / "o"; site.build(out)
    fr = (out / "fr" / "index.html").read_text(encoding="utf-8")
    w = site.words("fr")
    assert '<html lang="fr"' in fr and "<h1>Alpha en français</h1>" in fr and "mot" in fr
    assert w["group_guide"] in fr and w["subtitle"] in fr and f'· {w["site_name"]}</title>' in fr
    assert 'class="note"' not in fr.split("<main>")[1].split("mot")[0], "a translated page carries no 'not yet translated' line"
    assert '<html lang="en"' in (out / "index.html").read_text(encoding="utf-8")


def test_a_page_with_no_translation_is_built_from_english_and_says_so(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# Alpha\n\nenglish words"}, {})
    out = tmp_path / "o"; site.build(out)
    sw = (out / "sw" / "index.html").read_text(encoding="utf-8")
    assert '<html lang="sw"' in sw and "<h1>Alpha</h1>" in sw
    assert re.search(r'<p class="note">' + re.escape(site.words("sw")["not_translated"]) + r'</p>\s*<div lang="en">', sw)
    assert "english words" in sw[sw.index('<div lang="en">'):]


def test_a_translated_page_links_to_pages_in_its_own_language_translated_or_not(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site,
         {"01-a.md": "# A\n\n[b](02-b.md) [s](../help/02-sites.md#which)", "02-b.md": "# B\n\nx",
          "fr/01-a.md": "# A fr\n\n[b](02-b.md) [s](../../help/fr/02-sites.md#which)"},
         {"02-sites.md": "# Sites\n\nx"})
    out = tmp_path / "o"; site.build(out)
    fr = (out / "fr" / "index.html").read_text(encoding="utf-8")
    assert 'href="b.html"' in fr and 'href="sites.html#which"' in fr, "neither target is translated; both lead to the page in fr/"
    assert (out / "fr" / "b.html").is_file() and (out / "fr" / "sites.html").is_file()


def test_other_languages_reach_shared_assets_and_pictures_by_climbing(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n![shot](img/s.png)", "fr/01-a.md": "# A fr\n\n![capture](../img/s.png)"}, {})
    (site.GUIDE_DIR / "img").mkdir(); (site.GUIDE_DIR / "img" / "s.png").write_bytes(b"png")
    out = tmp_path / "o"; site.build(out)
    en, fr = (out / "index.html").read_text(encoding="utf-8"), (out / "fr" / "index.html").read_text(encoding="utf-8")
    assert 'src="img/s.png"' in en and 'href="static/site.css"' in en
    assert 'src="../img/s.png"' in fr and 'alt="capture"' in fr and 'href="../static/site.css"' in fr and 'src="../static/img/' in fr
    assert (out / "img" / "s.png").is_file() and not (out / "fr" / "img").exists() and not (out / "fr" / "static").exists()
    for page in out.rglob("*.html"):   # opened from disk, every reference resolves to a file
        for ref in re.findall(r'(?:href|src)="((?:\.\./)?(?:static|img)/[^"]+)"', page.read_text(encoding="utf-8")):
            assert (page.parent / ref).resolve().is_file(), (page, ref)


def test_no_page_in_any_language_is_root_relative_or_from_a_cdn(site, tmp_path):
    out = tmp_path / "o"; site.build(out)
    for page in out.rglob("*.html"):
        h = page.read_text(encoding="utf-8")
        assert not re.search(r'(?:href|src)="/', h), page
        assert not re.search(r'(?:src|href)="https?://[^"]*\.(?:js|css|woff2?)"', h), page

def test_the_switcher_links_each_page_to_itself_in_every_language(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\nx", "02-b.md": "# B\n\ny"}, {})
    out = tmp_path / "o"; site.build(out)
    link = r'<a href="([^"]+)" lang="(\w+)" hreflang="\2" data-lang="\2"( aria-current="true")?>([^<]+)</a>'
    en = (out / "b.html").read_text(encoding="utf-8")
    nav = en[en.index('<nav class="langs"'):]; nav = nav[:nav.index("</nav>")]
    assert re.findall(link, nav) == [("b.html", "en", ' aria-current="true"', "English"), ("fr/b.html", "fr", "", "Français"),
                                     ("es/b.html", "es", "", "Español"), ("pt/b.html", "pt", "", "Português"), ("sw/b.html", "sw", "", "Kiswahili")]
    fr = (out / "fr" / "b.html").read_text(encoding="utf-8")
    nav = fr[fr.index('<nav class="langs"'):]; nav = nav[:nav.index("</nav>")]
    assert [(h, c, bool(cur)) for h, c, cur, _ in re.findall(link, nav)] == \
        [("../b.html", "en", False), ("b.html", "fr", True), ("../es/b.html", "es", False), ("../pt/b.html", "pt", False), ("../sw/b.html", "sw", False)]
    assert re.findall(r'<link rel="alternate" hreflang="(\w+)" href="([^"]+)">', fr) == \
        [("en", "../b.html"), ("fr", "b.html"), ("es", "../es/b.html"), ("pt", "../pt/b.html"), ("sw", "../sw/b.html")]
    for page in out.rglob("*.html"):   # every switcher link leads to a page
        h = page.read_text(encoding="utf-8")
        for href in re.findall(r'<a href="([^"]+)" lang="\w+" hreflang', h):
            assert (page.parent / href).resolve().is_file(), (page, href)


def test_an_unreviewed_language_shows_the_machine_translated_note_and_a_reviewed_one_does_not(site, tmp_path, monkeypatch):
    langs = [{"code": "en", "name": "English", "reviewed": True}, {"code": "fr", "name": "Français", "reviewed": False},
             {"code": "es", "name": "Español", "reviewed": True}]
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\nx", "02-b.md": "# B\n\ny"}, {}, langs=langs)
    out = tmp_path / "o"; site.build(out)
    fr = (out / "fr" / "b.html").read_text(encoding="utf-8")
    m = re.search(r'<p class="note machine">(.*?)</p>', fr, re.S)
    before, after = site.words("fr")["machine_translated"].split("{{english}}")
    assert m and before.strip() in m.group(1) and after.strip() in m.group(1)
    assert re.search(r'<a href="\.\./b\.html"[^>]*>' + re.escape(site.words("fr")["english_page"]) + "</a>", m.group(1))
    assert fr.index('class="note machine"') < fr.index("<h1>")
    for page in ("b.html", "es/b.html"):
        assert 'class="note machine"' not in (out / page).read_text(encoding="utf-8"), page


def test_each_page_loads_the_language_script_and_names_the_languages(site, tmp_path):
    out = tmp_path / "o"; site.build(out)
    assert (out / "static" / "lang.js").is_file()
    assert re.search(r'<html lang="en" data-langs="en fr es pt sw">', (out / "index.html").read_text(encoding="utf-8"))
    assert '<script src="static/lang.js"></script>' in (out / "index.html").read_text(encoding="utf-8")
    assert '<script src="../static/lang.js"></script>' in (out / "sw" / "index.html").read_text(encoding="utf-8")


def test_the_language_script_guards_storage_and_only_leaves_an_english_page():
    js = (ROOT / "web" / "site" / "lang.js").read_text()
    assert js.count("try") >= 2 and js.count("catch") >= 2, "reading and writing the choice can each throw"
    assert "location.replace" in js and "location.href =" not in js, "no entry is left in the history to bounce back to"
    assert re.search(r"lang\s*!==?\s*'en'|lang\s*===?\s*'en'", js), "only an English page sends the reader on, so there is no loop"

EN = "# A\n\nRun `SMART_<date>.bak.zip` at `example.pamdas.org`.\n\n1. one\n2. two\n\n**Stop.**\n{: .important }\n\n[b](02-b.md)"

@pytest.mark.parametrize("fr, says", [
    ("# A\n\n`SMART_<date>.bak.zip` `example.pamdas.org`\n\n1. un\n\n**Stop.**\n{: .important }\n\n[b](02-b.md)", "steps"),
    ("# A\n\n`SMART_<date>.bak.zip` `example.pamdas.org`\n\n1. un\n2. deux\n\n[b](02-b.md)", "notes"),
    ("# A\n\n`SMART_<date>.bak.zip`\n\n1. un\n2. deux\n\n**Stop.**\n{: .important }\n\n[b](02-b.md)", r"example\.pamdas\.org"),
    ("# A\n\n`SMART_<date>.bak.zip` `example.pamdas.org`\n\n1. un\n2. deux\n\n**Stop.**\n{: .important }", "links"),
])
def test_a_translation_that_lost_something_fails_the_build(site, tmp_path, monkeypatch, fr, says):
    tree(tmp_path, monkeypatch, site, {"01-a.md": EN, "02-b.md": "# B\n\nx", "fr/01-a.md": fr}, {})
    with pytest.raises(site.BuildError, match=r"fr.01-a\.md.*" + says):
        site.build(tmp_path / "o")


def test_a_faithful_translation_builds(site, tmp_path, monkeypatch):
    fr = "# A fr\n\nLancez `SMART_<date>.bak.zip` sur `example.pamdas.org`.\n\n1. un\n2. deux\n\n**Arrêtez.**\n{: .important }\n\n[b](02-b.md)"
    tree(tmp_path, monkeypatch, site, {"01-a.md": EN, "02-b.md": "# B\n\nx", "fr/01-a.md": fr}, {})
    site.build(tmp_path / "o")


def test_a_translation_with_no_english_page_or_an_unknown_language_folder_fails(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\nx", "fr/09-extra.md": "# Extra\n\nx"}, {})
    with pytest.raises(site.BuildError, match=r"09-extra\.md.*English"):
        site.build(tmp_path / "o")
    tree(tmp_path / "second", monkeypatch, site, {"01-a.md": "# A\n\nx", "de/01-a.md": "# A\n\nx"}, {})
    with pytest.raises(site.BuildError, match=r"de\b.*language"):
        site.build(tmp_path / "o2")


def test_a_translation_with_fewer_tabs_or_a_missing_picture_fails_the_build(site, tmp_path, monkeypatch):
    en = "# A\n\n### One {: .tab }\n\nx\n\n### Two {: .tab }\n\ny\n\n### Three {: .tab }\n\nz"
    tree(tmp_path, monkeypatch, site, {"01-a.md": en, "fr/01-a.md": "# A\n\n### Un {: .tab }\n\nx\n\n### Deux {: .tab }\n\ny"}, {})
    with pytest.raises(site.BuildError, match=r"fr.01-a\.md.*tabs"):
        site.build(tmp_path / "o")
    tree(tmp_path / "second", monkeypatch, site, {"01-a.md": "# A\n\n![shot](img/s.png)", "fr/01-a.md": "# A\n\npas d'image"}, {})
    (site.GUIDE_DIR / "img").mkdir(); (site.GUIDE_DIR / "img" / "s.png").write_bytes(PNG)
    with pytest.raises(site.BuildError, match=r"fr.01-a\.md.*pictures.*s\.png"):
        site.build(tmp_path / "o2")
