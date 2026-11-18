# Language support, part 2: the app's screens and messages. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the hosted app's screens, its server error messages and its help drawer in English, French, Spanish, Portuguese and Swahili, chosen by the reader.

**Architecture:** Every phrase the app shows moves out of `pages.js`, `app.js` and `index.html` into one message file per language, read through a small `i18n.js` that Node can test. The server keeps its English error text and adds a stable code the client translates. The help drawer serves the translated help pages part 1 wrote. Nothing stored changes.

**Tech Stack:** Plain browser JavaScript (no new library), FastAPI, pytest, `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-17-language-support-design.md` ("Shared rules" and "Part 2: the app's screens and messages"). Part 1 (the docs site) is PR 37; this branch is built on it. Part 3 (findings) has its own plan later.

## Global Constraints

- Languages, in order: `en`, `fr`, `es`, `pt`, `sw`, from `web/static/locales/languages.json` (part 1). English is the source and the fallback.
- Message files: `web/static/locales/<code>.json`, nested keys, `{{name}}` placeholders, `_one` / `_other` plural suffixes (the shape EarthRanger's web app uses).
- A message holds text only, never HTML. Every message and every value is escaped where it goes into the page.
- A key missing in the chosen language shows the English message. A key missing in English fails a test.
- Nothing stored or returned by the API changes meaning: a server error keeps its English `detail`; `code` and `values` are added beside it.
- Stays English, by the spec: the dataset browser, the live log, the quirks reference, and (until part 3) findings' titles, details and fixes. Text a job stored on a dataset or a load (`error`, `log_tail`) stays as stored.
- Never translated: file names, hosts, code, status values in the API, names from a site's data.
- Terms follow `docs/translation-glossary.md`.
- Security rules unchanged: the site token is never written to a log, an API response, rendered HTML or a message; the 422 handler still drops submitted values.
- With `AUTH_DISABLED` the service listens on localhost only. Port 8080 is taken on this machine; use another.
- Tests: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q` and `node --test "tests/js/*.test.js"`. Both pass at the end of every task. Existing tests that assert English words keep asserting them, for English.
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Do not push; do not open a PR.

## Review Focus

1. **A phrase left in the code.** A reader in Swahili meets an English button. Expected: every builder's output is free of English under a stand-in language. Test in Task 4 (`pseudo`), and the browser walk in Task 10 for `app.js`.
2. **A message or a value with markup in it** (a dataset named `<img onerror=…>`, a translation containing `<b>`). Expected: shown as text. Tests in Task 1 and Task 4.
3. **A count the language pluralises differently** (0 and 1 in French take the singular; large numbers group differently). Expected: the language's own form and digit grouping. Test in Task 1.
4. **A server error the client has no message for** (a new code, an old server, a 422 list). Expected: the server's English text, or a plain "the request was not valid", never `[object Object]` or a key name. Test in Task 6.
5. **Switching language with a page open** (a dialog open, a load page polling, the help drawer loaded in the old language). Expected: the page re-renders in the new language, the help drawer reloads, nothing is submitted twice. Task 2, checked in the browser in Task 10.

## File Structure

| File | Responsibility |
|---|---|
| `web/static/i18n.js` | `T`, `t`, `tn`, `fmtNum`, `pickLang`, `setMessages`, `setLang`: pure, Node-testable. |
| `web/static/locales/en.json` | Every phrase of the app, in English. |
| `web/static/locales/{fr,es,pt,sw}.json` | The translations. |
| `web/static/pages.js` | Builders; every phrase through `T` / `tn`. |
| `web/static/app.js` | Wiring: loads messages, the language choice, dialogs, the help drawer. |
| `web/templates/index.html` | Shell with `data-i18n` marks, the language menu, the note. |
| `web/app.py`, `web/auth.py` | `ApiError` with a code; `/api/help?lang=`; the template's languages. |
| `web/help_pages.py` | `sections(lang)`. |
| `web/guide/<code>/*.md`, `web/help/<code>/*.md` | Name the app's buttons as the app now shows them. |
| `tests/js/i18n.test.js`, `tests/js/locales.test.js`, `tests/js/pseudo.test.js`, `tests/test_web_i18n.py` | Tests. |

---

### Task 1: The message functions

**Files:**
- Create: `web/static/i18n.js`, `web/static/locales/en.json` (starting with only the keys this task's tests use), `tests/js/i18n.test.js`
- Modify: `tests/js/shim.js`

**Interfaces (all top-level functions in `i18n.js`, so `pages.js` and `app.js` call them as globals):**
- `setMessages(lang: string, messages: object)`: stores one language's nested messages.
- `setLang(lang: string)`: the language `T`/`t`/`tn`/`fmtNum` use. Default `'en'`.
- `currentLang() -> string`
- `t(key: string, values?: object) -> string`: the message as **plain text**, each `{{name}}` replaced by `String(values[name])`. Looks in the current language, then English. If neither has it, returns the key. For `alert`, `confirm`, `textContent`, `title`.
- `T(key, values?, html?: object) -> string`: the message as **HTML-safe text**: the message and every value are escaped; each `{{name}}` found in `html` is replaced by that string unescaped (markup the caller built). For builders.
- `tn(key, n: number, values?, html?) -> string`: as `T`, choosing `key + '_' + category` by `Intl.PluralRules(lang)`, falling back to `key + '_other'`; `{{count}}` is `fmtNum(n)`.
- `fmtNum(n) -> string`: `Number(n).toLocaleString(lang)`.
- `pickLang(stored: string|null, browser: string[]|undefined, supported: string[]) -> string`: `stored` if supported; else the first of `browser` whose part before `-`, lower-cased, is supported; else `'en'`.
- `hasMessage(key) -> boolean`: whether the current language or English has it.
- `tests/js/shim.js` `load()` runs `i18n.js`, then sets English from `web/static/locales/en.json`, then runs `pages.js`, all in one context, so every existing test sees English. It gains `load({ lang, messages })` to set another language.

- [ ] **Step 1: Write the failing tests** (`tests/js/i18n.test.js`)

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./shim');

const EN = { greet: 'Hello {{name}}', only: { en: 'English only' }, patrol_one: '{{count}} patrol', patrol_other: '{{count}} patrols',
             link: 'Read {{more}} first', plain: 'A <b>bold</b> claim' };
const FR = { greet: 'Bonjour {{name}}', patrol_one: '{{count}} patrouille', patrol_other: '{{count}} patrouilles' };
function ctx(lang) { const P = load(); P.setMessages('en', EN); P.setMessages('fr', FR); P.setLang(lang); return P; }

test('t gives plain text in the language, English when the language lacks the key, the key when neither has it', () => {
  const P = ctx('fr');
  assert.equal(P.t('greet', { name: 'Awa' }), 'Bonjour Awa');
  assert.equal(P.t('only.en'), 'English only');
  assert.equal(P.t('no.such.key'), 'no.such.key');
  assert.equal(P.hasMessage('only.en'), true); assert.equal(P.hasMessage('no.such.key'), false);
});
test('T escapes the message and every value, and inserts only the markup the caller built', () => {
  const P = ctx('en');
  assert.equal(P.T('greet', { name: '<img src=x onerror=alert(1)>' }), 'Hello &lt;img src=x onerror=alert(1)&gt;');
  assert.equal(P.T('plain'), 'A &lt;b&gt;bold&lt;/b&gt; claim');
  assert.equal(P.T('link', {}, { more: '<a href="#x">this</a>' }), 'Read <a href="#x">this</a> first');
  assert.equal(P.t('greet', { name: '<b>' }), 'Hello <b>', 't is plain text: the caller escapes it or gives it to textContent');
});
test('tn follows the language: French takes the singular for 0 and 1, and groups digits its own way', () => {
  const en = ctx('en'), fr = ctx('fr');
  assert.equal(en.tn('patrol', 0), '0 patrols'); assert.equal(en.tn('patrol', 1), '1 patrol'); assert.equal(en.tn('patrol', 1234), '1,234 patrols');
  assert.equal(fr.tn('patrol', 0), '0 patrouille'); assert.equal(fr.tn('patrol', 1), '1 patrouille');
  assert.match(fr.tn('patrol', 1234), /^1[   ]234 patrouilles$/);
});
test('tn falls back to _other when the language has no form for the category', () => {
  const P = load(); P.setMessages('en', { x_other: '{{count}} things' }); P.setLang('en');
  assert.equal(P.tn('x', 1), '1 things');
});
test('pickLang: a remembered choice, then the browser, then English', () => {
  const P = load(), S = ['en', 'fr', 'es', 'pt', 'sw'];
  assert.equal(P.pickLang('sw', ['fr-FR'], S), 'sw');
  assert.equal(P.pickLang(null, ['pt-BR', 'en'], S), 'pt');
  assert.equal(P.pickLang('de', ['es-MX'], S), 'es');
  assert.equal(P.pickLang(null, ['de'], S), 'en');
  assert.equal(P.pickLang(null, undefined, S), 'en');
});
test('the shim gives every other test English', () => {
  assert.equal(load().currentLang(), 'en');
});
```

- [ ] **Step 2: Run; expect failure** (`P.setMessages is not a function`)
- [ ] **Step 3: Implement `i18n.js`, the shim, and an `en.json` holding `{}`**
- [ ] **Step 4: Run both suites; expect pass**
- [ ] **Step 5: Commit** (`App: message functions for more than one language`)

---

### Task 2: Choosing a language, and the shell

**Files:**
- Modify: `web/templates/index.html`, `web/static/app.js`, `web/static/app.css`, `web/app.py`, `web/static/locales/en.json`
- Test: `tests/test_web_i18n.py` (new), `tests/js/locales.test.js` (new)

**Interfaces:**
- Server, in the page `GET /` renders:
  - `<script src="/static/i18n.js?v=…">` before `pages.js`; `i18n.js` joins `ASSETS`.
  - `<script type="application/json" id="languages">` holding the registry as JSON (`code`, `name`, `reviewed`).
  - `<meta name="locales-v" content="…">`: one hash over every `web/static/locales/*.json`, for cache-busting.
  - A language menu in the header, outside the account menu so it shows on the sign-in page: `<select id="lang" aria-label="Language">` with one `<option value="code" lang="code">Name</option>` per language.
  - `<p id="langNote" class="lang-note" hidden>` directly under the header.
  - Every fixed phrase of the shell carries a mark instead of being the source of truth: `data-i18n="key"` (text), `data-i18n-title="key"`, `data-i18n-aria="key"`. The English text stays in the template as the first paint.
- `en.json` gains the `shell.*` keys the template names, including `shell.language` ("Language") and `shell.machineTranslated` ("This translation was made by machine and has not yet been reviewed by a fluent speaker. If something is unclear, switch to English.").
- `app.js`:
  - `async function loadMessages(lang)`: fetches `/static/locales/<lang>.json?v=<locales-v>` (and English, once) and calls `setMessages`. A fetch that fails leaves English and does not throw.
  - `async function useLang(lang, remember: boolean)`: loads messages, `setLang`, sets `<html lang>`, the `<select>` value, applies the shell marks, shows `#langNote` when that language is `reviewed: false`, forgets the loaded help (`HELP = null`), and, if `remember`, stores `localStorage.lang` inside `try/catch`.
  - `boot()` calls `useLang(pickLang(stored, navigator.languages, codes), false)` before the first screen is shown.
  - Changing the `<select>` calls `useLang(value, true)`, then closes any dialog and the help drawer (`closeLayers()`) and re-renders where the reader is: `renderRoute(parseRoute(location.hash))` when signed in, `showSignIn()` when not.
- The app and the docs site are on different origins; each keeps its own `lang`.

- [ ] **Step 1: Write the failing tests**

`tests/test_web_i18n.py` (use the client fixture the other `tests/test_web_*.py` files use):

```python
def test_the_page_carries_the_languages_the_message_script_and_the_shell_marks(client):
    h = client.get("/").text
    assert re.search(r'<script src="/static/i18n\.js\?v=\w+"></script>\s*<script src="/static/pages\.js', h)
    langs = json.loads(re.search(r'<script type="application/json" id="languages">(.*?)</script>', h, re.S).group(1))
    assert [l["code"] for l in langs] == ["en", "fr", "es", "pt", "sw"] and langs[1]["reviewed"] is False
    assert re.findall(r'<option value="(\w+)" lang="\1">', h) == ["en", "fr", "es", "pt", "sw"]
    assert re.search(r'<meta name="locales-v" content="\w{6,}">', h) and 'id="langNote"' in h
    assert 'data-i18n="shell.sites"' in h and 'data-i18n="shell.signOut"' in h and 'data-i18n-aria="shell.help"' in h


def test_message_files_are_served(client):
    r = client.get("/static/locales/en.json")
    assert r.status_code == 200 and "shell" in r.json()
```

`tests/js/locales.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..', '..', 'web');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');
const flat = (o, p = '') => Object.entries(o).flatMap(([k, v]) => typeof v === 'object' ? flat(v, p + k + '.') : [[p + k, v]]);
const EN = Object.fromEntries(flat(JSON.parse(read('static/locales/en.json'))));

test('every key the code and the template ask for is in the English file', () => {
  const src = read('static/pages.js') + read('static/app.js');
  const asked = new Set([...src.matchAll(/\b(?:T|t|hasMessage)\(\s*'([\w.]+)'/g)].map(m => m[1]));
  for (const m of src.matchAll(/\btn\(\s*'([\w.]+)'/g)) asked.add(m[1] + '_other');
  for (const m of read('templates/index.html').matchAll(/data-i18n(?:-title|-aria)?="([\w.]+)"/g)) asked.add(m[1]);
  const missing = [...asked].filter(k => !(k in EN));
  assert.deepEqual(missing, []);
});
test('no message holds markup', () => {
  for (const [k, v] of Object.entries(EN)) assert.doesNotMatch(v, /<[a-z/]/i, k);
});
```

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Implement.** Style the menu and the note with tokens only; the menu must not push the header past a 320px phone.
- [ ] **Step 4: Run both suites; expect pass.** Start the app locally (`web/DEPLOY.md`, "Run locally", on a port other than 8080, bound to 127.0.0.1) and confirm in a browser that the menu shows on the sign-in page and that changing it sets `<html lang>`. Stop the server afterwards.
- [ ] **Step 5: Commit** (`App: a language menu, remembered, and a shell that can be translated`)

---

### Task 3: The builders, first half (sign-in, home, dataset page, sites, rangers)

**Files:**
- Modify: `web/static/pages.js` (lines 1–215: everything up to the load page), `web/static/locales/en.json`
- Test: existing `tests/js/shell.test.js`, `home.test.js`, `dataset.test.js`, `sites.test.js`, `pages.test.js`

**Rules:**
- Every phrase a reader sees becomes `T('group.name', values)`; a count becomes `tn`. Groups: `shell`, `signin`, `home`, `dataset`, `sites`, `rangers`, `status`, `units`.
- `plural(n, one, many)` goes; its callers use `tn`. `toLocaleString('en-US')` goes; use `fmtNum`.
- `pill(status, label)`: when no label is given, the label is `T('status.' + status)` if `hasMessage`, else the status in words as today. `en.json` has `status.<value>` for every key of `STATUS_CLASS`, worded exactly as today's output (`needs_attention` → "needs attention").
- `allowedPhrase` becomes three messages (`signin.yourAccount`, `signin.yourDomainAccount` with `{{domain}}`, `signin.accountAt` with `{{list}}` and `{{last}}`); a language orders the words itself.
- `loadScope` becomes four messages with `{{since}}` / `{{until}}`.
- A sentence with a link or a bold word inside it: the message has a placeholder, and the builder passes the markup through `T`'s third argument.
- English output does not change: the existing tests pass unedited. Where a test compares a whole string that this task had to restructure, keep the string identical.
- Fixed keys other tasks rely on (English values as today): `home.title` "Datasets"; `home.upload` "Upload a backup or export"; `dataset.browse` "Browse"; `dataset.load` "Load into EarthRanger"; `shell.sites` "EarthRanger sites"; `sites.add` "Add a site"; `rangers.title` "Rangers".
- Beside the **Browse** link, when the current language is not English, a short `dataset.browseInEnglish` note ("in English") says the data browser is not translated.

- [ ] **Step 1: Write the failing tests** (append to `tests/js/home.test.js` and `shell.test.js`)

```js
test('the home page follows the language', () => {
  const P = load({ lang: 'xx', messages: { home: { title: 'TITRE', upload: 'ENVOYER' }, status: { ready: 'PRÊT' } } });
  const h = P.renderHome([{ id: 'a1', name: 'R5', status: 'ready', mine: true }]);
  assert.match(h, /<h1>TITRE<\/h1>/); assert.match(h, />ENVOYER<\/button>/); assert.match(h, /<span class="pill st-success">PRÊT<\/span>/);
});
test('a status with no message is still shown in words', () => {
  assert.equal(load().pill('some_new_state'), '<span class="pill st-pending">some new state</span>');
});
test('the sign-in sentence is the language\'s own, with the domain as data', () => {
  const P = load({ lang: 'xx', messages: { signin: { yourDomainAccount: 'COMPTE {{domain}}' } } });
  assert.match(P.renderSignIn({ allowed: ['@a<b>.org'] }), /COMPTE @a&lt;b&gt;\.org/);
});
```

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Move the phrases**
- [ ] **Step 4: Run both suites; expect pass** (including Task 2's "every key … is in the English file")
- [ ] **Step 5: Commit** (`App: the sign-in, home, dataset, sites and rangers screens read their words from the message file`)

---

### Task 4: The builders, second half (the load page), and a test that no English is left

**Files:**
- Modify: `web/static/pages.js` (from `STAGES` to the end), `web/static/locales/en.json`
- Create: `tests/js/pseudo.test.js`
- Test: existing `tests/js/loadpage.test.js`

**Rules:** as Task 3, with groups `load`, `stages`, `findings`, `progress`, `plan`.
- `STAGE_LABEL` becomes `T('stages.' + stage)`; `fmtDur`'s units (`h`, `min`, `s`) become `units.*` messages.
- Findings: the frame is translated (the "Findings" heading, "No findings.", the severity word, "Fix:", "How to fix this", "Copy to clipboard"). A finding's own `title`, `detail`, `fix` and value labels are shown as stored; part 3 translates them.
- Fixed keys: `load.confirm` "Confirm and load"; `load.continue` "Continue"; `load.planAgain` "Plan again"; `load.delete` "Delete this load"; `findings.severity.blocking` "blocking"; `findings.severity.warning` "warning".

**The stand-in language test** (`tests/js/pseudo.test.js`): build a language in which every English message is replaced by `⟦key⟧` followed by its placeholders (`⟦load.confirm⟧`, `⟦home.count⟧{{count}}`), keeping plural suffixes. With it set, call every `render*` builder in `pages.js` with fixture data that reaches every branch (a dataset in each status; a load in each status, with and without findings, a plan, progress, rangers, continuations, a date window; sites; not-found; sign-in with none, one and several allowed entries). From each result: remove tags and their attributes except `title`, `aria-label`, `alt` and `placeholder` values, which are kept as text; remove every `⟦…⟧`; remove every fixture value (names, ids, hosts, dates, numbers, and the stored finding text). What is left must hold no run of three or more letters, apart from an allow-list declared at the top of the test: `EarthRanger`, `SMART`, `Google`, `CSV`, `GPS`, and unit symbols.

- [ ] **Step 1: Write `pseudo.test.js` and these tests in `loadpage.test.js`**

```js
test('a finding\'s frame is translated and its own words are shown as stored', () => {
  const P = load({ lang: 'xx', messages: { findings: { title: 'CONSTATS', fix: 'CORRIGER', severity: { blocking: 'BLOQUANT' } }, stages: { patrol_datamodel: 'ÉTAPE2' } } });
  const h = P.renderFindings([{ stage: 'patrol_datamodel', code: 'team', severity: 'blocking', title: 'Create a patrol team <x>', fix: 'Add it', values: [] }], 'needs_attention');
  assert.match(h, /<h3>CONSTATS<\/h3>/); assert.match(h, /BLOQUANT · ÉTAPE2/); assert.match(h, /<b>CORRIGER<\/b> Add it/);
  assert.match(h, /Create a patrol team &lt;x&gt;/);
});
test('durations use the language\'s units', () => {
  const P = load({ lang: 'xx', messages: { units: { hoursMinutes: '{{h}} HEURES {{m}} MINUTES' } } });
  assert.equal(P.fmtDur(3 * 3600 + 5 * 60), '3 HEURES 5 MINUTES');
});
```

(Use the unit key names you choose; keep `fmtDur`'s English output identical to today's.)

- [ ] **Step 2: Run; expect failure.** `pseudo.test.js` lists the English phrases still in the builders.
- [ ] **Step 3: Move the phrases until `pseudo.test.js` passes**
- [ ] **Step 4: Run both suites; expect pass**
- [ ] **Step 5: Commit** (`App: the load page reads its words from the message file; a test that no builder holds English`)

---

### Task 5: The wiring script (dialogs, prompts, the help drawer's frame)

**Files:**
- Modify: `web/static/app.js`, `web/static/locales/en.json`, `tests/js/locales.test.js`

**Rules:**
- Every phrase in `app.js` moves to `en.json` (groups `dialog`, `upload`, `siteDialog`, `loadDialog`, `share`, `confirm`, `signin`, `help`, `retry`, `csv`): the upload, site, load and share dialogs; the three `confirm()` prompts; sign-in errors; the retry note; the help drawer's note; CSV column headers.
- HTML built in `app.js` uses `T`; `alert`, `confirm`, `textContent` and `title` use `t`.
- Fixed keys: `upload.submit` "Upload"; `loadDialog.what` "What to load"; `loadDialog.modelOnly` "The data model only"; `loadDialog.modelAndPatrols` "The data model and patrols"; `loadDialog.makePlan` "Make the plan".
- The option lists a dialog builds from data (conservation areas, sites, languages of the bundle, configurable models) show the data as it is.

- [ ] **Step 1: Write the failing tests** (append to `tests/js/locales.test.js`)

```js
test('t() is used only where plain text is wanted; markup is built with T()', () => {
  const src = read('static/app.js') + read('static/pages.js');
  const ok = /(?:esc\(|alert\(|confirm\(|\.textContent = |\.title = |\.placeholder = |new Error\(|setAttribute\([^,]+, )\s*$/;
  const bad = [...src.matchAll(/\bt\(\s*'[\w.]+'/g)].filter(m => !ok.test(src.slice(Math.max(0, m.index - 40), m.index))).map(m => m[0]);
  assert.deepEqual(bad, []);
});
test('the wiring script holds no confirm or alert with words of its own', () => {
  const src = read('static/app.js');
  assert.deepEqual([...src.matchAll(/\b(?:alert|confirm)\(\s*'[^']*[A-Za-z]{3,} [a-z]/g)].map(m => m[0]), []);
});
test('every English message is used by the code or the template', () => {
  const src = read('static/pages.js') + read('static/app.js') + read('templates/index.html');
  const dynamic = [/^status\./, /^stages\./, /^findings\.severity\./, /^errors\./];   // looked up by a value from the data
  const unused = Object.keys(EN).filter(k => !dynamic.some(d => d.test(k)) && !src.includes("'" + k.replace(/_(one|other)$/, '') + "'") && !src.includes('"' + k + '"'));
  assert.deepEqual(unused, []);
});
```

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Move the phrases**
- [ ] **Step 4: Run both suites; expect pass.** Start the app locally and open each dialog (upload, add a site, load, share) and each prompt in English: the words are as before.
- [ ] **Step 5: Commit** (`App: the dialogs and prompts read their words from the message file`)

---

### Task 6: Server errors carry a code

**Files:**
- Modify: `web/app.py`, `web/auth.py`, `web/er_site.py` (only to tell its three `ValueError`s apart), `web/static/app.js`, `web/static/locales/en.json`
- Test: `tests/test_web_i18n.py`, `tests/js/locales.test.js`

**Interfaces:**
- `class ApiError(HTTPException)` in `web/app.py` (or a small `web/errors.py` if `auth.py` cannot import from `app.py`): `ApiError(status_code, code, detail, **values)`. A handler registered for it returns `{"detail": detail, "code": code, "values": values}` with the status. Every `raise HTTPException(…)` in `web/app.py` and `web/auth.py` becomes an `ApiError`; `detail` text is unchanged.
- The 422 handler is unchanged except that it adds `"code": "invalid_request"`.
- Codes (one per distinct message; the same message keeps one code):

| Code | Detail today | Values |
|---|---|---|
| `dataset_not_found` | Dataset not found | |
| `owner_only` | Only the owner can do that | |
| `upload_not_zip` | Upload a SMART backup or Conservation Area export as a .zip | |
| `upload_direct` | Uploads go straight to storage on this deployment | |
| `load_running` | Wait for the running load to stop first | |
| `upload_incomplete` | The upload is missing or incomplete; delete this dataset and upload again | |
| `extract_active` | An extraction is already queued or running | |
| `extract_start_failed` | Could not start the extraction job | |
| `load_running_delete` | Wait for the running load to stop (or delete it) first | |
| `share_not_allowed` | Can only share with allowed addresses | |
| `site_not_found` | Site not found | |
| `site_host_only` | Enter just the site's host name, like site.pamdas.org | |
| `site_host_missing` | Enter the site's host name, like site.pamdas.org | |
| `token_required` | A token is required | |
| `token_rejected` | The token was rejected: … | `reason` |
| `site_unreachable` | (the `SiteUnreachable` text) | `reason` |
| `window_not_date` | The window's … must be a date (YYYY-MM-DD) | `which` |
| `load_not_found` | Load not found | |
| `load_start_failed` | Could not start the load job | |
| `dataset_extracting` | The dataset is being extracted; wait for it to finish | |
| `load_active_same` | This load, or another load of this conservation area into that site, … | |
| `no_bundle` | No migration bundle for that conservation area; re-extract the dataset | |
| `scope_invalid` | What to load must be the data model only, or the data model and patrols | |
| `window_without_patrols` | A date window applies to patrols; a data-model-only load has none | |
| `window_reversed` | The window's start is after its end | |
| `no_patrols` | That conservation area has no patrols to load; load the data model only | |
| `language_not_in_bundle` | Language … is not in the bundle | `language` |
| `unknown_model` | Unknown configurable model | |
| `event_category_invalid` | The event category must be 2-30 letters, digits, '-' or '_' | |
| `load_active` | A load of this conservation area into that site is already active | |
| `site_removed` | The site was removed; register it again and start a new load | |
| `site_no_access` | You do not have access to that site | |
| `load_cannot_run` | A … load cannot be run; plan it again first | `status` |
| `load_cannot_plan` | A … load cannot be planned again now | `status` |
| `load_delete_running` | Wait for the load to stop before deleting it | |
| `bad_path` | Bad path | |
| `not_found` | Not found | |
| `dataset_status` | Dataset is … | `status` |
| `email_not_allowed` | This email is not allowed to use smart-able | |
| `token_invalid` | Invalid or expired token | |
| `signin_required` | Sign in required | |
| `invalid_request` | (422) | |

  `reason` values are the server's own English text (from EarthRanger or the network); they are shown as given. They never contain the token: assert it.
- `en.json` gains `errors.<code>` for every code, worded as the detail, with `{{placeholders}}` for the values; `errors.invalid_request` is "The request was not valid."
- `app.js` `api()`: on a failed response, read `detail`, `code`, `values`. The error's message is `t('errors.' + code, values)` when `hasMessage`, else `detail` when it is a string, else `t('errors.invalid_request')`, else the status text. The 401 path uses `errors.signin_required`.
- The sign-in screen's "This email is not allowed" path uses the same mapping.

- [ ] **Step 1: Write the failing tests**

```python
def test_an_error_keeps_its_english_detail_and_gains_a_code(client):
    r = client.get("/api/datasets/nope")
    assert r.status_code == 404 and r.json() == {"detail": "Dataset not found", "code": "dataset_not_found", "values": {}}


def test_an_error_with_a_name_in_it_gives_the_name_as_a_value(client):
    # use the fixtures test_web_loads.py uses to reach the "Language … is not in the bundle" refusal
    r = start_load(client, language="zz")
    assert r.status_code == 400 and r.json()["code"] == "language_not_in_bundle" and r.json()["values"] == {"language": "zz"}
    assert "zz" in r.json()["detail"]


def test_a_validation_error_has_a_code_and_still_drops_what_was_submitted(client):
    r = client.post("/api/sites", json={"name": "x", "url": "example.pamdas.org", "token": {"secret": "TOKEN-VALUE"}})
    assert r.status_code == 422 and r.json()["code"] == "invalid_request" and "TOKEN-VALUE" not in r.text


def test_no_route_raises_a_bare_http_exception():
    for f in ("app.py", "auth.py"):
        src = (ROOT / "web" / f).read_text()
        assert not re.search(r"raise HTTPException\(", src), f
    codes = set(re.findall(r'ApiError\(\s*\d+,\s*"(\w+)"', (ROOT / "web" / "app.py").read_text() + (ROOT / "web" / "auth.py").read_text()))
    en = json.loads((ROOT / "web" / "static" / "locales" / "en.json").read_text())["errors"]
    assert codes and codes <= set(en), codes - set(en)
```

`tests/js/locales.test.js`: extract `api()`'s message choice into a pure function `errorMessage(status, statusText, body)` in `pages.js` and test it:

```js
test('an error is shown in the language when its code is known, and as the server worded it when not', () => {
  const P = load({ lang: 'xx', messages: { errors: { dataset_not_found: 'INTROUVABLE', language_not_in_bundle: 'LANGUE {{language}}' } } });
  assert.equal(P.errorMessage(404, 'Not Found', { detail: 'Dataset not found', code: 'dataset_not_found', values: {} }), 'INTROUVABLE');
  assert.equal(P.errorMessage(400, 'Bad Request', { detail: 'x', code: 'language_not_in_bundle', values: { language: 'zz' } }), 'LANGUE zz');
  assert.equal(P.errorMessage(409, 'Conflict', { detail: 'Something new', code: 'brand_new_code' }), 'Something new');
  assert.equal(P.errorMessage(409, 'Conflict', { detail: 'Old server, no code' }), 'Old server, no code');
  assert.equal(P.errorMessage(422, 'Unprocessable', { detail: [{ loc: ['body', 'name'], msg: 'field required' }], code: 'invalid_request' }), 'The request was not valid.');
  assert.equal(P.errorMessage(500, 'Internal Server Error', null), 'Internal Server Error');
});
```

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Implement.** The existing Python tests that read `detail` pass unedited.
- [ ] **Step 4: Run both suites; expect pass**
- [ ] **Step 5: Commit** (`App: every server error carries a code the client can translate`)

---

### Task 7: The help drawer in the reader's language

**Files:**
- Modify: `web/help_pages.py`, `web/app.py`, `web/static/app.js`
- Test: `tests/test_web_i18n.py`, the existing help tests

**Interfaces:**
- `help_pages.sections(lang: str = "en") -> list`: each help page from `web/help/<lang>/<name>.md` when that file exists, else the English page. Each section gains `"lang"`: the language its text is in. The quirks reference is always English (`"lang": "en"`). Cached per language; a change to any source file of that language refreshes it.
- `GET /api/help?lang=<code>`: a code not in the registry is treated as `en`. The response shape is otherwise unchanged.
- `app.js`: `openHelp` requests `/api/help?lang=` + the current language; a section whose `lang` differs from the current language is rendered with `lang="…"` on its `<section>`. `useLang` already forgets the loaded help (Task 2); a drawer left open is closed by the language change.
- The site build (`scripts/build_pages.py`) still calls `help_pages` only for its Markdown configuration; `test_the_reference_pages_carry_the_apps_own_rendering` passes unedited.

- [ ] **Step 1: Write the failing tests**

```python
def test_help_is_served_in_the_language_asked_for_with_the_quirks_in_english(client):
    en = client.get("/api/help").json()["sections"]
    fr = client.get("/api/help?lang=fr").json()["sections"]
    assert [s["id"] for s in fr] == [s["id"] for s in en]
    assert {s["id"]: s["lang"] for s in fr} == {"overview": "fr", "sites": "fr", "loading": "fr", "statuses": "fr", "stops": "fr", "quirks": "en"}
    assert fr[0]["title"] != en[0]["title"] and all(s["lang"] == "en" for s in en)
    assert 'id="finding-team"' in next(s for s in fr if s["id"] == "stops")["html"], "the anchors the app links to survive translation"
    assert 'id="rangers-accounts"' in next(s for s in fr if s["id"] == "loading")["html"]


def test_help_in_an_unknown_language_is_english(client):
    assert client.get("/api/help?lang=../../etc").json() == client.get("/api/help").json()


def test_a_help_page_with_no_translation_is_the_english_one(client, monkeypatch, tmp_path):
    import help_pages
    d = tmp_path / "help"; (d / "fr").mkdir(parents=True)
    (d / "01-a.md").write_text("# A\n\nenglish"); (d / "02-b.md").write_text("# B\n\nenglish"); (d / "fr" / "01-a.md").write_text("# A fr\n\nfrançais")
    monkeypatch.setattr(help_pages, "HELP_DIR", d); help_pages._cache.clear()
    got = {s["id"]: (s["lang"], s["title"]) for s in help_pages.sections("fr")}
    assert got["a"] == ("fr", "A fr") and got["b"] == ("en", "B")
```

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run both suites; expect pass**
- [ ] **Step 5: Commit** (`App: the help drawer serves the reader's language`)

---

### Task 8: The four translations of the app

**Files:**
- Create: `web/static/locales/fr.json`, `es.json`, `pt.json`, `sw.json`
- Modify: `docs/translation-glossary.md`, `tests/js/locales.test.js`

**Rules:**
- Translate every key of `en.json`. Keep every `{{placeholder}}`. Give `_one` and `_other` for every plural; add the other forms the language's rules have only where the wording differs.
- Terms from the glossary, and the corrections the part 1 read-throughs made: "inactive", not "retired"; a duration is "after N hours", never a clock time; Swahili *amilifu* for active, *kategoria ya matukio* for event category, *sehemu ya kujaza* for a field; Spanish Latin American usage; Portuguese Brazilian usage.
- Short labels stay short: a button's translation should fit where the English fits. Where a language needs more room, prefer a shorter true wording over an abbreviation.
- Add to the glossary every app term not already there (buttons, tab names, stage names, status labels), one row each, so the docs (Task 9) and a reviewer use the same words.
- Status labels are the words a reader will quote to Support; add them to the glossary's "This tool's own words" with the API value beside them.

- [ ] **Step 1: Write the failing tests** (append to `tests/js/locales.test.js`)

```js
const LANGS = JSON.parse(read('static/locales/languages.json')).map(l => l.code).filter(c => c !== 'en');
for (const code of LANGS) {
  test(code + ' has every English message, with the same placeholders', () => {
    const L = Object.fromEntries(flat(JSON.parse(read('static/locales/' + code + '.json'))));
    const ph = s => (s.match(/\{\{\w+\}\}/g) || []).sort().join(' ');
    for (const [k, v] of Object.entries(EN)) {
      assert.ok(k in L && L[k].trim(), code + ' lacks ' + k);
      assert.equal(ph(L[k]), ph(v), code + ' ' + k);
      assert.doesNotMatch(L[k], /<[a-z/]/i, code + ' ' + k);
    }
    for (const k of Object.keys(L)) assert.ok(k in EN || /_(zero|one|two|few|many|other)$/.test(k) && k.replace(/_\w+$/, '_other') in EN, code + ' has an unknown key ' + k);
  });
  test(code + ' names no host but the example and holds no token', () => {
    const s = read('static/locales/' + code + '.json');
    assert.deepEqual([...new Set(s.match(/[a-z0-9-]+\.pamdas\.org/g) || [])].filter(h => !['example.pamdas.org', 'site.pamdas.org'].includes(h)), []);
    assert.doesNotMatch(s, /\b[0-9a-f]{32,}\b/);
  });
}
```

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Write the four files and the glossary rows**
- [ ] **Step 4: Run both suites; expect pass**
- [ ] **Step 5: Commit** (`App: French, Spanish, Portuguese and Swahili`)

---

### Task 9: The docs name the app's buttons as the app now shows them

**Files:**
- Modify: `web/guide/{fr,es,pt,sw}/03-your-first-migration.md`, `web/guide/{fr,es,pt,sw}/01-before-you-start.md`, `web/help/{fr,es,pt,sw}/*.md`
- Test: `tests/test_pages_site.py`

**Rules:**
- Part 1 named each app button in English with its meaning in brackets, and said the app was English. Now each translated page names the button, page, tab, stage and status **as that language's message file has it**, in bold, with no English beside it. Remove the sentences that say the app is in English ("L'application est pour l'instant en anglais…", "Les statuts sont affichés en anglais…", and their equivalents).
- The quoted sign-in refusal ("This email is not allowed") becomes the language's `errors.email_not_allowed`.
- In `04-statuses.md`, each row keeps the API value in code (`<code>needs_attention</code>`, unchanged) and adds the label the app shows beside it, so a reader can match either. The stage-status rows give the app's label for that language.
- Still English, and said to be: EarthRanger admin menu paths; the dataset browser; the quoted examples of stored text ("Data model only", "employee record deleted in SMART" if the app still shows it in English; check `en.json`).
- English pages: no change, unless a button name changed in this work.
- The build's shape checks must still pass: same steps, tabs, notes, links and code as the English pages.

- [ ] **Step 1: Write the failing test**

```python
NAMED_IN_THE_GUIDE = ["home.title", "home.upload", "upload.submit", "dataset.browse", "shell.sites", "sites.add", "dataset.load",
                      "loadDialog.what", "loadDialog.modelOnly", "loadDialog.modelAndPatrols", "loadDialog.makePlan",
                      "load.confirm", "load.continue", "rangers.title"]


def _message(code, key):
    node = json.loads((ROOT / "web" / "static" / "locales" / f"{code}.json").read_text(encoding="utf-8"))
    for part in key.split("."):
        node = node[part]
    return node


def test_the_translated_guide_names_each_button_as_the_app_shows_it(site, tmp_path):
    out = tmp_path / "o"; site.build(out)
    for code in ("fr", "es", "pt", "sw"):
        h = html.unescape((out / code / "your-first-migration.html").read_text(encoding="utf-8"))
        for key in NAMED_IN_THE_GUIDE:
            assert f"<strong>{_message(code, key)}</strong>" in h, (code, key)
        for english in ("Upload a backup or export", "Confirm and load", "Make the plan"):
            assert english not in h, (code, english)


def test_the_translated_statuses_page_gives_the_value_and_the_apps_label(site, tmp_path):
    out = tmp_path / "o"; site.build(out)
    for code in ("fr", "es", "pt", "sw"):
        h = html.unescape((out / code / "statuses.html").read_text(encoding="utf-8"))
        for value in ("planning", "planned", "queued", "running", "continuing", "needs_attention", "done", "failed"):
            assert re.search(rf"<code>{value}</code>[^<]*{re.escape(_message(code, 'status.' + value))}", h), (code, value)
```

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Edit the pages**, building after each language.
- [ ] **Step 4: Run both suites; expect pass**
- [ ] **Step 5: Commit** (`Docs: the translated pages name the app's buttons as the app shows them`)

---

### Task 10: Say how it works, and walk every screen in every language

**Files:**
- Modify: `web/DEPLOY.md` ("Languages" section), `README.md` if it describes the app as English-only

**`web/DEPLOY.md` gains:** where the app's messages are; how a reviewer corrects one; that `reviewed` in `languages.json` now also removes the note in the app; how to add a phrase (English first, then every language; the tests name what is missing); what stays English and why (the data browser, the log, the quirks reference, findings until part 3, text a job stored).

- [ ] **Step 1: Write the section.**
- [ ] **Step 2: Walk the app in a browser.** Start it locally with `AUTH_DISABLED`, bound to 127.0.0.1, on a port other than 8080, with a dataset that has no real data (make one from the test fixtures; never from `~/projects/smart-migration-artifacts` unless its contents have been checked). In each of the five languages, look at:
  - the sign-in page (with auth enabled in a second run, or the builder's output);
  - the home page, empty and with datasets in several statuses;
  - a dataset page: each tab;
  - the upload, add-a-site, load and share dialogs, and each confirm prompt;
  - the sites page;
  - a load page: planned with findings, running, needs attention, done, failed;
  - the help drawer, including a link from a finding to its help entry;
  - an error from the server (delete a running load; add a site with a bad host);
  - the header at a 360px-wide window.
  Then switch language with a dialog open, with the help drawer open, and on a polling load page.
  Record what was looked at, in which languages, and anything still English that is not on the "stays English" list. Fix what is found; a phrase found here that `pseudo.test.js` missed gets a fixture added so the test covers it.
- [ ] **Step 3: Run both suites; expect pass. Stop the local server.**
- [ ] **Step 4: Commit** (`Docs: how the app's languages work`)
