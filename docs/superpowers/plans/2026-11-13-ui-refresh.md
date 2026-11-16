# UI Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the hosted app around the dataset (home list, a dataset page with Overview, Loads and Rangers tabs, the load page in the same frame, sites under the account menu) and put it and the viewer on the EarthRanger design system: its tokens, Roboto, status colours, dark mode, one header.

**Architecture:** The FastAPI service and its API are unchanged. The page keeps one template, one stylesheet and plain scripts: a new `web/static/pages.js` holds pure functions (route parsing, HTML builders for every page and section, the status-to-token mapping) with no DOM access, so Node can test them; `web/static/app.js` keeps the wiring (fetching, history, polling, dialogs, the help drawer) and mounts the HTML the builders return. Colour comes only from `web/static/er-tokens.css`, a copy of the design system's generated stylesheet. The viewer stays a single self-contained file whose header and inline tokens are brought to the same look.

**Tech Stack:** FastAPI + Jinja2 (unchanged), vanilla JavaScript, CSS custom properties, Node's built-in test runner (`node --test`) driven from pytest, Roboto woff2 self-hosted.

**Spec:** `docs/superpowers/specs/2026-11-13-ui-refresh-design.md`

## Global Constraints

- Semantic tokens only: `web/static/app.css` contains no raw colour (`#hex`, `rgb(`, `hsl(`, named colours); every colour is `var(--er-...)` from `er-tokens.css`. The viewer's inline tokens carry the same values with a comment naming `er-tokens.css` as the source.
- Fonts: Roboto 400, 500, 700, Latin subset, self-hosted under `web/static/fonts/`, `font-display: optional`, fallback stack `Roboto, system-ui, "Helvetica Neue", Arial, sans-serif`; monospace `"Roboto Mono", ui-monospace, Menlo, monospace` without shipping a mono font. No Google Fonts stylesheet link for text fonts (Material Symbols stays as the icon font).
- Header: the white horizontal short lockup `EarthRanger-Logo-2026_Ai2-white-H-short.svg` on the teal band; the product name is **SMART migration**; "smart-able" appears only in `<title>` and the version string.
- Routes: `#/`, `#/datasets/<id>`, `#/datasets/<id>/loads`, `#/datasets/<id>/rangers`, `#/datasets/<id>/loads/<load>`, `#/sites`; `#load/<id>` redirects to the load's new route.
- Status tokens (spec §8): running/continuing/extracting → `--er-ui-status-running` on `--er-ui-status-bg-draft-bg`; done/ready/success → `--er-ui-status-success` on `--er-ui-status-bg-synced-bg`; needs_attention/warning → `--er-ui-status-warning` on `--er-ui-status-bg-warning-bg`; failed/blocking/error → `--er-ui-status-error-destructive` on `--er-ui-status-bg-error-bg`; planned → `--er-ui-status-ready`; queued/planning/uploading/pending → `--er-ui-status-disabled` on `--er-ui-status-bg-pending-sync-bg`; interrupted → error text on pending background.
- Content at most 1100px wide, 16px gutters, no horizontal page scroll at phone width.
- Dark mode: both pages follow `prefers-color-scheme` and honour `data-theme="light"|"dark"` on `<html>`; the choice is stored under `localStorage` key `theme` and read by both pages.
- All existing behaviour of the load page (polling, open-state and scroll preservation, the rangers memo, per-execution import wording) and of the help drawer is kept.
- Commit messages and PR descriptions end with the attribution lines in the session's system reminder.

## Review Focus

1. A route for a dataset or load the user cannot read (deleted, unshared, or a typo in a shared link): the page says "Not found or not shared with you" with a link home and replaces the entry, rather than an alert loop or a blank page. (Task 3 tests `parseRoute`; Task 6 adds the 404 render test and the replace-on-404 behaviour.)
2. A dataset whose extraction failed before any conservation area was written: the dataset page still opens, Overview shows the status and error, the other tabs are disabled rather than empty. (Task 6.)
3. The dataset page's Rangers tab when the latest load is a plan (no subject ids) or a data-model-only load (0 in-load patrols): the list still shows with the right wording, as the load page does. (Task 6 reuses the load page's section builder; Task 7 tests it with both shapes.)
4. Theme choice made on the app must apply when the viewer opens, and the viewer standalone (no app, maybe `file://`) must not throw on `localStorage` access. (Task 9.)
5. The upload dialog closed while an upload is in flight: the upload continues and the new dataset appears in the list. (Task 5.)

---

## File Structure

| File | Responsibility |
|---|---|
| `web/static/er-tokens.css` | Verbatim copy of the design system's `tokens.css`; the one source of colour (created, Task 1) |
| `web/static/fonts/roboto-{400,500,700}.woff2`, `web/static/fonts/roboto.css` | Self-hosted Roboto and its `@font-face` rules (Task 1) |
| `scripts/fetch_fonts.py` | Fetches and writes the font files, run once; documented in DEPLOY.md (Task 1) |
| `web/static/img/er-lockup-white-h-short.svg`, `er-lockup-h.svg` | The two lockups, copied from the design repository (Task 4) |
| `web/static/pages.js` | Pure functions: `parseRoute`, `routeHash`, `statusClass`, `pill`, and every `render*` builder returning HTML strings. No `document`, `window`, `fetch` (Tasks 3–8) |
| `web/static/app.js` | Wiring: `api`, `boot`, history and `navigate`, page mounting, polling, dialogs, the help drawer, theme switch (Tasks 3–8) |
| `web/static/app.css` | The app's styles on the tokens (Task 4, extended by later tasks) |
| `web/templates/index.html` | The shell: header, breadcrumb slot, `<main id="page">`, dialogs, help drawer (Task 4) |
| `web/app.py:60` | `ASSETS` gains the new static files for cache-busting (Task 1, Task 3) |
| `browse/index.html`, `browse/build_quirks.py` | The viewer's header, tokens, fonts, theme key (Task 9) |
| `tests/test_static_assets.py` | Stylesheet and font rules; runs the Node tests (Task 1, Task 2) |
| `tests/js/shim.js`, `tests/js/*.test.js` | Loads `pages.js` under Node and tests its functions (Task 2 onward) |

---

### Task 1: Tokens and fonts

**Files:**
- Create: `web/static/er-tokens.css`, `web/static/fonts/roboto.css`, `web/static/fonts/roboto-400.woff2`, `roboto-500.woff2`, `roboto-700.woff2`, `scripts/fetch_fonts.py`
- Modify: `web/app.py:60` (`ASSETS`), `web/templates/index.html:7-8` (links)
- Test: `tests/test_static_assets.py`

**Interfaces:**
- Produces: the CSS variables `--er-ui-*` from the design system (names exactly as in `tokens.css`, e.g. `--er-ui-text-primary-text`, `--er-ui-cta-primary`, `--er-ui-status-running`); the font family `Roboto` at weights 400, 500, 700; `ASSETS` keys `"er-tokens.css"`, `"fonts/roboto.css"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_static_assets.py
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "web" / "static"
RAW_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\b(?:white|black|red|blue|green|gray|grey)\b")


def test_the_tokens_file_is_the_design_systems():
    css = (STATIC / "er-tokens.css").read_text()
    assert css.startswith("/* Generated by scripts/emit-css.ts")   # verbatim copy, source noted below it
    assert "--er-ui-text-primary-text: #0a3235;" in css and '[data-theme="dark"]' in css


def test_the_app_stylesheet_has_no_raw_colour():
    css = (STATIC / "app.css").read_text()
    offenders = [l for l in css.splitlines() if RAW_COLOUR.search(l) and "/*" not in l]
    assert offenders == []


def test_fonts_are_self_hosted_with_a_fallback_and_optional_display():
    css = (STATIC / "fonts" / "roboto.css").read_text()
    for w in (400, 500, 700):
        assert f"font-weight: {w};" in css and f"roboto-{w}.woff2" in css and (STATIC / "fonts" / f"roboto-{w}.woff2").stat().st_size > 5000
    assert css.count("font-display: optional;") == 3
    app = (STATIC / "app.css").read_text()
    assert 'Roboto, system-ui, "Helvetica Neue", Arial, sans-serif' in app
    html = (ROOT / "web" / "templates" / "index.html").read_text()
    assert "fonts.googleapis.com/css2?family=Inter" not in html and "/static/fonts/roboto.css" in html and "/static/er-tokens.css" in html
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_static_assets.py -v`
Expected: FAIL, `er-tokens.css` not found.

- [ ] **Step 3: Copy the tokens file**

Copy `/Users/chrisdo/allenai/design/earthranger/tokens.css` to `web/static/er-tokens.css` unchanged, then append one comment at the end: the source path, the design system version from DESIGN.md's front matter (`0.0.1`) and the copy date.

- [ ] **Step 4: Write `scripts/fetch_fonts.py`**

`main() -> int`: fetches `https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap` with a current Chrome `User-Agent` (so the response names woff2 files), takes the `latin` block's `url(...)` for each weight, downloads each to `web/static/fonts/roboto-<weight>.woff2`, and writes `web/static/fonts/roboto.css` with three `@font-face` rules: `font-family: Roboto; font-style: normal; font-weight: <w>; font-display: optional; src: url(roboto-<w>.woff2) format("woff2"); unicode-range: <the latin range from the response>`. Run it once and commit the four files; the script is for refreshing them.

- [ ] **Step 5: Wire the assets**

In `web/app.py:60` extend `ASSETS` to `("app.css", "app.js", "er-tokens.css", "fonts/roboto.css")`. In `index.html` replace the Inter link with `<link rel="stylesheet" href="/static/er-tokens.css?v={{ assets['er-tokens.css'] }}">` and `<link rel="stylesheet" href="/static/fonts/roboto.css?v={{ assets['fonts/roboto.css'] }}">`, keeping the Material Symbols link. In `app.css` set `--sans: Roboto, system-ui, "Helvetica Neue", Arial, sans-serif` and `--mono: "Roboto Mono", ui-monospace, Menlo, monospace` on `:root` (the raw-colour test does not care about this task's colours yet; Task 4 replaces them).

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_static_assets.py -v`
Expected: the tokens and fonts tests PASS; `test_the_app_stylesheet_has_no_raw_colour` still FAILS (Task 4 makes it pass). Mark it `@pytest.mark.xfail(strict=True, reason="until Task 4")` for now.

- [ ] **Step 7: Commit**

```bash
git add web/static/er-tokens.css web/static/fonts scripts/fetch_fonts.py web/app.py web/templates/index.html web/static/app.css tests/test_static_assets.py
git commit -m "Design tokens and self-hosted Roboto"
```

---

### Task 2: Node test harness for the page builders

**Files:**
- Create: `web/static/pages.js` (empty shell), `tests/js/shim.js`, `tests/js/pages.test.js`
- Modify: `tests/test_static_assets.py` (runs the Node tests), `web/app.py:60` (`ASSETS` gains `"pages.js"`), `web/templates/index.html` (loads `pages.js` before `app.js`)

**Interfaces:**
- Produces: `tests/js/shim.js` exports `load()` which evaluates `web/static/pages.js` in a fresh VM context with only `esc`-free globals (no `document`, no `window`) and returns the context, so every `function name(...)` and top-level `const` in `pages.js` is reachable as a property; `pages.js` defines plain top-level functions and constants and never touches the DOM.

- [ ] **Step 1: Write the failing test**

```js
// tests/js/pages.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./shim');

test('pages.js loads with no DOM and exposes its functions', () => {
  const P = load();
  assert.equal(typeof P.esc, 'function');
  assert.equal(P.esc('<a & "b">'), '&lt;a &amp; &quot;b&quot;&gt;');
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test tests/js`
Expected: FAIL, cannot find `./shim`.

- [ ] **Step 3: Write `tests/js/shim.js`**

`load() -> object`: reads `web/static/pages.js`, runs it with `vm.runInNewContext` in a context `{ console }` only, and returns the context. A reference to `document` or `window` inside `pages.js` throws `ReferenceError` at call time, which is the guarantee.

- [ ] **Step 4: Create `web/static/pages.js`**

Move `esc` from `app.js:3` into `pages.js` (and delete it from `app.js`, which now relies on `pages.js` loading first). Add `pages.js` to `ASSETS` and to the template as `<script src="/static/pages.js?v={{ assets['pages.js'] }}"></script>` before `app.js`.

- [ ] **Step 5: Run the Node tests from pytest**

Add to `tests/test_static_assets.py`:

```python
import shutil, subprocess

def test_the_page_builders_pass_their_node_tests():
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    r = subprocess.run(["node", "--test", "tests/js"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
```

Run: `.venv/bin/python -m pytest tests/test_static_assets.py -v` and `node --check web/static/app.js web/static/pages.js`
Expected: PASS; both syntax checks pass.

- [ ] **Step 6: Commit**

```bash
git add web/static/pages.js web/static/app.js web/app.py web/templates/index.html tests/js tests/test_static_assets.py
git commit -m "pages.js and a Node harness for the page builders"
```

---

### Task 3: The router

**Files:**
- Modify: `web/static/pages.js`, `web/static/app.js:30-38` (popstate), `app.js:296-328` (`showDatasets`, `showLoad`)
- Test: `tests/js/router.test.js`

**Interfaces:**
- Produces, in `pages.js`: `parseRoute(hash: string) -> {page: 'home'|'dataset'|'load'|'sites'|'legacy-load', id?: string, tab?: 'overview'|'loads'|'rangers', load?: string}`; `routeHash(route) -> string` (its inverse; `page:'home'` → `#/`). In `app.js`: `navigate(route, nav = 'push')` which writes history (`push`/`replace`/`none`) and calls `renderRoute(route)`; `renderRoute(route)` dispatches to one `show*` function per page (defined in Tasks 5–8; until then it logs). The `fromList` convention from PR 30 becomes `history.state.from`, the previous route's hash, so a page's Back button can `history.back()` when the previous entry is its parent and `navigate(parent)` otherwise.

- [ ] **Step 1: Write the failing tests**

```js
// tests/js/router.test.js
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
test('parseRoute maps every route and tolerates junk', () => {
  assert.deepEqual(P.parseRoute(''), { page: 'home' });
  assert.deepEqual(P.parseRoute('#/'), { page: 'home' });
  assert.deepEqual(P.parseRoute('#/datasets/abc123'), { page: 'dataset', id: 'abc123', tab: 'overview' });
  assert.deepEqual(P.parseRoute('#/datasets/abc123/loads'), { page: 'dataset', id: 'abc123', tab: 'loads' });
  assert.deepEqual(P.parseRoute('#/datasets/abc123/rangers'), { page: 'dataset', id: 'abc123', tab: 'rangers' });
  assert.deepEqual(P.parseRoute('#/datasets/abc123/loads/ld9'), { page: 'load', id: 'abc123', load: 'ld9' });
  assert.deepEqual(P.parseRoute('#/sites'), { page: 'sites' });
  assert.deepEqual(P.parseRoute('#load/ld9'), { page: 'legacy-load', load: 'ld9' });
  assert.deepEqual(P.parseRoute('#/nonsense/x'), { page: 'home' });
  assert.deepEqual(P.parseRoute('#/datasets/<script>'), { page: 'home' });   // ids are [A-Za-z0-9]+
});
test('routeHash inverts parseRoute', () => {
  for (const h of ['#/', '#/datasets/abc123', '#/datasets/abc123/loads', '#/datasets/abc123/rangers', '#/datasets/abc123/loads/ld9', '#/sites'])
    assert.equal(P.routeHash(P.parseRoute(h)), h);
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `node --test tests/js`
Expected: FAIL, `parseRoute is not a function`.

- [ ] **Step 3: Implement `parseRoute` and `routeHash` in `pages.js`**

Ids match `/^[A-Za-z0-9]+$/`; anything else is `home`.

- [ ] **Step 4: Implement `navigate` and `renderRoute` in `app.js`**

Replace the `popstate` handler so it calls `renderRoute(parseRoute(location.hash))` (a null state is fine: the hash is the truth). `showApp()` calls `navigate(parseRoute(location.hash), 'replace')`. A `legacy-load` route fetches `GET /api/loads/<load>` for its `dataset_id` and navigates to the load route with `'replace'`; a 404 navigates home with `'replace'`. Keep `showLoad`/`showDatasets` working by making them call `navigate` (Task 7 replaces them).

- [ ] **Step 5: Run the tests and the syntax checks**

Run: `node --test tests/js && node --check web/static/app.js && node --check web/static/pages.js && .venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/static/pages.js web/static/app.js tests/js/router.test.js
git commit -m "A hash router with the old load links redirected"
```

---

### Task 4: The shell: header, theme, frame, controls, sign-in

**Files:**
- Create: `web/static/img/er-lockup-white-h-short.svg` (copy of `.../assets/EarthRanger-Logo-2026_Ai2-white-H-short.svg`), `web/static/img/er-lockup-h.svg` (copy of `EarthRanger-Logo-2026_Ai2-H.svg`)
- Modify: `web/templates/index.html` (whole body), `web/static/app.css` (rewritten on tokens), `web/static/app.js` (`boot`, `showSignIn`, `showApp`, theme, account menu), `web/static/pages.js` (`statusClass`, `pill`, `renderBreadcrumb`, `renderSignIn`)
- Test: `tests/js/shell.test.js`, `tests/test_static_assets.py` (drop the xfail)

**Interfaces:**
- Produces in `pages.js`: `statusClass(status: string) -> 'running'|'success'|'warning'|'error'|'ready'|'pending'|'interrupted'` (the spec §8 table; unknown → `pending`); `pill(status, label?) -> html` rendering `<span class="pill st-<class>">label</span>` with the label defaulting to the status with underscores as spaces; `renderBreadcrumb(parts: {label, hash?}[]) -> html` (last part is text, others links); `renderSignIn({allowed}) -> html`.
- Produces in `app.js`: `setTheme(choice: 'system'|'light'|'dark')` writing `document.documentElement.dataset.theme` (removed for system) and `localStorage.theme`; `mountHeader(signedIn: boolean)`; `mountPage(html)` writing `#page`; `setBreadcrumb(parts)`.
- Produces in the template: `<header>` with `#home` (lockup link), `#appName`, `#version`, `#helpBtn`, `#account` (menu trigger showing `#whoEmail`) and `#accountMenu` (items: `#menuSites`, theme radios `name="theme"`, `#signOut`); `<div id="crumbs">`; `<main id="page" class="wrap">`; the existing `#modal` and help drawer.
- CSS classes: `.btn` (`.primary`, `.secondary`, `.danger`, `.ghost`), `.panel`, `.pill.st-*`, `.tabs`, `.card`, `.field`, `.crumbs`, `.title-block`, `.actions`, `.empty`.

- [ ] **Step 1: Write the failing tests**

```js
// tests/js/shell.test.js
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
test('every status maps to a token class', () => {
  const m = { running: 'running', continuing: 'running', queued: 'pending', planning: 'pending', uploading: 'pending', planned: 'ready',
              needs_attention: 'warning', done: 'success', ready: 'success', failed: 'error', interrupted: 'interrupted', whatever: 'pending' };
  for (const [s, c] of Object.entries(m)) assert.equal(P.statusClass(s), c, s);
  assert.equal(P.pill('needs_attention'), '<span class="pill st-warning">needs attention</span>');
  assert.equal(P.pill('done', 'Done'), '<span class="pill st-success">Done</span>');
});
test('breadcrumb links all but the last part and escapes', () => {
  const h = P.renderBreadcrumb([{ label: 'Datasets', hash: '#/' }, { label: 'R5 <Lawin>', hash: '#/datasets/a1' }, { label: 'Load' }]);
  assert.match(h, /<a href="#\/">Datasets<\/a>/); assert.match(h, /R5 &lt;Lawin&gt;/); assert.doesNotMatch(h, /<a[^>]*>Load</);
});
test('sign-in names the product and the allowed domain', () => {
  const h = P.renderSignIn({ allowed: '@earthranger.com' });
  assert.match(h, /SMART migration/); assert.match(h, /@earthranger\.com/); assert.match(h, /id="signInBtn"/); assert.match(h, /er-lockup-h\.svg/);
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `node --test tests/js`
Expected: FAIL on `statusClass`.

- [ ] **Step 3: Implement the four builders in `pages.js`**

The sign-in copy, verbatim from the spec: heading "SMART migration"; sentence "Upload a SMART conservation-area backup, browse it, and load it into an EarthRanger site."; the hint "Sign in with your <allowed> Google account."; button "Sign in with Google" with the `login` icon; an empty `<p id="signInError" class="tiny">`.

- [ ] **Step 4: Rewrite the template body**

Header: `<a id="home" href="#/"><img src="/static/img/er-lockup-white-h-short.svg" alt="EarthRanger"></a><span id="appName">SMART migration</span><span id="version" class="tiny">{{ version }}</span>`, then at the right `<button id="helpBtn" class="btn ghost">` and `<details id="account"><summary id="whoEmail"></summary><div id="accountMenu">…</div></details>` with the items named in Interfaces (theme as three radio inputs labelled System, Light, Dark). `<div id="crumbs" class="crumbs" hidden></div>`, `<main id="page" class="wrap"></main>`, then the help drawer and `#modal` as they are. `<title>` stays `smart-able`. Remove every old panel: upload, sites, datasets, `#loadPage`, `#signIn`.

- [ ] **Step 5: Rewrite `app.css` on the tokens**

Every colour a `var(--er-...)`: body on `--er-ui-background-secondary-background` with `--er-ui-text-primary-text`; header on `--er-ui-cta-secondary` with `--er-ui-text-primary-text-reversed`, 48px; `.panel` on `--er-ui-background-elevated-component` with `1px solid var(--er-ui-divider-lines)` and 10px radius; `th` on `--er-ui-background-elevated-component-0`; `.btn.primary` fill `--er-ui-cta-primary` text `--er-ui-cta-text`; `.btn.secondary` border `--er-ui-field-outline` text `--er-ui-cta-secondary`; `.btn.danger` text `--er-ui-status-error-destructive`; inputs border `--er-ui-field-outline`, labels `--er-ui-text-form-labels`; links `--er-ui-cta-primary`; `:focus-visible` a 2px ring in `--er-ui-cta-primary`; `.pill.st-*` per the status table; `.tabs` with the active tab's underline in `--er-ui-cta-primary`; `.mi` in `--er-ui-icons`. Type: body `14px/21px var(--sans)`, `h1` 24px/500, `h2` 20px/500, `h3` 16px/500, `.btn` 14px/600. Keep the help drawer, dialog, stage table, findings, plan, rangers and progress rules, translated to tokens. The wrap: `max-width: 1100px; margin: 0 auto; padding: 16px`.

- [ ] **Step 6: Wire `boot`, theme and the menu in `app.js`**

`boot()` applies `setTheme(localStorage.theme || 'system')` before the first fetch, binds the theme radios, `#menuSites` → `navigate({page:'sites'})`, `#signOut` as before, `#helpBtn` as before. `showSignIn()` mounts `renderSignIn(CONFIG)` into `#page` with the header's Help and account hidden; `showApp()` shows them and navigates. Delete the old `#uploadForm`, `#siteForm`, `#loadBack` bindings (their pages come in Tasks 5–8).

- [ ] **Step 7: Run everything**

Run: `node --test tests/js && node --check web/static/app.js web/static/pages.js && .venv/bin/python -m pytest -q` (remove the xfail from `test_the_app_stylesheet_has_no_raw_colour` first)
Expected: PASS, including the no-raw-colour test.

- [ ] **Step 8: Commit**

```bash
git add web/static/img web/static/app.css web/static/app.js web/static/pages.js web/templates/index.html tests/js/shell.test.js tests/test_static_assets.py
git commit -m "The shell: EarthRanger header, tokens, theme, sign-in"
```

---

### Task 5: The dataset list and the upload dialog

**Files:**
- Modify: `web/static/pages.js` (`renderHome`, `renderDatasetCard`), `web/static/app.js` (`showHome`, `uploadDialog`, polling)
- Test: `tests/js/home.test.js`

**Interfaces:**
- Consumes: `GET /api/datasets` items as today (`id, name, source_name, source_size, created_at, status, error, cas[{id,n}], db_version, counts{patrols,waypoints}, owner_email, mine, shared_with, export, extract_held`).
- Produces in `pages.js`: `renderDatasetCard(d) -> html` (`<a class="card" href="#/datasets/<id>">` with lines 1–2 and the right column per spec §2); `renderHome(datasets) -> html` (the "Upload a backup or export" primary button `#uploadBtn`, the cards newest first by `created_at`, or the empty state "No datasets yet. Upload a backup or export to begin.").
- Produces in `app.js`: `showHome()` (fetch, mount, bind `#uploadBtn`, poll every 5 s while any dataset is `queued`/`running`, re-rendering cards in place by replacing `#page`'s card list only); `uploadDialog()` (the existing upload flow inside the modal: name, file, progress bar; on success close and `showHome()`; the XHR keeps running if the dialog is closed).

- [ ] **Step 1: Write the failing tests**

```js
// tests/js/home.test.js
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
const d = { id: 'a1', name: 'R5 <Lawin>', source_name: 'r5.zip', source_size: 2900000000, created_at: '2026-10-07T00:00:00+00:00', status: 'ready',
            cas: [{ id: '050500', n: 'Albay' }, { id: '050504', n: 'Guinobatan' }], db_version: '7.5.6', counts: { patrols: 2570, waypoints: 30791 }, mine: true, shared_with: ['x@earthranger.com'] };
test('a dataset card links to its page and shows status, areas, counts, owner', () => {
  const h = P.renderDatasetCard(d);
  assert.match(h, /href="#\/datasets\/a1"/); assert.match(h, /R5 &lt;Lawin&gt;/); assert.match(h, /2\.9 GB/);
  assert.match(h, /st-success/); assert.match(h, /Albay/); assert.match(h, /050504/); assert.match(h, /2,570 patrols/); assert.match(h, /you/); assert.match(h, /shared/);
});
test('a failed extraction shows its error on the card', () => {
  assert.match(P.renderDatasetCard({ ...d, status: 'failed', error: 'zip is not a SMART backup' }), /st-error[\s\S]*zip is not a SMART backup/);
});
test('home orders newest first and has an empty state', () => {
  const h = P.renderHome([{ ...d, id: 'old', created_at: '2026-01-01T00:00:00+00:00' }, { ...d, id: 'new', created_at: '2026-11-01T00:00:00+00:00' }]);
  assert.ok(h.indexOf('#/datasets/new') < h.indexOf('#/datasets/old'));
  assert.match(P.renderHome([]), /No datasets yet\. Upload a backup or export to begin\./);
  assert.match(h, /id="uploadBtn"/);
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `node --test tests/js` → FAIL on `renderDatasetCard`.

- [ ] **Step 3: Implement the two builders in `pages.js`**

`fmtBytes` moves from `app.js:4` to `pages.js`. Counts use `toLocaleString('en-US')`.

- [ ] **Step 4: Implement `showHome` and `uploadDialog` in `app.js`**

`renderRoute` dispatches `home` → `showHome`. Delete `loadList`, `loadsCell`, `loadScope`, `action` and `upload` from `app.js` (their parts move to the dataset page in Task 6 and the dialog here). Polling uses the existing `listGen` guard: a response for a superseded render is dropped.

- [ ] **Step 5: Run everything**

Run: `node --test tests/js && node --check web/static/app.js web/static/pages.js && .venv/bin/python -m pytest -q` → PASS.

- [ ] **Step 6: Commit**

```bash
git add web/static/pages.js web/static/app.js tests/js/home.test.js
git commit -m "Home: dataset cards and the upload dialog"
```

---

### Task 6: The dataset page

**Files:**
- Modify: `web/static/pages.js` (`renderDatasetPage`, `renderOverview`, `renderLoadsTab`, `renderRangersTab`, `renderNotFound`), `web/static/app.js` (`showDataset`, the share dialog and dataset actions moved here, the load dialog opened with a preselected area)
- Test: `tests/js/dataset.test.js`

**Interfaces:**
- Consumes: `GET /api/datasets/<id>` (one dataset, with `log_tail`, `started_at`, `finished_at` as the API gives them), `GET /api/datasets/<id>/loads` (list items: `id, ca_id, status, held, progress, site{name,url}, created_at, owner_email, options`), `GET /api/loads/<id>` for the rangers tab's source load (`rangers`, `rangers_total`, `options.scope`, `stages`).
- Produces in `pages.js`: `renderDatasetPage(d, tab, extra) -> html` where `extra` is `{loads}` for the loads tab and `{load}` for the rangers tab; the title block (name, source file and size, uploaded date, owner, shared-with) and the `.actions` (`#shareBtn`, `#extractBtn`, `#deleteBtn`, rendered only when `d.mine`; all `disabled` while `extract_held`); the `.tabs` with hrefs `#/datasets/<id>`, `/loads`, `/rangers` (loads and rangers tabs carry `aria-disabled="true"` unless `d.status === 'ready'`); `renderOverview(d)` (status pill, times, collapsible `log_tail` open while running, one row per `d.export` entry with Browse `href="/d/<id>/#<ca dir>"`-style link to the viewer and `data-act="load" data-ca="<dir>"` when `entry.patrols`, else the "re-extract to enable loading" note); `renderLoadsTab(d, loads)` (rows per spec §3, `data-load` on each, `#loadBtn` when any area has a bundle, empty state "No loads yet."); `renderRangersTab(load)` (reuses `renderRangersSection(load)` from Task 7's interface, with a line "From the load of <area> into <site>, <date>"; empty state per spec §1); `renderNotFound() -> html` ("Not found or not shared with you" with a link to `#/`).
- Produces in `app.js`: `showDataset(route)` (fetches the dataset; a 404 mounts `renderNotFound()` and replaces the entry; fetches what the tab needs; binds actions; polls every 5 s while extracting); `loadDialog(d, caId?)` is the existing dialog with `#ldCa` preselected.

- [ ] **Step 1: Write the failing tests**

```js
// tests/js/dataset.test.js
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
const d = { id: 'a1', name: 'R5 Lawin', source_name: 'r5.zip', source_size: 1000, created_at: '2026-10-07T00:00:00+00:00', status: 'ready', mine: true, shared_with: [],
            export: [{ dir: 'ALPHA', ca_id: '050500', name: 'Albay', patrols: 1527, waypoints: 30000 }, { dir: 'BETA', ca_id: '050504', name: 'Guinobatan', patrols: 0 }],
            counts: { patrols: 1527, waypoints: 30000 }, log_tail: 'done' };
test('overview lists areas with Browse and a Load button only where there is a bundle', () => {
  const h = P.renderDatasetPage(d, 'overview', {});
  assert.match(h, /href="\/d\/a1\/"/); assert.match(h, /data-act="load" data-ca="ALPHA"/); assert.doesNotMatch(h, /data-act="load" data-ca="BETA"/);
  assert.match(h, /re-extract to enable loading/); assert.match(h, /id="shareBtn"/); assert.match(h, /id="deleteBtn"/);
});
test('a dataset still extracting disables the actions and the other tabs', () => {
  const h = P.renderDatasetPage({ ...d, status: 'running', extract_held: true, export: [] }, 'overview', {});
  assert.match(h, /id="deleteBtn"[^>]*disabled/); assert.match(h, /href="#\/datasets\/a1\/loads"[^>]*aria-disabled="true"/); assert.match(h, /<details open/);
});
test('a failed extraction still opens, with its error', () => {
  assert.match(P.renderDatasetPage({ ...d, status: 'failed', error: 'boom', export: [] }, 'overview', {}), /st-error[\s\S]*boom/);
});
test('the loads tab lists loads newest first with an empty state', () => {
  const loads = [{ id: 'l1', ca_id: 'ALPHA', status: 'done', site: { name: 'phinney', url: 'p.pamdas.org' }, created_at: '2026-11-01T00:00:00+00:00', progress: { done: 10, patrols_total: 10 } },
                 { id: 'l2', ca_id: 'ALPHA', status: 'running', site: { name: 'phinney', url: 'p.pamdas.org' }, created_at: '2026-11-02T00:00:00+00:00', progress: { done: 3, patrols_total: 10 } }];
  const h = P.renderDatasetPage(d, 'loads', { loads });
  assert.ok(h.indexOf('data-load="l2"') < h.indexOf('data-load="l1"')); assert.match(h, /3 of 10 patrols/); assert.match(h, /id="loadBtn"/);
  assert.match(P.renderDatasetPage(d, 'loads', { loads: [] }), /No loads yet\./);
});
test('not found names the problem and links home', () => { assert.match(P.renderNotFound(), /Not found or not shared with you[\s\S]*href="#\/"/); });
```

- [ ] **Step 2: Run to verify they fail** → `node --test tests/js` FAILS on `renderDatasetPage`.

- [ ] **Step 3: Implement the builders in `pages.js`**

The viewer link for an area is `/d/<dataset id>/` (the viewer's own selector picks the area; pass `#overview` only).

- [ ] **Step 4: Implement `showDataset` and move the dataset actions in `app.js`**

`shareDialog` is reused as is. Delete is the existing confirm with the spec's wording; on success `navigate({page:'home'}, 'replace')`. Re-extract as today, then re-fetch. `renderRoute` dispatches `dataset` → `showDataset`.

- [ ] **Step 5: Run everything** → `node --test tests/js && node --check web/static/app.js web/static/pages.js && .venv/bin/python -m pytest -q` PASS.

- [ ] **Step 6: Commit**

```bash
git add web/static/pages.js web/static/app.js tests/js/dataset.test.js
git commit -m "The dataset page: overview, loads and rangers tabs"
```

---

### Task 7: The load page in the frame

**Files:**
- Modify: `web/static/pages.js` (move `stageRows`, `stageSummary`, `importSummary`, `renderStages`, `renderPlan`, the findings builder and the rangers section out of `app.js`; add `renderLoadTitle`, `renderLoadPage`), `web/static/app.js` (`showLoad` rewritten over the builders; polling, open-state and scroll preservation, rangers memo, copy and help buttons kept)
- Test: `tests/js/loadpage.test.js`

**Interfaces:**
- Consumes: `GET /api/loads/<id>` as today.
- Produces in `pages.js`: `renderLoadTitle(l) -> html` (heading "<ca_id> → <site name>" with `pill(l.status)` and the statuses "?" button `data-help="help-statuses"`; the small line: host, event category, language, window, configurable model, started by and when; `.actions` with the buttons the current `renderLoad` computes, same ids/data attributes `data-run`, `data-replan`, `data-del`, and the same notes); `renderFindings(findings) -> html` (today's markup, with the copy buttons and `data-help="finding-<code>"`); `renderRangersSection(l) -> html` (today's `renderRangers` without the DOM memo: the table, the CSV button `data-csv`, the help button); `renderProgress(l, active) -> html`; `renderLoadPage(l, active) -> html` composing: stages (`renderStages`), findings, plan, rangers, progress, log. `Date.now` is read through a module-level `now()` so tests can pin time.
- Produces in `app.js`: `showLoad(route)` (fetch; 404 → `renderNotFound` with replace; mount; bind; the rangers memo compares `l.id + rangers_total + JSON.stringify(rangers)` and replaces only that section; open-state and scroll preservation as today; poll every 4 s while `l.held`).

- [ ] **Step 1: Write the failing tests**

```js
// tests/js/loadpage.test.js
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
const base = { id: 'ld1', ca_id: '050500', status: 'planned', held: false, site: { name: 'phinney', url: 'p.pamdas.org' }, options: { language: 'en', event_category: 'lawin050500', scope: 'all' },
               owner_email: 'ops@earthranger.com', created_at: '2026-11-13T10:00:00+00:00', mode: 'plan', stages: {}, findings: [], plan: null, rangers: [], progress: null };
test('the title block shows status, options, and the right actions', () => {
  const h = P.renderLoadTitle({ ...base, findings: [{ code: 'team', severity: 'blocking', stage: 'patrol_datamodel', title: 't' }] });
  assert.match(h, /050500 → phinney/); assert.match(h, /st-ready/); assert.match(h, /lawin050500/); assert.match(h, /data-run[^>]*>[^<]*Confirm and load \(stops at 1 blocking\)/);
  assert.match(h, /data-replan/); assert.match(h, /data-del/); assert.match(h, /data-help="help-statuses"/);
  assert.doesNotMatch(P.renderLoadTitle({ ...base, status: 'running', held: true }), /data-run|data-del/);
  assert.match(P.renderLoadTitle({ ...base, status: 'needs_attention' }), /Continue/);
});
test('the rangers section renders for a plan and for a data-model-only load', () => {
  const rows = [{ name: 'Ana Cruz', smart_employee_id: 'E1', smart_member_id: 'm1', active: true, patrols: 0, patrols_total: 2, deleted: false, subject_id: null }];
  const plan = P.renderRangersSection({ ...base, rangers: rows, rangers_total: 1 });
  assert.match(plan, /Ana Cruz/); assert.match(plan, /not created yet/); assert.match(plan, /0 <span class="tiny">\/ 2<\/span>/);
  const dm = P.renderRangersSection({ ...base, options: { scope: 'datamodel' }, rangers: rows, rangers_total: 1 });
  assert.match(dm, /Patrols \(all\)/); assert.doesNotMatch(dm, /this load/);
});
test('the page composes its sections in order', () => {
  const h = P.renderLoadPage({ ...base, status: 'done', log_tail: 'load ld1: done', progress: { done: 2, patrols_total: 2, failed: 0, skipped: 0 },
    stages: { import: { status: 'done', started_at: '2026-11-13T10:00:00+00:00', finished_at: '2026-11-13T10:05:00+00:00', metrics: { imported: 2, failed: 0, skipped: 0, events_written: 9, events_reported_by: 9, events_reported_by_backfilled: 0 } } },
    findings: [{ code: 'patrol_type_icons', severity: 'warning', stage: 'patrol_datamodel', title: 'Pick icons', fix: 'x', values: [] }],
    rangers: [{ name: 'Ana Cruz', patrols: 2, patrols_total: 2 }], rangers_total: 1 }, false);
  const i = s => h.indexOf(s);
  assert.ok(i('class="stagetable"') < i('Findings') && i('Findings') < i('Rangers') && i('Rangers') < i('Progress') && i('Progress') < i('load ld1: done'));
  assert.match(h, /this execution wrote 9 events; 9 of the events it handled report who made them/);
});
```

- [ ] **Step 2: Run to verify they fail** → FAIL on `renderLoadTitle`.

- [ ] **Step 3: Move the builders and add the new ones in `pages.js`**

The moved functions keep their behaviour and tests from the existing code paths; only `renderRangers` loses its DOM memo (which moves to `showLoad`). `importSummary`'s `Date.now()` becomes `now()`.

- [ ] **Step 4: Rewrite `showLoad` in `app.js`**

`renderRoute` dispatches `load` → `showLoad`. Breadcrumb: Datasets › dataset name (fetched once per load page from `GET /api/datasets/<id>`) › "<ca_id> → <site>". The Back behaviour from PR 30 (`from` in history state) decides whether the breadcrumb's dataset link is `history.back()` or `navigate`. A poll that fails keeps the last render and retries on the next tick; after two consecutive failures a `.tiny` line "Could not refresh; retrying…" appears under the title block and disappears on the next success (the same rule applies to the home and dataset pages' polls).

- [ ] **Step 5: Run everything** → PASS.

- [ ] **Step 6: Commit**

```bash
git add web/static/pages.js web/static/app.js tests/js/loadpage.test.js
git commit -m "The load page in the new frame"
```

---

### Task 8: Sites

**Files:**
- Modify: `web/static/pages.js` (`renderSites`), `web/static/app.js` (`showSites`, `siteDialog`, the load dialog's "Add a site…" entry)
- Test: `tests/js/sites.test.js`

**Interfaces:**
- Consumes: `GET /api/sites` items (`id, name, url, token_hint, checked_as, mine, owner_email, shared_with`), `POST /api/sites`, `DELETE /api/sites/<id>`, the share endpoints.
- Produces in `pages.js`: `renderSites(sites) -> html` (`#addSiteBtn`, rows per spec §5 with `data-act="siteShare"` and `data-act="siteDelete"` for the owner, empty state "No sites yet. Add the EarthRanger site you will load into.").
- Produces in `app.js`: `showSites()`; `siteDialog(onCreated?)` (the modal with name, host, token; submit calls `POST /api/sites`; a 4xx shows its detail in the dialog; on success closes, re-renders the list, and calls `onCreated(site)` if given); the load dialog's `#ldSite` gains a last option `value="__add__"` "Add a site…" which opens `siteDialog` and, on return, repopulates the picker with the new site selected.

- [ ] **Step 1: Write the failing test**

```js
// tests/js/sites.test.js
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
test('sites list rows, owner actions, and the empty state', () => {
  const h = P.renderSites([{ id: 's1', name: 'phinney', url: 'p.pamdas.org', token_hint: 'dbe5', checked_as: 'smart_migration', mine: true, shared_with: [] },
                           { id: 's2', name: 'other', url: 'o.pamdas.org', token_hint: 'aaaa', checked_as: 'x', mine: false, owner_email: 'a@earthranger.com', shared_with: ['me@earthranger.com'] }]);
  assert.match(h, /id="addSiteBtn"/); assert.match(h, /…dbe5 as smart_migration/);
  assert.match(h, /data-act="siteDelete" data-id="s1"/); assert.doesNotMatch(h, /data-act="siteDelete" data-id="s2"/); assert.match(h, /a@earthranger\.com/);
  assert.match(P.renderSites([]), /No sites yet\. Add the EarthRanger site you will load into\./);
});
```

- [ ] **Step 2: Run to verify it fails** → FAIL on `renderSites`.

- [ ] **Step 3: Implement `renderSites`; implement `showSites`, `siteDialog` and the picker entry in `app.js`**

Remove confirms with: "Loads that reference this site stay readable but cannot be continued; register the site again to load into it." Delete the old `loadSites`, `siteAction`, `addSite`. `renderRoute` dispatches `sites` → `showSites`.

- [ ] **Step 4: Run everything** → PASS.

- [ ] **Step 5: Commit**

```bash
git add web/static/pages.js web/static/app.js tests/js/sites.test.js
git commit -m "Sites page and the add-site dialog"
```

---

### Task 9: The viewer's header, tokens, fonts and theme

**Files:**
- Modify: `browse/index.html` (the `:root` token blocks at lines 12–47, the header at 265–274, the `#home` link logic, fonts link), `browse/build_quirks.py:96-103` (`app_theme` finds the new brand mark)
- Test: `tests/test_browser_data.py` or a new `tests/test_viewer_page.py`

**Interfaces:**
- Produces: the viewer's `:root` block defines the same `--er-ui-*` variables as `er-tokens.css` for light, `prefers-color-scheme: dark` and `[data-theme]`, with a comment `/* from web/static/er-tokens.css (design system 0.0.1): keep the two in step */`, and maps its existing `--bg`, `--surface`, `--ink`, `--brand` ... to them so no rule below changes; the header carries `<img class="lockup" src="/static/img/er-lockup-white-h-short.svg" alt="EarthRanger">` with an inline SVG fallback for standalone use (the file is not reachable from `file://`), "SMART migration" as the `h1`, the dataset name, tabs and selector as now, and `#home` relabelled "Back to dataset" with `href="/#/datasets/<id>"` when `location.pathname` matches `^/d/([A-Za-z0-9]+)/`; fonts `<link rel="stylesheet" href="/static/fonts/roboto.css">` only when served under `/d/` (added by script after the path check), the Google Fonts Roboto link removed; on load, `localStorage.theme` (wrapped in try/catch) sets `data-theme`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_viewer_page.py
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def test_the_viewer_shares_the_apps_tokens_header_and_theme_key():
    html = (ROOT / "browse" / "index.html").read_text()
    tokens = (ROOT / "web" / "static" / "er-tokens.css").read_text()
    for name in ("--er-ui-text-primary-text", "--er-ui-cta-primary", "--er-ui-background-secondary-background", "--er-ui-status-running"):
        light = re.search(name + r": (#[0-9a-f]{6});", tokens).group(1)
        assert f"{name}: {light};" in html, name
    assert "keep the two in step" in html
    assert "SMART migration" in html and "fonts.googleapis.com/css2?family=Roboto" not in html
    assert "localStorage.getItem('theme')" in html and "Back to dataset" in html
    assert "<svg class=\"acorn\"" not in html
```

- [ ] **Step 2: Run to verify it fails** → `.venv/bin/python -m pytest tests/test_viewer_page.py -v` FAILS.

- [ ] **Step 3: Make the changes in `browse/index.html`**

Keep the viewer self-contained: no reference to `er-tokens.css` at runtime, only its values. The quirks builder reads the token block by regex (`build_quirks.app_theme`): update its two regexes to the new block boundaries and to the lockup `<img class="lockup"...>` (or the inline fallback SVG) in place of the acorn, and keep the quirks page's header consistent.

- [ ] **Step 4: Run the viewer checks**

Run: `.venv/bin/python -m pytest tests/test_viewer_page.py tests/test_browser_data.py tests/test_quirks.py -q`, then `.venv/bin/python browse/build_quirks.py docs/smart-data-quirks.md /tmp/quirks-check.html`, then the viewer script through `node --check` (extract the inline script as the earlier checks did).
Expected: PASS; the quirks page builds.

- [ ] **Step 5: Commit**

```bash
git add browse/index.html browse/build_quirks.py tests/test_viewer_page.py
git commit -m "Viewer: the EarthRanger header, shared tokens, theme and fonts"
```

---

### Task 10: Docs, cleanup and the manual pass

**Files:**
- Modify: `README.md` (web service section: the pages, the routes, where tokens and fonts live, `scripts/fetch_fonts.py`), `web/DEPLOY.md` (static assets, the design repository as the token source), `docs/superpowers/specs/2026-10-21-hosted-load-design.md` (the UI section now points at the refresh spec), `web/help/01-overview.md` and `03-loading.md` (wording that names "the dataset card", "the load page's Rangers section" updated to the dataset page and its tabs)
- Delete: nothing in `app.js` should remain of `loadList`, `loadsCell`, `loadScope`, `action`, `upload`, `loadSites`, `siteAction`, `addSite`, `showDatasets`, the old `renderLoad` body; the test `tests/test_help.py` keeps passing (help anchors unchanged).

- [ ] **Step 1: Grep for leftovers**

Run: `grep -n "loadList\|loadsCell\|showDatasets\|siteForm\|uploadForm\|#loadPage\|Inter" web/static/app.js web/templates/index.html web/static/app.css`
Expected: no matches.

- [ ] **Step 2: Update the documents named above**

- [ ] **Step 3: Full verification**

Run: `node --test tests/js && node --check web/static/app.js web/static/pages.js && .venv/bin/python -m pytest -q`
Expected: all PASS.

- [ ] **Step 4: Manual pass on a local run**

Run the service locally (`BACKEND=local AUTH_DISABLED=true`, per DEPLOY.md) against an extracted dataset and walk: sign-in page; home with a card; upload dialog; the dataset's three tabs; Browse into the viewer and Back to dataset; a load page (plan one against a fake or staging site); sites; theme System/Light/Dark on both pages; phone width. Record anything found as a fix commit.

- [ ] **Step 5: Commit**

```bash
git add README.md web/DEPLOY.md docs web/help
git commit -m "Docs for the refreshed UI"
```
