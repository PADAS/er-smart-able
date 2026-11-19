// tests/js/loadpage.test.js
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
const base = { id: 'ld1', ca_id: '050500', status: 'planned', held: false, site: { name: 'phinney', url: 'p.pamdas.org' }, options: { language: 'en', event_category: 'lawin050500', scope: 'all' },
               owner_email: 'ops@earthranger.com', created_at: '2026-11-13T10:00:00+00:00', mode: 'plan', stages: {}, findings: [], plan: null, rangers: [], progress: null };
test('the title block shows status, options, and the right actions', () => {
  const h = P.renderLoadTitle({ ...base, findings: [{ code: 'team', severity: 'blocking', stage: 'patrol_datamodel', title: 't' }] });
  assert.match(h, /050500 → phinney/); assert.match(h, /st-ready/); assert.match(h, /lawin050500/); assert.match(h, /data-run[^>]*>(?:<span class="mi"[^>]*>play_arrow<\/span>)?Confirm and load \(stops at 1 blocking\)/);
  assert.match(h, /data-replan/); assert.match(h, /data-del/); assert.match(h, /data-help="help-statuses"/);
  assert.doesNotMatch(P.renderLoadTitle({ ...base, status: 'running', held: true }), /data-run|data-del/);
  assert.match(P.renderLoadTitle({ ...base, status: 'needs_attention' }), /Continue/);
});
test('the rangers section renders for a plan and for a data-model-only load', () => {
  const rows = [{ name: 'Ana Cruz', smart_employee_id: 'E1', smart_member_id: 'm1', active: true, patrols: 0, patrols_total: 2, deleted: false, subject_id: null }];
  const plan = P.renderRangersSection({ ...base, rangers: rows, rangers_total: 1 });
  assert.match(plan, /Ana Cruz/); assert.match(plan, /not created yet/); assert.match(plan, /0 <span class="tiny">\/ 2<\/span>/);
  const dm = P.renderRangersSection({ ...base, options: { scope: 'datamodel' }, rangers: rows, rangers_total: 1 });
  assert.match(dm, /Patrols \(all\)/); assert.doesNotMatch(dm, /Patrols \(this load \/ all\)/);
});
test('the page composes its sections in order', () => {
  // mode 'run': a plan-mode load shows no progress bar, so the import summary would not appear
  const h = P.renderLoadPage({ ...base, mode: 'run', status: 'done', log_tail: 'load ld1: done', progress: { done: 2, patrols_total: 2, failed: 0, skipped: 0 },
    stages: { import: { status: 'done', started_at: '2026-11-13T10:00:00+00:00', finished_at: '2026-11-13T10:05:00+00:00', metrics: { imported: 2, failed: 0, skipped: 0, events_written: 9, events_reported_by: 9, events_reported_by_backfilled: 0 } } },
    findings: [{ code: 'patrol_type_icons', severity: 'warning', stage: 'patrol_datamodel', title: 'Pick icons', fix: 'x', values: [] }],
    rangers: [{ name: 'Ana Cruz', patrols: 2, patrols_total: 2 }], rangers_total: 1 }, false);
  const i = s => h.indexOf(s);
  assert.ok(i('class="stagetable"') < i('Findings') && i('Findings') < i('Rangers') && i('Rangers') < i('Progress') && i('Progress') < i('load ld1: done'));
  assert.match(h, /this execution wrote 9 events; 9 of the events it handled report who made them/);
});
test('the title block names the host, options, window and who started it', () => {
  const h = P.renderLoadTitle({ ...base, options: { ...base.options, since: '2024-01-01', configurable_model: 'cm-uuid' } });
  assert.match(h, /p\.pamdas\.org/); assert.match(h, /language en/); assert.match(h, /Patrols from 2024-01-01/); assert.match(h, /configurable model cm-uuid/);
  assert.match(h, /started by ops@earthranger\.com, 2026-11-13 10:00/);
  assert.doesNotMatch(h, /event type set/);
  const shared = P.renderLoadTitle({ ...base, options: { ...base.options, configurable_model: 'cm-uuid', event_type_set: 'Region <5>' } });
  assert.match(shared, /event type set Region &lt;5&gt;/);
  assert.match(P.renderLoadTitle({ ...base, site: null }), /050500 → removed site/);
  assert.doesNotMatch(P.renderLoadTitle({ ...base, site: null }), /data-run|data-replan/);
});
test('findings sort blocking first, keep their copy and help buttons, and say when there are none', () => {
  const h = P.renderFindings([{ code: 'w', severity: 'warning', stage: 'preflight', title: 'Warn' },
    { code: 'team', severity: 'blocking', stage: 'patrol_datamodel', title: 'Block', values: [{ label: 'id', value: 'a"b' }] }], 'planned');
  assert.ok(h.indexOf('Block') < h.indexOf('Warn')); assert.match(h, /data-help="finding-team"/); assert.match(h, /data-copy="a&quot;b"/); assert.match(h, /Patrol setup/);
  assert.match(P.renderFindings([], 'done'), /No findings\./); assert.equal(P.renderFindings([], 'running'), '');
});
test('time is read through now(), so a test can pin it', () => {
  const at = Date.parse('2026-11-13T10:05:00+00:00');
  const real = P.now; P.now = () => at;
  const l = { ...base, mode: 'run', status: 'running', held: true, started_at: '2026-11-13T10:00:00+00:00', updated_at: '2026-11-13T10:04:30+00:00',
              stages: { datamodel: { status: 'running', started_at: '2026-11-13T10:03:00+00:00' } } };
  let h; try { h = P.renderStages(l, true); } finally { P.now = real; }
  assert.match(h, /2 min 0 s…/); assert.match(h, /Running for 5 min 0 s · the job last reported 30 s ago/);
});
test('a load that cannot be opened says so in the load\'s words', () => {
  assert.match(P.renderNotFound('load'), /Not found or not shared with you[\s\S]*This load does not exist[\s\S]*href="#\/"/);
  assert.match(P.renderNotFound(), /This dataset does not exist/);
});
test('run and plan-again are disabled, with the reason, while the dataset is being extracted', () => {
  const h = P.renderLoadTitle({ ...base, dataset_extracting: true });
  assert.match(h, /data-run disabled/); assert.match(h, /data-replan disabled/); assert.match(h, /being extracted; the load can go on when that finishes/);
  assert.doesNotMatch(h, /data-del[^>]*disabled/);
  assert.doesNotMatch(P.renderLoadTitle(base), /disabled|being extracted/);
});
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

test('the kept rangers table is rebuilt when the language changes, and only then', () => {
  const l = { id: 'l1', rangers_total: 2, rangers: [{ name: 'A B', active: true }, { name: 'C D', active: false }] };
  const en = load(), fr = load({ lang: 'fr', messages: {} });
  assert.equal(en.rangersKey(l), en.rangersKey({ ...l, rangers: l.rangers.map(r => ({ ...r })) }), 'the same rows in the same language keep the table');
  assert.notEqual(en.rangersKey(l), fr.rangersKey(l), 'another language does not reuse the table');
  assert.notEqual(en.rangersKey(l), en.rangersKey({ ...l, rangers: l.rangers.slice(1) }));
  assert.equal(en.rangersKey({ id: 'l1' }), '', 'no rows: nothing to keep');
});
test('the load page takes its rangers key from rangersKey', () => {
  const src = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', '..', 'web', 'static', 'app.js'), 'utf8');
  assert.match(src, /const key = rangersKey\(l\);/);
});

// ---- part 3: findings in the reader's language
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

test('the translated path is the one taken for a named finding in another language', () => {
  const h = load({ lang: 'fr', messages: {} }).renderFindings([TEAM], 'needs_attention');   // the real French messages are not loaded here: English is the fallback text
  assert.match(h, /class="original"/, 'a named finding with its message and values is shown from the message file');
});
// ---- support view
test('a load in support view says so and has no run, plan-again or delete', () => {
  const stale = { ...base, status: 'running', held: false };
  for (const l of [base, { ...base, status: 'needs_attention' }, { ...base, status: 'failed' }, { ...base, status: 'done' }, stale, { ...base, site: null, status: 'failed', error: 'Site was removed' }, { ...base, dataset_extracting: true }]) {
    const h = P.renderLoadPage({ ...l, access: 'support' }, false);
    assert.match(h, /class="support-line">.*Owned by ops@earthranger\.com\./, l.status);
    assert.doesNotMatch(h, /data-run|data-replan|data-del/, l.status);
    assert.match(P.renderLoadPage({ ...l, access: 'shared' }, false), /data-del/, l.status);
    assert.doesNotMatch(P.renderLoadPage({ ...l, access: 'shared' }, false), /support-line/);
  }
  assert.match(P.renderLoadPage({ ...base, site: null, status: 'failed', error: 'Site was removed', access: 'support' }, false), /Site was removed/);
  const h = P.renderLoadPage({ ...stale, access: 'support' }, false);   // told what happened, not what to press
  assert.match(h, /The job stopped without reporting\.</); assert.doesNotMatch(h, /continue to resume/);
  assert.match(P.renderLoadPage({ ...stale, access: 'shared' }, false), /continue to resume/);
});
