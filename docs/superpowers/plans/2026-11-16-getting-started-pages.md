# Getting-started Pages Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public static site at `https://padas.github.io/er-smart-able/` that gets a support person from nothing to a first SMART-to-EarthRanger migration with the hosted app.

**Architecture:** `scripts/build_pages.py` renders `web/guide/*.md` (new) and `web/help/*.md` (the in-app help, unchanged) to `_site/` with the app's Markdown renderer, a page template and a site stylesheet in `web/site/`, and assets copied from `web/static/`. A GitHub Actions workflow builds and deploys it to Pages on pushes to `main`.

**Tech Stack:** Python 3.12, `markdown>=3.6` (already a dependency), pytest, GitHub Actions (`upload-pages-artifact`, `deploy-pages`).

**Spec:** `docs/superpowers/specs/2026-11-16-getting-started-pages-design.md`

## Global Constraints

- The app is unchanged: `web/help_pages.py`'s behaviour, `/api/help` and `tests/test_help.py` stay as they are and pass.
- `web/help/*.md` is not edited. Nothing from it is pasted into `web/guide/`.
- Nothing loads from a CDN or Google Fonts. No Material Symbols icons on the site.
- Site CSS uses only `var(--er-ui-*)` tokens for colour (plus `transparent`, `inherit`, `currentColor`).
- All links between pages and to assets are relative, with no leading `/`.
- The theme follows the system; `data-theme` is set by an inline head script as in `web/templates/index.html`. No theme switch.
- No real conservation area's ranger names, no customer EarthRanger host, no token. The only `*.pamdas.org` host allowed is `example.pamdas.org`.
- The app's address is exactly `https://smart-able-977100970772.us-central1.run.app/`.
- The unverified note's text is exactly: `These steps are not yet verified against SMART Desktop.`
- Voice of the guide pages: plain, second person, short steps, as in `web/help/`.
- Run tests with `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q` from the repository root.
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.

## Review Focus

1. A link from one page to another with an anchor (`02-sites.md#which-user`) keeps the anchor: `sites.html#which-user`.
2. A page title with `<`, `&` or `"` is escaped in `<title>`, the navigation and the previous/next links.
3. `_site/index.html` opened from disk works: no `href` or `src` begins with `/`.
4. A second build into an `--out` folder that holds a page from an earlier build (a source file since removed) leaves no stale page behind.
5. A source file with no `#` title heading fails the build, naming the file, and does not produce an untitled page.

Each has its test in Task 1.

## File Structure

| File | Responsibility |
| --- | --- |
| `scripts/build_pages.py` | Collect sources, render, rewrite links, write `_site/` |
| `web/site/page.html` | The page shell, with `{{name}}` placeholders |
| `web/site/site.css` | The site's layout, tokens only |
| `web/guide/01-before-you-start.md`, `02-get-your-inputs.md`, `03-your-first-migration.md` | The new pages |
| `tests/test_pages_site.py` | Build and content tests |
| `.github/workflows/pages.yml` | Build and deploy to Pages |
| `.gitignore`, `README.md`, `web/DEPLOY.md` | `_site/` ignored; the site documented |

---

### Task 1: The build script, template and stylesheet

**Files:**
- Create: `scripts/build_pages.py`, `web/site/page.html`, `web/site/site.css`
- Create: `web/guide/01-before-you-start.md` with a title and one sentence only (Task 2 writes the content); the build needs at least one guide page
- Test: `tests/test_pages_site.py`

**Interfaces:**
- Produces (in `scripts/build_pages.py`):
  - `GUIDE_DIR`, `HELP_DIR`, `SITE_DIR`, `STATIC_DIR`: module-level `Path`s (`web/guide`, `web/help`, `web/site`, `web/static`), so a test can point them at a temporary tree with `monkeypatch.setattr`.
  - `@dataclass Page`: `src: Path`, `slug: str`, `title: str`, `group: str`, `html: str`. `group` is `"Get started"` for guide files and `"Reference"` for help files. `slug` is the filename without its `NN-` prefix and `.md`; the first guide page's slug is `index`.
  - `class BuildError(Exception)`: its message names the source file and, for a link, the link.
  - `pages() -> list[Page]`: guide files in filename order, then help files in filename order.
  - `build(out: Path) -> list[Path]`: empties `out`, writes `<slug>.html` per page, copies assets to `out/static/` (`er-tokens.css`, `fonts/`, `img/`, `site.css`), returns the written page paths.
  - CLI: `python scripts/build_pages.py [--out _site]`; exits 1 with the `BuildError` message on stderr.

- [ ] **Step 1: Write the failing tests** in `tests/test_pages_site.py`

A fixture `site(tmp_path, monkeypatch)` loads `scripts/build_pages.py` with `importlib.util` and returns the module; a helper `tree(tmp_path, monkeypatch, mod, guide: dict, help: dict)` writes Markdown files under a temporary `guide/` and `help/` and points `GUIDE_DIR` and `HELP_DIR` at them.

```python
def test_the_real_site_builds_a_page_per_source_with_index_first(site, tmp_path):
    out = tmp_path / "_site"
    written = site.build(out)
    names = [p.name for p in written]
    assert names[0] == "index.html"
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
```

For that test the temporary `guide/` must sit two levels below a stand-in for the repository root, or the helper resolves repository files against the real `ROOT`; the implementer chooses, provided the real `README.md` is what the link is checked against.

```python
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
    out = tmp_path / "o"; out.mkdir(); (out / "gone.html").write_text("old")
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A"}, {})
    site.build(out)
    assert not (out / "gone.html").exists()

def test_the_reference_pages_carry_the_apps_own_rendering(site, tmp_path):
    sys.path.insert(0, str(ROOT / "web")); import help_pages
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
```

- [ ] **Step 2: Run them and see them fail**

Run: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q tests/test_pages_site.py`
Expected: every test errors, because `scripts/build_pages.py` does not exist.

- [ ] **Step 3: Write `web/site/page.html`**

Placeholders the script fills: `{{title}}` (escaped), `{{nav}}`, `{{body}}`, `{{prev_next}}`. The head carries the inline theme script (copy the one in `web/templates/index.html`), then `static/er-tokens.css`, `static/fonts/roboto.css`, `static/site.css`. The header band holds `static/img/er-lockup-white-h-short.svg` (alt "EarthRanger") and the text `SMART migration · Getting started`, linking to `index.html`. `<title>` is `{{title}} · SMART migration`. The body is `<nav>` then `<main>` containing `<h1>{{title}}</h1>{{body}}{{prev_next}}`. A footer links to `https://github.com/PADAS/er-smart-able`.

- [ ] **Step 4: Write `web/site/site.css`**

Tokens only. Two columns (navigation about 240px, content with a readable measure of about 72ch); under `max-width: 700px` the navigation sits above the content and nothing scrolls sideways (`overflow-wrap: anywhere` on content, tables and `pre` scroll inside themselves). Navigation groups have a heading each; the current link is marked from `[aria-current="page"]`. `.unverified` is a callout: a bordered, tinted block. `.prev` and `.next` sit at the foot, left and right.

- [ ] **Step 5: Write `scripts/build_pages.py`** to the Interfaces above

Render with `help_pages._split_title` and `build_quirks.convert(body, help_pages.EXTENSIONS)` by importing `web/help_pages.py` (put `web/` on `sys.path`); do not change that module. Rewrite links on the rendered HTML: a relative `href` ending `.md` (with optional `#anchor`) is resolved from the source file's folder; if it is one of the site's sources it becomes `<slug>.html#anchor`; otherwise, if the file exists in the repository, `https://github.com/PADAS/er-smart-able/blob/main/<path>#anchor`; otherwise `BuildError`. `https?://` links get `target="_blank" rel="noopener"`. Escape titles with `html.escape`. `build` removes `out` if it exists before writing.

- [ ] **Step 6: Run the tests and see them pass**

Run: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q tests/test_pages_site.py tests/test_help.py`
Expected: all pass.

- [ ] **Step 7: Build and look**

Run: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python scripts/build_pages.py --out /tmp/site-check && ls /tmp/site-check`
Expected: `index.html`, the five reference pages, `static/`.

- [ ] **Step 8: Commit**

```bash
git add scripts/build_pages.py web/site web/guide tests/test_pages_site.py
git commit -m "Pages: a build script renders the guide and the in-app help as a static site"
```

---

### Task 2: The three guide pages

**Files:**
- Modify: `web/guide/01-before-you-start.md`
- Create: `web/guide/02-get-your-inputs.md`, `web/guide/03-your-first-migration.md`
- Test: `tests/test_pages_site.py` (append)

**Interfaces:**
- Consumes: `build(out)` and the slugs from Task 1: `index`, `get-your-inputs`, `your-first-migration`, and the reference pages `overview`, `sites`, `loading`, `statuses`, `stops`.

Read before writing, and take every fact from them: `web/help/*.md` (all five), `README.md` ("Quick start", "What you get"), `RUNBOOK.md` (the sections on backups and exports), `docs/profiles-to-er-entities.md` (its conclusion only). Do not state anything these do not support.

- [ ] **Step 1: Write the failing tests**

```python
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
    assert re.search(r'class="unverified"[^>]*>\s*These steps are not yet verified against SMART Desktop\.', h)
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
```

- [ ] **Step 2: Run them and see them fail**

Run: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q tests/test_pages_site.py -k "before_you_start or get_your_inputs or first_migration or no_real_site"`
Expected: FAIL (the two pages do not exist; the first is a stub).

- [ ] **Step 3: Write `01-before-you-start.md`** (title `# Before you start`)

Sections: what the tool does (one paragraph); what it migrates and what it does not (two short lists; "does not" includes what the loading help says is skipped or left to a person, and that Profiles data can be browsed but is not loaded); supported SMART versions (7.5.x proven; 8.0–8.1.x expected to work and not yet proven); where the app is (the address as a link) and who can sign in (the exact sign-in wording from the spec's Content section); what you need before you begin, linking to `02-get-your-inputs.md`.

- [ ] **Step 4: Write `02-get-your-inputs.md`** (title `# Get your inputs`)

Two parts. **From SMART**: the three accepted inputs (a system backup zip named `SMART_<date>.bak.zip`, a zipped SMART Desktop install folder, a Conservation Area export from File → Export Conservation Area), upload a `.zip` only, with this paragraph directly above the steps:

```markdown
These steps are not yet verified against SMART Desktop.
{: .unverified }
```

**From EarthRanger**: the host (host only, without `https://`, as `example.pamdas.org`) and an API token: which user and permissions (from `web/help/02-sites.md`, linked), a superuser is the simple choice, and "ask the site's EarthRanger administrator for a token"; no click path.

- [ ] **Step 5: Write `03-your-first-migration.md`** (title `# Your first migration`)

Numbered steps, each naming the button or page as the app labels it, each ending with a link to the reference page that covers it: Sign in → Upload ("Upload a backup or export") → wait for extraction (status pills; `04-statuses.md`) → Browse → Add a site ("EarthRanger sites" in the account menu; `02-sites.md`) → "Load into EarthRanger" and "Make the plan" (`03-loading.md`) → read the plan and its findings → "Confirm and load" → what to do if it stops (`05-stops.md`) → check the result in EarthRanger. Recommend a data-model-only load first, if the loading help supports that as an option.

- [ ] **Step 6: Run the tests and see them pass**

Run: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q tests/test_pages_site.py`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add web/guide tests/test_pages_site.py
git commit -m "Pages: before you start, get your inputs, your first migration"
```

---

### Task 3: Publish and document

**Files:**
- Create: `.github/workflows/pages.yml`
- Modify: `.gitignore`, `README.md` (the "Documentation" section), `web/DEPLOY.md` (a new section after "4. Verify")
- Test: `tests/test_pages_site.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_the_workflow_builds_and_deploys_on_main_for_the_sites_sources():
    y = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    for path in ("web/guide/**", "web/help/**", "web/site/**", "web/static/**", "scripts/build_pages.py", "browse/build_quirks.py", "web/help_pages.py", ".github/workflows/pages.yml"):
        assert path in y, path
    assert "workflow_dispatch" in y and "branches: [main]" in y
    assert "pages: write" in y and "id-token: write" in y and "contents: read" in y
    assert "scripts/build_pages.py --out _site" in y and "actions/upload-pages-artifact" in y and "actions/deploy-pages" in y
    assert "/_site/" in (ROOT / ".gitignore").read_text()
```

- [ ] **Step 2: Run it and see it fail**

Run: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q tests/test_pages_site.py -k workflow`
Expected: FAIL, no such file.

- [ ] **Step 3: Write `.github/workflows/pages.yml`**

```yaml
name: Publish the getting-started site

# Builds web/guide and web/help into a static site and deploys it to GitHub Pages.
# One-time setup by a repository admin: Settings → Pages → Source: GitHub Actions.
on:
  push:
    branches: [main]
    paths:
      - "web/guide/**"
      - "web/help/**"
      - "web/site/**"
      - "web/static/**"
      - "web/help_pages.py"
      - "browse/build_quirks.py"
      - "scripts/build_pages.py"
      - ".github/workflows/pages.yml"
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install "markdown>=3.6"
      - run: python scripts/build_pages.py --out _site
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: _site
      - id: deploy
        uses: actions/deploy-pages@v4
```

- [ ] **Step 4: Ignore the output and document the site**

`.gitignore`: add `/_site/` with a one-line comment. `README.md`, "Documentation": one bullet linking `https://padas.github.io/er-smart-able/` as the getting-started guide for the hosted app, built from `web/guide/` and `web/help/`. `web/DEPLOY.md`: a section "The getting-started site" saying what it is built from, how to build it locally (`python scripts/build_pages.py`, then open `_site/index.html`), that it publishes on merges to `main` that touch its sources, and the one-time Pages setting.

- [ ] **Step 5: Run every test**

Run: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q`
Expected: all pass, the two existing skips unchanged.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/pages.yml .gitignore README.md web/DEPLOY.md tests/test_pages_site.py
git commit -m "Pages: publish the site from main; document it"
```
