# Language support, part 1: the docs site. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the getting-started site (three guide pages, five help pages) in English, French, Spanish, Portuguese and Swahili, with a language switcher and a "machine translated" note.

**Architecture:** `scripts/build_pages.py` builds the site once per language in a registry. English keeps its addresses; each other language is a folder with the same page names, sharing one copy of the stylesheets, fonts and pictures. A translated source sits in a folder named for its language beside the English source; a page with no translation is built from English. A small script remembers the reader's choice and sends a first-time reader to their browser's language.

**Tech Stack:** Python 3.12, `markdown` (already used), plain JSON, plain browser JavaScript, pytest, `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-17-language-support-design.md` (Shared rules and Part 1). Parts 2 and 3 (the app, findings) have their own plans later.

## Global Constraints

- Languages and order: `en` English, `fr` Français, `es` Español, `pt` Português, `sw` Kiswahili. `en` is the source and is `reviewed: true`; the other four start `reviewed: false`.
- English page addresses do not change (`index.html`, `get-your-inputs.html`, ...). Other languages: `<code>/<same page name>`.
- Every link and asset reference in every built page is relative. Nothing loads from a CDN.
- `web/help_pages.py` and what the app serves are not changed. `help_pages` globs `web/help/*.md` only, so language folders under `web/help/` do not reach the app.
- Never translated: file names and patterns, hosts, code spans, status values, permission names, names from a site's data.
- No page in any language names a host other than `example.pamdas.org`, a real conservation area's rangers, or a token.
- A term EarthRanger or SMART already translates uses their translation (the glossary, Task 5).
- Stylesheet colours come only from `--er-ui-*` tokens (an existing test enforces it).
- Tests: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q` and `node --test "tests/js/*.test.js"`. Both pass at the end of every task.
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Do not push; do not open a PR.
- Anything read from `~/projects/smart-migration-artifacts` is interface text only. No data from it is copied into the repository.

## Review Focus

1. **A browser language with a region** (`pt-BR`, `fr-CA`, `sw-KE`): the reader is sent to `pt`, `fr`, `sw`. Test in Task 3 (`pick`).
2. **Browser storage that throws** (private window, blocked site data): the page renders, the switcher works, no error stops the script. Test in Task 3.
3. **A translated page that links to a page with no translation yet:** the link leads to that page in the same language (built from English), not out to English and not to a build failure. Test in Task 2.
4. **A remembered language that is no longer in the registry:** the reader stays on English; no redirect, no loop. Test in Task 3 (`pick`).
5. **The site opened from disk inside a language folder** (`_site/fr/index.html`): stylesheets, fonts and pictures load, because every reference climbs with `../`. Test in Task 2.

## File Structure

| File | Responsibility |
|---|---|
| `web/static/locales/languages.json` | The registry: `[{"code","name","reviewed"}]`, in display order. Read by the site build now and the app in part 2. |
| `web/site/locales/<code>.json` | The words of the page shell in one language. Flat keys. |
| `scripts/build_pages.py` | Builds every language; resolves translated sources; the refusals. |
| `web/site/page.html` | The shell; gains language, root prefix, switcher, note, alternates. |
| `web/site/lang.js` | `pick()` (pure) and the wiring that remembers a choice and redirects from English. |
| `web/site/site.css` | Styles for the switcher and the note. |
| `docs/translation-glossary.md` | One row per term, one column per language, with the source of each. |
| `web/guide/<code>/*.md`, `web/help/<code>/*.md` | The translations. |
| `tests/test_pages_site.py`, `tests/js/sitelang.test.js` | Tests. |

---

### Task 1: The registry and the shell's words

**Files:**
- Create: `web/static/locales/languages.json`, `web/site/locales/en.json`, `fr.json`, `es.json`, `pt.json`, `sw.json`
- Modify: `scripts/build_pages.py`
- Test: `tests/test_pages_site.py`

**Interfaces:**
- Produces, in `build_pages`:
  - `LOCALES_DIR = STATIC_DIR / "locales"`, `WORDS_DIR = SITE_DIR / "locales"`
  - `@dataclass Lang: code: str; name: str; reviewed: bool`
  - `languages() -> list[Lang]`: the registry in file order. `BuildError` if the file is missing, empty, or its first entry is not `en`.
  - `words(code: str) -> dict[str, str]`: that language's shell words. `BuildError` naming the file if it is missing, or lacks a key `en.json` has, or a value drops a `{{placeholder}}` the English value has.
- Shell word keys (all required), with the English values:
  - `site_name`: "SMART migration"
  - `subtitle`: "Getting started"
  - `pages_label`: "Pages"
  - `group_guide`: "Get started"
  - `group_reference`: "Reference"
  - `previous`: "Previous"
  - `next`: "Next"
  - `footer`: "The tool's source and engineering notes are on {{github}}."
  - `language_label`: "Language"
  - `not_translated`: "This page is not yet translated. It is shown in English."
  - `machine_translated`: "This translation was made by machine and has not yet been reviewed by a fluent speaker. The {{english}} is the reference."
  - `english_page`: "English page"
- The four other files translate every value, keep `{{github}}` and `{{english}}`, and follow the glossary where a term is in it (write them after Task 5 if doing tasks in order is easier; the test below only needs the keys).

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run them; expect failure** (`AttributeError: ... has no attribute 'languages'`)

Run: `.venv/bin/python -m pytest tests/test_pages_site.py -q -k "registry or shell_word or words_file"`

- [ ] **Step 3: Create the six JSON files and implement `Lang`, `languages()`, `words()`**

- [ ] **Step 4: Run the whole suite; expect pass**

- [ ] **Step 5: Commit** (`Pages: a registry of languages and the shell's words in each`)

---

### Task 2: The build writes every language

**Files:**
- Modify: `scripts/build_pages.py`, `web/site/page.html`, `tests/test_pages_site.py`

**Interfaces:**
- Consumes: `languages()`, `words()`, `Lang` from Task 1.
- Produces:
  - `Page` gains `lang: str` and `translated: bool`.
  - `pages(code: str = "en") -> list[Page]`: one page per English source, in English order, with English slugs. For `code != "en"`, a page's source is `<folder>/<code>/<same file name>` if that file exists (`translated=True`); otherwise the English file (`translated=False`).
  - `build(out: Path) -> list[Path]`: every page written, English first, then each language in registry order.
  - `_english(path: Path, code: str) -> Path`: the English source a path under a language folder stands for (`web/guide/fr/03-x.md` → `web/guide/03-x.md`); a path not under a language folder is returned unchanged.
- Rules the tests pin:
  - **Links in a translated page** are written as real relative paths from the translated file (`03-x.md`, `../../help/fr/02-sites.md`, `../img/shot.png`). A link to a `.md` is resolved, passed through `_english`, and looked up in the page list, so it works whether or not the target is translated. It becomes `<slug>.html` (same folder).
  - **Assets:** English pages reference `static/...` and `img/...`; other languages `../static/...` and `../img/...`. Pictures are published once, in `out/img/`.
  - **Shell:** `<html lang="<code>">`; the title suffix, header, navigation group names, navigation label, previous/next and footer come from `words(code)`. `{{github}}` in the footer becomes the existing GitHub link.
  - **A page with no translation:** above the body, `<p class="note">` with `not_translated`; the body is wrapped in `<div lang="en">`. Its title (page, navigation, previous/next) is the English title.
  - Template placeholder names and markup are the builder's.
- The existing test `test_the_real_site_builds_a_page_per_source_with_index_first` compares `len(names)` to the number of sources: change it to count the English pages (`[p for p in written if p.parent == out]`). No other existing test changes.
- `tree()` in the tests gains two optional arguments, `langs: list | None` and `words: dict | None`: when given, it writes a registry and words files under `tmp_path/repo` and points `LOCALES_DIR` / `WORDS_DIR` at them; file names in `guide` / `help` may include a language folder (`"fr/01-a.md"`). When not given, the real registry and words are used.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run them; expect failure**

- [ ] **Step 3: Implement.** `_sources`, `pages`, `_links`, `_images`, `_nav`, `_prev_next` and `build` take the language; `_check_out` is unchanged and still runs before anything is removed, after every language's pages have been rendered (so a source that cannot build in any language leaves the last site alone).

- [ ] **Step 4: Run the whole suite; expect pass.** Then `python scripts/build_pages.py --out _site` and confirm `_site/fr/index.html` exists.

- [ ] **Step 5: Commit** (`Pages: the build writes the site in every language`)

---

### Task 3: The switcher, the note, and remembering a choice

**Files:**
- Create: `web/site/lang.js`, `tests/js/sitelang.test.js`
- Modify: `scripts/build_pages.py`, `web/site/page.html`, `web/site/site.css`, `tests/test_pages_site.py`

**Interfaces:**
- Consumes: `Lang.reviewed`, `words()`; the per-language build from Task 2.
- Produces in each page:
  - In the head: one `<link rel="alternate" hreflang="<code>" href="<relative>">` per language, including the page's own.
  - In the header: `<nav class="langs" aria-label="<language_label>">` holding, for each language in registry order, `<a href="<relative>" lang="<code>" hreflang="<code>" data-lang="<code>">Name</a>`; the current language's link also has `aria-current="true"`. `<relative>` is the same page in that language: from English `fr/b.html`; from French `../b.html` (English) and `../es/b.html`.
  - When the page's language is `reviewed: false`: `<p class="note machine">` holding `machine_translated`, with `{{english}}` replaced by `<a href="<this page in English>" lang="..." >english_page</a>`. It is inside `<main>`, above the `<h1>`. A reviewed language has no such element.
  - `<html ... data-langs="en fr es pt sw">` (the registry's codes) and a blocking `<script src="<root>static/lang.js"></script>` in the head. The build copies `web/site/lang.js` to `out/static/lang.js`.
- `web/site/lang.js`:
  - `pick(stored, browser, supported) -> string | null`: the language to go to from an English page, or `null` to stay. `stored` is the remembered code or `null`; `browser` is `navigator.languages` (may be undefined); `supported` is the registry's codes.
    - `stored` in `supported` → `stored`, except `"en"` → `null`.
    - `stored` not in `supported` (or `null`) → the first entry of `browser` whose part before `-`, lower-cased, is in `supported`; `"en"` → `null`; none → `null`.
  - Wiring: reads `localStorage.getItem('lang')`; on a page whose `<html lang>` is `en`, if `pick(...)` returns a code, `location.replace(code + '/' + <page file name or index.html> + location.hash)`. A click on any `[data-lang]` link stores that code. Every storage read and write is inside `try/catch`; a throw is treated as "nothing remembered".
  - Exported for Node the way `web/static/pages.js` is (see `tests/js/shim.js`); with no `document`, loading it does nothing but define `pick`.
- CSS: the switcher sits at the right of the header band and wraps under the brand on a narrow screen; `.note` is a quiet bordered paragraph. Tokens only. The header must still fit 320px (`test_the_header_fits_a_320px_phone` must keep passing; extend it if the switcher changes what it measures).

- [ ] **Step 1: Write the failing tests**

`tests/js/sitelang.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { pick } = require('../../web/site/lang.js');
const S = ['en', 'fr', 'es', 'pt', 'sw'];

test('a remembered language wins over the browser', () => {
  assert.equal(pick('fr', ['es-ES'], S), 'fr');
  assert.equal(pick('en', ['fr-FR'], S), null);            // choosing English sticks
});
test('with nothing remembered, the first browser language the site has', () => {
  assert.equal(pick(null, ['pt-BR', 'en'], S), 'pt');
  assert.equal(pick(null, ['fr-CA'], S), 'fr');
  assert.equal(pick(null, ['SW-ke'], S), 'sw');
  assert.equal(pick(null, ['de-DE', 'es'], S), 'es');
  assert.equal(pick(null, ['en-GB', 'fr'], S), null);      // English comes first: stay
  assert.equal(pick(null, ['de', 'ja'], S), null);
  assert.equal(pick(null, undefined, S), null);
  assert.equal(pick(null, [], S), null);
});
test('a remembered language the site no longer has is ignored', () => {
  assert.equal(pick('ne', ['en-US'], S), null);
  assert.equal(pick('ne', ['es'], S), 'es');
});
```

`tests/test_pages_site.py`:

```python
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
```

- [ ] **Step 2: Run both suites; expect failure**

- [ ] **Step 3: Implement** the switcher, alternates, note, `lang.js`, the copy in `build()`, and the styles.

- [ ] **Step 4: Run both suites; expect pass.** Build, then open `_site/index.html` and `_site/fr/index.html` in headless Chrome at 1100px and 360px wide and look at the header, the switcher and the note in light and dark.

- [ ] **Step 5: Commit** (`Pages: a language switcher, a remembered choice, and the machine-translated note`)

---

### Task 4: The build refuses a translation that lost something

**Files:**
- Modify: `scripts/build_pages.py`, `tests/test_pages_site.py`

**Interfaces:**
- Produces: `_shape(body_html: str) -> dict` with keys `tabs` (count of tab panels), `images` (sorted published names), `steps` (count of `<li>` directly inside `<ol>`), `notes` (count of elements with class `important` or `unverified`), `code` (set of the text of every `<code>` outside `<pre>`), `links` (sorted `href`s after link rewriting, outside links included).
- In `pages(code)`, for each translated page, compare `_shape` with its English page's. `BuildError` naming the translated file and the first difference when: `tabs`, `steps` or `notes` differ; `images` differ; a `code` text of the English page is missing; `links` differ.
- `BuildError` naming the file when a `.md` in a language folder has no English file of the same name, and when a folder under `web/guide/` or `web/help/` other than `img` is not a registry code.

- [ ] **Step 1: Write the failing tests**

```python
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
```

Add a tabs case and a pictures case in the same style (a translation with two tabs where English has three; a translation missing a picture).

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run the whole suite; expect pass**
- [ ] **Step 5: Commit** (`Pages: a translation that lost a step, a note, a picture or a name fails the build`)

---

### Task 5: The glossary

**Files:**
- Create: `docs/translation-glossary.md`

**What it holds:** a short introduction for a reviewer (what the glossary is for; that the four translations are unreviewed; how to correct a page and how to mark a language reviewed, pointing at `web/DEPLOY.md`), then one table per group of terms. Columns: English, Français, Español, Português, Kiswahili, Source.

**Sources, in order (spec, "Terms"):**
1. EarthRanger: `/Users/chrisdo/padas/das-web-react/public/locales/{fr,es,pt,sw}/*.json` against `en-US/`. Find the English value, take the same key's value in each language. Source column: `EarthRanger`.
2. SMART Desktop 7.5.6: the `.properties` message bundles inside the `org.wcs.smart*` jars under `plugins/` in `~/projects/smart-migration-artifacts/SMART 7.5.6 (R5 Lawin).zip` (`*_fr.properties`, `*_es.properties`, `*_pt.properties`, `*_sw.properties` beside the English bundle). Extract only those jars into a new empty folder in the scratchpad; read only `.properties` files; copy nothing else. Source column: `SMART 7.5.6`. `.properties` files escape non-ASCII as `\uXXXX`: decode them.
3. Neither has it: translate it, Source column `not from a product`.

**Terms to cover, at least:**
- EarthRanger: patrol, patrol type, track, event, event type, event category, subject, subject group, report, user, permission, token, site, administrator, superuser.
- SMART interface, exactly as in the English steps: Conservation Area, Username, Password, Login, File, Export Conservation Area..., Backup System, Backup SMART System, Browse..., Export, Backup, Cancel, OK, Exclude filestore from backup, "Conservation Area exported successfully.", Backup Complete, "System backed up successfully to file:", Exit.
- This tool's own words: dataset, upload, extract / extraction, browse, load, plan, confirm, finding, blocking finding, warning, stage, run, continuation, roster, ranger, waypoint, observation, attachment, getting started, reference.
- Windows words used in the zipped-folder steps: File Explorer, Send to, Compressed (zipped) folder, Compress to ZIP file. Source: `not from a product` unless found.

**Rules:**
- Where SMART has no entry in a language for a name, write `(English only)` in that cell; the step will give the English name alone.
- Where EarthRanger and SMART translate one English word differently (for example "patrol"), keep both rows and say in the Source column which product each belongs to; the pages use EarthRanger's word when talking about EarthRanger and the app, and SMART's when naming something on a SMART screen.
- End with a section "Checked by a fluent speaker", empty for now, with one line per language for a reviewer's name and date.

- [ ] **Step 1:** Build the term list; pull the EarthRanger translations.
- [ ] **Step 2:** Pull the SMART translations as above. Record in the glossary's introduction which SMART names had no entry in which language.
- [ ] **Step 3:** Fill the rest; write the file.
- [ ] **Step 4:** Check: every cell is filled or says `(English only)`; no row names a real conservation area, person or host. Run `grep -i "lawin\|camarines\|albay" docs/translation-glossary.md` and expect no output.
- [ ] **Step 5: Commit** (`Docs: the translation glossary, from EarthRanger's and SMART's own translations`)

---

### Task 6: The guide in four languages

**Files:**
- Create: `web/guide/{fr,es,pt,sw}/01-before-you-start.md`, `02-get-your-inputs.md`, `03-your-first-migration.md` (twelve files)
- Modify (if not done in Task 1): `web/site/locales/{fr,es,pt,sw}.json` to follow the glossary
- Test: `tests/test_pages_site.py`

**Rules for every translated page:**
- Same structure as the English page, in the same order: headings, steps, tabs (`{: .tab }`), notes (`{: .important }`), pictures, links. Task 4's checks enforce the counts.
- Terms from the glossary. Plain, second person, short sentences, as the English is. Use the formal or neutral address usual in software for that language, the same on every page.
- Not translated: code spans, file names, hosts, the app's address, status values.
- Buttons and screens of this app are named in English in bold, followed by the translation in brackets the first time on a page, because the app is English until part 2. (Part 2 removes the English.)
- **SMART steps:** each SMART menu, window or button is named as the glossary gives it for that language, in bold, followed by the English name in brackets: `**Fichier → …** (File → Export Conservation Area...)`. Where the glossary says `(English only)`, give the English name alone, in bold.
- Pictures: `![alt text in the page's language](../img/<same file>.png)`. The alt text describes the picture, which shows SMART in English; where it quotes a label in the picture, it quotes the English label.
- Links: to a page in the same folder by its file name; to a help page as `../../help/<code>/<file>.md`; to a repository file by its real relative path.

- [ ] **Step 1: Write the failing test**

```python
def test_the_guide_is_translated_into_every_language(site, tmp_path):
    for l in site.languages()[1:]:
        ps = {p.slug: p for p in site.pages(l.code)}
        for slug in ("index", "get-your-inputs", "your-first-migration"):
            assert ps[slug].translated, (l.code, slug)
            assert ps[slug].title != {p.slug: p for p in site.pages("en")}[slug].title or l.code == "en", (l.code, slug)


def test_no_page_in_any_language_names_a_real_site_or_a_token(site, tmp_path):
    out = tmp_path / "o"; site.build(out)
    for page in out.rglob("*.html"):
        h = page.read_text(encoding="utf-8")
        assert set(re.findall(r"[a-z0-9-]+\.pamdas\.org", h)) <= {"example.pamdas.org"}, page
        assert not re.search(r"\b[0-9a-f]{32,}\b", h), page


def test_translated_smart_steps_give_the_english_menu_name_beside_the_translated_one(site, tmp_path):
    out = tmp_path / "o"; site.build(out)
    for code in ("fr", "es", "pt", "sw"):
        h = (out / code / "get-your-inputs.html").read_text(encoding="utf-8")
        assert "Export Conservation Area..." in h and "Backup System" in h, code   # the picture shows these words
        assert h.count('<section class="tab-panel">') == 3, code
```

- [ ] **Step 2: Run; expect failure** (pages not translated)
- [ ] **Step 3: Write the twelve pages**, one language at a time, building after each (`python scripts/build_pages.py --out _site`) so Task 4's checks catch a dropped step at once.
- [ ] **Step 4: Run the whole suite; expect pass.** Open `get-your-inputs.html` in each language in headless Chrome at 1100px and 360px and look at each of the three tabs: nothing overflows, no tab label is cut.
- [ ] **Step 5: Commit** (`Guide: French, Spanish, Portuguese and Swahili`)

---

### Task 7: The reference pages in four languages

**Files:**
- Create: `web/help/{fr,es,pt,sw}/01-overview.md`, `02-sites.md`, `03-loading.md`, `04-statuses.md`, `05-stops.md` (twenty files)
- Test: `tests/test_pages_site.py`

**Rules:** as Task 6, plus:
- Status values in the tables (`planning`, `needs_attention`, ...) stay as they are, in code where the English has code; only the "Meaning" column and the headings are translated. The plain-text stage statuses (`pending`, `not reached`, ...) are shown as the app shows them, in English, followed by the translation in brackets.
- Where a help page refers to another by title in italics, use that page's translated title.
- `web/help/*.md` (English) is not edited. `web/help_pages.py` is not edited.

- [ ] **Step 1: Write the failing test**

```python
def test_the_reference_is_translated_into_every_language_and_the_app_still_serves_english(site, tmp_path, monkeypatch):
    for l in site.languages()[1:]:
        ps = {p.slug: p for p in site.pages(l.code)}
        for slug in ("overview", "sites", "loading", "statuses", "stops"):
            assert ps[slug].translated, (l.code, slug)
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    import help_pages
    titles = [s["title"] for s in help_pages.sections()]
    assert "Statuses" in titles and len(titles) == len(list((ROOT / "web" / "help").glob("*.md"))) + 1, "five pages and the quirks reference, in English only"


def test_status_values_survive_translation(site, tmp_path):
    out = tmp_path / "o"; site.build(out)
    for code in ("fr", "es", "pt", "sw"):
        h = (out / code / "statuses.html").read_text(encoding="utf-8")
        for v in ("planning", "planned", "queued", "running", "continuing", "needs_attention", "done", "failed"):
            assert f"<code>{v}</code>" in h, (code, v)
```

(If `help_pages.sections()` returns a different shape than a list of dicts with `title`, adapt the assertion to it; the point is that the app's help is unchanged.)

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Write the twenty pages**, building after each language.
- [ ] **Step 4: Run both suites; expect pass.** View `statuses.html` and `stops.html` in each language at 360px wide: the tables do not push the page sideways.
- [ ] **Step 5: Commit** (`Reference: French, Spanish, Portuguese and Swahili`)

---

### Task 8: Say how it works, and check the whole site

**Files:**
- Modify: `web/DEPLOY.md` (section "The getting-started site"), `README.md` (the line about the site), `tests/test_pages_site.py`

**`web/DEPLOY.md` gains, briefly:**
- The site is in five languages; where the registry, the shell's words and the translated pages are.
- **To correct a translation:** edit the page under `web/guide/<code>/` or `web/help/<code>/`; keep its steps, tabs, pictures, notes, links and code as the English page has them, or the build fails and says what is missing.
- **To mark a language reviewed:** set `"reviewed": true` in `web/static/locales/languages.json`; the "machine translated" note goes.
- **When an English page changes:** change the four translations in the same pull request; the build's checks catch a missing step but not a changed sentence.
- **To add a language:** a registry entry, a words file, and pages as they are translated; untranslated pages show in English.
- A pointer to `docs/translation-glossary.md`.

- [ ] **Step 1: Write the failing test**

```python
def test_the_deploy_notes_say_how_to_correct_and_review_a_translation():
    d = (ROOT / "web" / "DEPLOY.md").read_text()
    assert "languages.json" in d and '"reviewed": true' in d and "translation-glossary.md" in d
    assert "web/guide/<code>/" in d
```

- [ ] **Step 2: Run; expect failure. Write the section. Run both suites; expect pass.**
- [ ] **Step 3: Check the built site as a reader would.** `python scripts/build_pages.py --out _site`, then in headless Chrome:
  - every page of every language at 1100px (40 pages): the note shows on the four unreviewed languages and not on English; the navigation, previous/next and footer are in the page's language;
  - `index.html`, `get-your-inputs.html` and `statuses.html` in every language at 360px: no sideways scroll;
  - `_site/fr/index.html` opened from disk: styled, lockup and pictures present.
  Report what was looked at and what was not.
- [ ] **Step 4: Commit** (`Docs: how the site's languages work, and how to correct and review a translation`)
