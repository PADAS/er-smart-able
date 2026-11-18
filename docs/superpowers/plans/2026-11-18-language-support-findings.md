# Language support, part 3: findings. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a load's findings (what stopped it, and what to do) in the reader's language, with the stored English kept in reach.

**Architecture:** A finding is stored in English, worded partly by `er-smart-sync`. When the server builds a finding it now also stores a message key and the counts and names its sentence uses. The browser shows the message for that key in the reader's language when it has one and every placeholder is filled; otherwise it shows the stored English. The stored English stays under the translated text, because it carries data (member names, patrol counts) the translated sentence does not.

**Tech Stack:** Python (`web/findings.py`), plain browser JavaScript, pytest, `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-17-language-support-design.md` ("Part 3: findings"). Parts 1 and 2 are merged (PRs 37 and 38).

## Global Constraints

- No change to `er-smart-sync`. Its English wording is read, never edited.
- Nothing stored changes meaning: a finding keeps `stage`, `code`, `severity`, `title`, `detail`, `fix`, `affected`, `values` exactly as today. `key`, `params` and `created_by_run` are added; each value gains `label_key`.
- A load made before this change has no `key`: it shows its stored English, as today.
- **An English reader sees no change.** In English the page shows the stored text, as today. The English messages exist as the source for the translations and as the fallback.
- A finding is shown translated only when the reader's language is not English, the finding has a `key`, the message exists, and every placeholder is filled. Never a raw key, a raw `{{placeholder}}`, or half of each.
- Copyable values and `detail` lines are shown exactly as stored. They are data.
- A message holds text only, never HTML; every message and value is escaped where it goes into the page.
- Terms follow `docs/translation-glossary.md` and the wording of `web/help/<code>/05-stops.md`, which already explains each finding in each language.
- Messages: `web/static/locales/<code>.json`, nested keys, `{{name}}` placeholders, `_one` / `_other` plurals.
- Tests: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q` and `node --test "tests/js/*.test.js"`. Both pass at the end of every task.
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>` (the implementer's own model name). Do not push; do not open a PR.
- With `AUTH_DISABLED` the service listens on 127.0.0.1 only; never use port 8080.

## Review Focus

1. **A finding worded in a way the server does not recognise** (a new `er-smart-sync` release rewords a message or adds a code). Expected: no `key`; the page shows the stored English. Tests in Task 1 and Task 2.
2. **A finding whose message needs a value the finding lacks** (`params` missing a name). Expected: the stored English, whole. Test in Task 2.
3. **A count of one** ("1 patrol type(s)"). Expected: the language's singular. Test in Task 3 (every plural has `_one`), and Task 2.
4. **Data in the stored text that the translation drops** (a team's members, "referenced by 12 patrols", the patrol type names needing icons). Expected: still readable, under "Original text". Test in Task 2.
5. **A plan's findings for things the run will create.** Expected: marked as such in the reader's language, not blocking. Tests in Task 1 and Task 2.

## File Structure

| File | Responsibility |
|---|---|
| `web/findings.py` | Builds findings; now also names each one's message key and params. |
| `web/static/pages.js` | `findingText(f)` chooses translated or stored text; `renderFindings` shows it. |
| `web/static/locales/*.json` | `findingText.<key>.title`, `.fix`; `findings.valueLabel.*`; frame words. |
| `web/help/<code>/05-stops.md` | Names each finding as the app now shows it. |
| `docs/translation-glossary.md` | The findings that still show in English, and why. |
| `tests/test_findings.py`, `tests/js/loadpage.test.js`, `tests/js/locales.test.js`, `tests/js/pseudo.test.js` | Tests. |

---

### Task 1: The server names each finding's message

**Files:**
- Modify: `web/findings.py`
- Test: `tests/test_findings.py`

**Interfaces:**
- `finding(stage, code, severity, title, detail="", fix="", patrols=(), values=(), key=None, params=None)` adds `"key": key` and `"params": dict(params or {})` to the dict.
- `FINDING_KEYS: frozenset[str]`: every key this module can emit (below). Exported for the tests in Task 2.
- Each entry of `values` gains `"label_key"`: `team_name`, `subject_group`, `station_name`, `feature`, `permission`. `"label"` stays.
- `plan_mode_adjust` adds `"created_by_run": True` to each finding it turns into info. Title and severity change as today.

**Keys and params** (a finding the rules below do not match gets `key=None`):

| Source | Code | Key | Params |
|---|---|---|---|
| checklist | `team` | `checklist.team` | `name`: the title after "Create the patrol team " |
| checklist | `roster_group` | `checklist.roster_group` | |
| checklist | `permission_subject_group` | `checklist.permission_subject_group` | `group`: the name in backticks in the title |
| checklist | `enable_patrol_schemas` | `checklist.enable_patrol_schemas` | |
| checklist | `permission_patrol_types`, `permission_segment_schema`, `permission_subjects`, `permission_patrol_config` | `checklist.<code>` | |
| checklist | `patrol_type_icons` | `checklist.patrol_type_icons` | |
| checklist | `station_names` | `checklist.station_names` | |
| preflight | `timezone`, `language`, `time_coverage`, `feature_flag`, `permissions`, `patrol_types`, `segment_schema`, `choices`, `subjects`, `teams`, `collection_type`, `observers`, `bundle_warnings` | `preflight.<code>` | `count`: the finding's `count` |
| preflight | `leg_span` | `preflight.leg_span` | `count`; `days`: the number before " leg days" in the message |
| preflight | `inactive_members`, level warning | `preflight.inactive_members.retired` | `count` |
| preflight | `inactive_members`, level blocking | `preflight.inactive_members.stranded` | `count` |
| preflight | `event_types`, message has "have no active event type" | `preflight.event_types.unmatched` | `count` |
| preflight | `event_types`, message has "match more than one event type" | `preflight.event_types.ambiguous` | `count` |
| preflight | `event_types`, message has "map to an inactive event type" | `preflight.event_types.inactive` | `count` |
| preflight | `event_types`, message has "exist only as configurable" | `preflight.event_types.variants` | `count` |
| preflight | `check_failed` | none | (its message is the check's name and a Python error) |
| import | `patrols_failed` | `import.patrols_failed` | `count` |
| datamodel | `site_token_rejected` | `datamodel.site_token_rejected` | |

- A param the rule cannot extract (the title does not match, `days` is not found) leaves `key=None`: the page then shows the stored English.
- `count` is `f["count"]` when it is an int, else `len(f["examples"])`.
- `_created_by_run` keeps working from the title, as today, and may use the key.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_findings.py`; `findings` is the module fixture that file already uses)

```python
PRE = lambda code, level, message, **kw: {"code": code, "level": level, "message": message, "fix": "x", "count": kw.pop("count", 2),
                                          "examples": kw.pop("examples", ["a", "b"]), "affected_patrols": [], **kw}


def test_every_finding_names_its_message_and_the_values_it_uses(findings):
    cl = findings.from_checklist([
        {"code": "team", "title": "Create the patrol team Alpha Team", "steps": ["add a team with display `Alpha Team`."]},
        {"code": "permission_subject_group", "title": "Add the subjects to the `Rangers` subject group", "steps": []},
        {"code": "roster_group", "title": "Put the ranger subjects in the patrol roster subject group", "steps": []}])
    assert [(f["key"], f["params"]) for f in cl] == [("checklist.team", {"name": "Alpha Team"}),
        ("checklist.permission_subject_group", {"group": "Rangers"}), ("checklist.roster_group", {})]
    assert cl[0]["values"] == [{"label": "Team name", "value": "Alpha Team", "label_key": "team_name"}]
    assert cl[0]["title"] == "Create the patrol team Alpha Team", "the stored English is untouched"
    pre = findings.from_preflight({"blocking": [PRE("patrol_types", "blocking", "2 patrol type(s) the legs need are missing or inactive")],
                                   "warnings": [PRE("leg_span", "warning", "3 leg(s) start on SMART's 1970-01-01 placeholder or span more than a year (41 leg days as stored)", count=3)]})
    assert (pre[0]["key"], pre[0]["params"]) == ("preflight.patrol_types", {"count": 2})
    assert (pre[1]["key"], pre[1]["params"]) == ("preflight.leg_span", {"count": 3, "days": 41})
    assert findings.from_failed_patrols({"u1": "boom"}, {})[0]["key"] == "import.patrols_failed"
    assert findings.from_failed_patrols({"u1": "boom"}, {})[0]["params"] == {"count": 1}
    assert findings.token_rejected("401")["key"] == "datamodel.site_token_rejected"


@pytest.mark.parametrize("level, message, key", [
    ("blocking", "4 observed SMART categor(ies) have no active event type on the site", "preflight.event_types.unmatched"),
    ("blocking", "1 categor(ies) match more than one event type (several data model pushes on this site)", "preflight.event_types.ambiguous"),
    ("warning", "2 observed categor(ies) map to an inactive event type (a SMART parent or retired category)", "preflight.event_types.inactive"),
    ("blocking", "3 observed categor(ies) exist only as configurable model variants (one event type per form)", "preflight.event_types.variants"),
])
def test_the_four_event_type_findings_are_told_apart(findings, level, message, key):
    assert findings.from_preflight({"blocking": [PRE("event_types", level, message)]})[0]["key"] == key


def test_retired_and_stranded_members_are_told_apart(findings):
    f = findings.from_preflight({"warnings": [PRE("inactive_members", "warning", "2 patrol member(s) are retired (inactive subjects)")],
                                 "blocking": [PRE("inactive_members", "blocking", "1 retired member(s) are in no configured member group, so reactivating them would still leave them off the roster", count=1)]})
    assert {x["key"] for x in f} == {"preflight.inactive_members.retired", "preflight.inactive_members.stranded"}


def test_a_finding_the_rules_do_not_recognise_has_no_key(findings):
    f = findings.from_preflight({"blocking": [PRE("brand_new_code", "blocking", "something new"),
                                              PRE("event_types", "blocking", "reworded beyond recognition"),
                                              PRE("leg_span", "warning", "reworded, with no day count"),
                                              PRE("check_failed", "blocking", "check_teams could not run: KeyError: 'x'")]})
    assert [x["key"] for x in f] == [None, None, None, None] and all(x["params"] == {} for x in f)
    cl = findings.from_checklist([{"code": "team", "title": "A reworded team title", "steps": []}, {"code": "unheard_of", "title": "x", "steps": []}])
    assert [x["key"] for x in cl] == [None, None]


def test_every_key_the_module_can_emit_is_listed(findings):
    assert {"checklist.team", "preflight.event_types.unmatched", "preflight.inactive_members.stranded", "import.patrols_failed",
            "datamodel.site_token_rejected"} <= findings.FINDING_KEYS
    assert "preflight.check_failed" not in findings.FINDING_KEYS and len(findings.FINDING_KEYS) == 32


def test_a_plans_findings_for_what_the_run_creates_say_so(findings):
    pre = findings.from_preflight({"blocking": [PRE("patrol_types", "blocking", "2 patrol type(s) the legs need are missing or inactive"),
                                                PRE("teams", "blocking", "1 patrol team(s) are missing or inactive", count=1)]})
    out = findings.plan_mode_adjust(pre)
    assert out[0]["created_by_run"] is True and out[0]["severity"] == "info" and out[0]["key"] == "preflight.patrol_types"
    assert "created_by_run" not in out[1] and out[1]["severity"] == "blocking"
```

(32 = 10 checklist keys + 13 plain preflight + leg_span + 2 inactive_members + 4 event_types + 1 import + 1 datamodel. If the count differs when implemented, the table above is the authority: make the constant match the table and correct the number in the test.)

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Implement.** One small table-driven function, `_key(source, f) -> (key, params)`, called by `from_checklist`, `from_preflight`, `from_failed_patrols` and `token_rejected`.
- [ ] **Step 4: Run both suites; expect pass.** The existing tests in `tests/test_findings.py` and `tests/test_load_job.py` pass unedited, except where one compares a whole finding dict: there, add the new fields to the expectation and nothing else.
- [ ] **Step 5: Commit** (`Findings: each one names its message and the values its sentence uses`)

---

### Task 2: The page shows a finding in the reader's language

**Files:**
- Modify: `web/static/pages.js` (`renderFindings` and a new `findingText`), `web/static/locales/en.json`
- Test: `tests/js/loadpage.test.js`, `tests/js/locales.test.js`, `tests/js/pseudo.test.js`, `tests/test_findings.py`

**Interfaces:**
- `findingText(f) -> { title, fix, translated }`, plain text. `translated` is true only when all of these hold: `currentLang() !== 'en'`; `f.key` is a string; `hasMessage('findingText.' + f.key + '.title')`; the rendered title and fix contain no `{{`. Then `title` and `fix` are the messages (the title through `tn` when `f.params.count` is a number, else `t`). Otherwise `title = f.title`, `fix = f.fix`, `translated = false`.
- A finding with `created_by_run` and `translated`: the title is `t('findings.createdByRun', { title })`. Not translated: `f.title` already carries the English prefix.
- `renderFindings`:
  - shows `findingText(f).title` and `.fix`, escaped;
  - when `translated`, adds below the fix a closed `<details class="original" lang="en"><summary>` + `T('findings.original')` + `</summary>` holding the stored `title` and `fix`, escaped, the fix in a `<pre>`;
  - a value's label is `T('findings.valueLabel.' + v.label_key)` when `v.label_key` is set and `hasMessage`, else `v.label`;
  - `detail`, values and everything else as today.
- `en.json` gains:
  - `findingText.<key>.title` and `.fix` for every key in `FINDING_KEYS`. A title with a count has `title_one` and `title_other` and no bare `title`. Wording: the title says what the stored title says, as a sentence a site person can act on; the fix is the instruction from the matching entry of `web/help/05-stops.md`, in the app's terms ("press Continue"), never the command line ("run patrol-datamodel").
  - `findings.original`: "Original text (English)"; `findings.createdByRun`: "Will be created by this load: {{title}}"; `findings.valueLabel.{team_name,subject_group,station_name,feature,permission}`.
- `tests/js/locales.test.js`: add `/^findingText\./` and `/^findings\.valueLabel\./` to the dynamic-key list of "every English message is used".

- [ ] **Step 1: Write the failing tests**

`tests/js/loadpage.test.js`:

```js
const TEAM = { stage: 'patrol_datamodel', code: 'team', severity: 'blocking', title: 'Create the patrol team Alpha <Team>', detail: '',
  fix: 'Django admin > Patrol configuration > Teams > add a team with display `Alpha <Team>`.\nMembers (from SMART): A B, C D.\nReferenced by 12 patrols in the bundle.',
  key: 'checklist.team', params: { name: 'Alpha <Team>' }, values: [{ label: 'Team name', value: 'Alpha <Team>', label_key: 'team_name' }], affected: { count: 0, patrols: [] } };
const XX = { findingText: { checklist: { team: { title: 'ÉQUIPE {{name}}', fix: 'CRÉEZ-LA' } }, preflight: { patrol_types: { title_one: '{{count}} TYPE', title_other: '{{count}} TYPES', fix: 'CONTINUEZ' } } },
  findings: { original: 'ORIGINAL', createdByRun: 'SERA CRÉÉ : {{title}}', valueLabel: { team_name: 'NOM' } } };

test('a finding is shown in the reader\'s language, with the stored text under it', () => {
  const h = load({ lang: 'xx', messages: XX }).renderFindings([TEAM], 'needs_attention');
  assert.match(h, /<b>ÉQUIPE Alpha &lt;Team&gt;<\/b>/); assert.match(h, /CRÉEZ-LA/); assert.match(h, /<span class="tiny">NOM<\/span>/);
  const orig = h.slice(h.indexOf('<details class="original" lang="en">'));
  assert.match(orig, /<summary>ORIGINAL<\/summary>/); assert.match(orig, /Create the patrol team Alpha &lt;Team&gt;/);
  assert.match(orig, /Members \(from SMART\): A B, C D\./); assert.match(orig, /Referenced by 12 patrols/);
});
test('an English reader sees the stored text, as before, and no second copy', () => {
  const h = load().renderFindings([TEAM], 'needs_attention');
  assert.match(h, /<b>Create the patrol team Alpha &lt;Team&gt;<\/b>/); assert.match(h, /Members \(from SMART\)/);
  assert.doesNotMatch(h, /class="original"/); assert.match(h, /<span class="tiny">Team name<\/span>/);
});
test('a finding with no key, no message, or a missing value is shown as stored, whole', () => {
  const P = load({ lang: 'xx', messages: XX });
  for (const f of [{ ...TEAM, key: undefined }, { ...TEAM, key: 'checklist.unheard_of' }, { ...TEAM, params: {} }, { ...TEAM, key: null, params: undefined }]) {
    const h = P.renderFindings([f], 'needs_attention');
    assert.match(h, /<b>Create the patrol team Alpha &lt;Team&gt;<\/b>/); assert.doesNotMatch(h, /ÉQUIPE|\{\{|class="original"/);
  }
});
test('a counted title follows the language\'s plural, and a plan marks what the run creates', () => {
  const P = load({ lang: 'xx', messages: XX });
  const f = n => ({ stage: 'preflight', code: 'patrol_types', severity: 'blocking', title: n + ' patrol type(s) the legs need are missing or inactive', fix: 'Run patrol-datamodel', key: 'preflight.patrol_types', params: { count: n }, values: [] });
  assert.equal(P.findingText(f(1)).title, '1 TYPE'); assert.equal(P.findingText(f(3)).title, '3 TYPES'); assert.equal(P.findingText(f(3)).fix, 'CONTINUEZ');
  const made = { ...f(2), severity: 'info', created_by_run: true, title: 'Will be created by this load: 2 patrol type(s) the legs need are missing or inactive' };
  assert.equal(P.findingText(made).title, 'SERA CRÉÉ : 2 TYPES');
  assert.equal(load().findingText(made).title, made.title);
});
```

`tests/test_findings.py` (the server's keys and the English messages are one set):

```python
def test_every_key_has_an_english_title_and_fix_and_no_message_is_left_over(findings):
    en = json.loads((ROOT / "web" / "static" / "locales" / "en.json").read_text())["findingText"]
    have = set()
    def walk(node, path):
        if any(k in node for k in ("title", "title_one", "title_other", "fix")):
            assert "fix" in node and ("title" in node or {"title_one", "title_other"} <= set(node)), path
            have.add(path)
        else:
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
    walk(en, "")
    assert have == set(findings.FINDING_KEYS)
```

`tests/js/pseudo.test.js`: add to the `renderFindings` and `renderLoadPage` fixtures a keyed finding of each shape (a checklist finding with a name and a value, a counted preflight finding, a created-by-run finding) so the stand-in language renders the translated path; the stored English inside `<details class="original" lang="en">` is stored text and is stripped as such.

- [ ] **Step 2: Run; expect failure**
- [ ] **Step 3: Implement** `findingText`, the rendering, and the English messages.
- [ ] **Step 4: Run both suites; expect pass.** The existing findings tests in `loadpage.test.js` pass unedited.
- [ ] **Step 5: Commit** (`App: a finding is shown in the reader's language, with its stored text under it`)

---

### Task 3: The four translations

**Files:**
- Modify: `web/static/locales/{fr,es,pt,sw}.json`, `docs/translation-glossary.md`

**Rules:**
- Translate every new key. Keep every `{{placeholder}}`. Give `_one` and `_other` wherever English has them.
- Each fix says what the entry for that finding says in `web/help/<code>/05-stops.md`; reuse its wording and terms. EarthRanger admin menu paths stay in English, as on that page.
- Settled terms: inactive, not retired; Swahili *amilifu*, *kategoria ya matukio*, *sehemu ya kujaza*, *maandalizi ya doria* for the Patrol setup stage; Portuguese *preparação de patrulhas*; Spanish Latin American usage; French *vous*.
- A fix that tells the reader to press a button names it as the app does (`load.continue`, `load.planAgain`), character for character.
- Glossary: add a section "Findings that still show in English" listing: a finding with code `check_failed`; any finding from a load made before this release; any finding whose wording a later `er-smart-sync` changes; and the `detail` lines and copyable values of every finding (they are data).

- [ ] **Step 1: Run `node --test "tests/js/*.test.js"`; expect the per-language tests in `locales.test.js` to fail on the missing keys.**
- [ ] **Step 2: Write the translations, one language at a time, running the tests after each.**
- [ ] **Step 3: Re-read each language against `en.json` and against that language's `05-stops.md`:** a changed instruction, a lost "nothing to do", a wrong button name, a wrong plural.
- [ ] **Step 4: Run both suites; expect pass.**
- [ ] **Step 5: Commit** (`Findings: French, Spanish, Portuguese and Swahili`)

---

### Task 4: Docs, and a look at real pages

**Files:**
- Modify: `web/help/{fr,es,pt,sw}/05-stops.md`, `web/DEPLOY.md`, `tests/test_pages_site.py`

**Docs:**
- In each translated `05-stops.md`, the four bold finding names under "Event types" (`**No active event type** (…)` and the three after it) are still English with a gloss. Each becomes that language's `findingText.preflight.event_types.<variant>` title, shortened to its name if the page's sentence needs it, with no English beside it. The page's sentence saying finding names are in English, if it has one, goes.
- Keep steps, notes, links, anchors and code spans as the English page has them (the build checks).
- `web/DEPLOY.md`, "Languages": findings are now translated by key; the stored English is under "Original text"; what still shows in English and why (point to the glossary); how to add a finding (a key in `web/findings.py`, the English message, then every language; the tests name what is missing).

**The look:**
- Run the app on 127.0.0.1:8090 with `BACKEND=local AUTH_DISABLED=true` and made-up data only (the earlier walk's seed script and driver are in `.superpowers/sdd/2026-11-17-language-support-app/walk/` if that folder still exists; otherwise seed from `tests/test_web_loads.py`'s helpers). Seed one load whose findings carry keys and params: a team to create, a counted preflight finding, an event-types finding, a created-by-run finding in a plan, a `check_failed`, and one with no key.
- In each of the five languages look at that load page: translated title and fix; "Original text" closed, and showing the stored English when opened; value labels; the `check_failed` and the no-key finding in English; the help button on a finding opening its entry; nothing overflowing at 360px.
- Report a table of what was seen per language and what was not. Stop the server.

- [ ] **Step 1: Write the failing test**

```python
def test_the_translated_stops_page_names_the_event_type_findings_as_the_app_does(site, tmp_path):
    out = tmp_path / "o"; site.build(out)
    for code in ("fr", "es", "pt", "sw"):
        h = html.unescape((out / code / "stops.html").read_text(encoding="utf-8"))
        for english in ("No active event type", "Match more than one event type", "Map to an inactive event type", "Exist only as configurable model variants"):
            assert english not in h, (code, english)
```

- [ ] **Step 2: Run; expect failure. Edit the pages and `DEPLOY.md`. Run both suites and the site build; expect pass.**
- [ ] **Step 3: Do the look. Fix what it finds when the fix is small; record what is not.**
- [ ] **Step 4: Commit** (`Docs: findings in the reader's language`)
