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
