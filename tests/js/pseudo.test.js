// A stand-in language in which every English message reads "⟦key⟧" followed by its placeholders.
// Every render* builder in pages.js is called with fixtures that reach each branch; once the tags, the
// stand-in messages and the fixture's own values are removed, no word may be left: whatever is left
// is English written into the code instead of the message file.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { load } = require('./shim');

// Words that are the same in every language. Each entry is a name or an acronym, never a phrase:
// to make a phrase pass, move it to the message file instead.
const ALLOWED = [
  'EarthRanger', // the product's name (the logo's alt text)
  'SMART',       // the conservation software's name
  'Google',      // the sign-in provider's name
  'CSV',         // a file format
  'GPS',         // an acronym
];
// What the page shows that is not language: the names of a load's files are the files' real names.
const FILE_NAMES = ['plan.json', 'findings.json', 'checklist.json', 'checklist.md', 'rangers.json', 'import-ledger.json', 'log.txt'];

const EN = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'web', 'static', 'locales', 'en.json'), 'utf8'));
function standIn(node, prefix) {
  const out = {};
  for (const [k, v] of Object.entries(node)) {
    const key = prefix + k;
    out[k] = typeof v === 'object' ? standIn(v, key + '.') : '⟦' + key + '⟧' + (v.match(/\{\{\w+\}\}/g) || []).join('');
  }
  return out;
}
const P = load({ lang: 'xx', messages: standIn(EN, '') });
P.now = () => Date.parse('2026-11-13T10:05:00+00:00');

// ---- fixtures
const area = (dir, more) => Object.assign({ dir, ca_id: 'ca' + dir, name: 'Reserve ' + dir, version: '7.5.1', patrols: 12, waypoints: 1 }, more);
const DATASETS = ['queued', 'running', 'ready', 'failed', 'uploading', 'extracting', 'odd_status'].map((status, i) => ({
  id: 'ds' + i, name: 'Dataset ' + status, source_name: 'backup-' + i + '.zip', source_size: [5e9, 5e6, 5e3, 5, 0, 2e9, 1][i], status,
  created_at: '2026-11-1' + i + 'T10:00:00+00:00', started_at: '2026-11-13T10:00:00+00:00', finished_at: i % 2 ? '2026-11-13T10:30:00+00:00' : null,
  cas: [{ id: 'cas' + i, n: 'Area ' + status }, { id: 'noname' + i }], counts: i % 3 ? { patrols: 3, waypoints: 1 } : { patrols: 1234 },
  error: i === 3 ? 'The extraction broke: disk full' : '', mine: i % 2 === 0, owner_email: 'owner' + i + '@example.org', shared_with: i < 2 ? ['pal@example.org', 'kin@example.org'] : [],
  extract_held: status === 'running', db_version: '7.4', log_tail: i < 3 ? 'extracting line one' : '',
  export: i === 2 ? [area('d1'), area('d2', { dir: '', version: null, patrols: null, waypoints: null })] : [],
}));
const ownDs = { ...DATASETS[2], mine: true, extract_held: false, export: [area('d1'), area('d2', { dir: '', patrols: null, waypoints: null })] };
const SITES = [{ id: 's1', name: 'Site One', url: 'one.example.org', token_hint: 'ab12', checked_as: 'ops@example.org', mine: true, owner_email: 'ops@example.org', shared_with: ['pal@example.org'] },
               { id: 's2', name: 'Site Two', url: 'two.example.org', token_hint: 'cd34', checked_as: 'ops@example.org', mine: false, owner_email: 'other@example.org', shared_with: [] }];
const RANGERS = [{ name: 'Ana Cruz', smart_employee_id: 'E1', active: true, patrols: 0, patrols_total: 2, deleted: false, subject_id: null },
                 { name: 'Ben Diaz', smart_employee_id: 'E2', active: false, patrols: 2, patrols_total: 2, deleted: true, subject_id: 'subj-9' },
                 { name: 'Cy Eze', smart_employee_id: 'E3', patrols: 1, patrols_total: 1, subject_id: 'subj-8' }];
const FINDINGS = [
  { stage: 'patrol_datamodel', code: 'team', severity: 'blocking', title: 'Create a patrol team', detail: 'Stored detail lines', fix: 'Add it by hand', values: [{ label: 'Team id', value: 'team-77' }], affected: { count: 5 } },
  { stage: 'preflight', code: 'icons', severity: 'warning', title: 'Pick some icons', values: [] },
  { stage: 'mystery_stage', code: 'odd', severity: 'curious', title: 'Something unusual', affected: {} },
  { stage: 'import', code: 'note', severity: 'info', title: 'For your information' },
];
const SITE = { name: 'Site One', url: 'one.example.org' };
const LOAD = { id: 'ld1', ca_id: '050500', status: 'planned', held: false, site: SITE, options: { language: 'xx-lang', event_category: 'cat050500', scope: 'all', since: '2024-01-01', until: '2024-06-30', configurable_model: 'cm-uuid' },
  owner_email: 'ops@example.org', created_at: '2026-11-13T10:00:00+00:00', mode: 'plan', stages: {}, findings: [], plan: null, rangers: [], progress: null };
const T0 = '2026-11-13T10:00:00+00:00', T1 = '2026-11-13T10:03:00+00:00', T2 = '2026-11-13T10:05:00+00:00';
const FULL_METRICS = {
  datamodel: { categories_created: 1, categories_existing: 2, event_types_created: 3, event_types_updated: 4, event_types_unchanged: 5, event_types_migrated: 6, event_types_skipped_by_mode: 7, event_types_skipped_by_conflict: 8, event_types_errored: 9, choices_created: 1, choices_updated: 2, choices_unchanged: 3, choices_deactivated: 4, choices_errored: 5 },
  patrol_datamodel: { types_created: 1, types_updated: 2, types_unchanged: 3, subjects_created: 4, subjects_updated: 5, subjects_deactivated: 6, subjects_unchanged: 7, subjects_grouped: 8, schema_written: 1 },
  preflight: { blocking: 1, warnings: 2, patrols: 3 },
  import: { planned: 4, already_done: 1, events_written: 9, events_reported_by: 8, events_reported_by_backfilled: 2 },
};
const stagesOf = (status, extra) => Object.fromEntries(Object.keys(FULL_METRICS).map(s => [s, { status, started_at: T0, finished_at: T1, metrics: FULL_METRICS[s], ...extra }]));
const PLAN = { event_categories: { create: [{ label: 'Cat new' }], update: [], deactivate: [{ label: 'Cat old', value: 'cat-old' }], unchanged: 2 },
  event_types: { create: [{ label: 'Type new', value: 'type-new' }], update: [{ label: 'Type same', value: 'Type same' }], more: { create: 4 }, unchanged: 1 },
  patrol_types: { create: [], update: [] }, universal_patrol_fields: 'written', choices: { update: [{ label: 'Choice up', value: 'ch-1' }], more: 3 },
  subjects: { create: [{ label: 'Subj new', value: 'subj-id' }] }, roster: { group: 'Rangers group', add: 3 },
  patrols: { total: 12, first: '2024-01-02', last: '2024-06-01', already_done: 2, events: 40, track_points: 900 } };
const LOADS = [
  { ...LOAD, findings: FINDINGS, plan: PLAN, rangers: RANGERS, rangers_total: 5, stages: stagesOf('done') },
  { ...LOAD, options: { scope: 'datamodel' }, dataset_extracting: true, plan: { event_types: { create: [{ label: 'T' }] } }, rangers: RANGERS, rangers_total: 3, findings: [], stages: stagesOf('done') },
  { ...LOAD, options: { since: '2024-01-01' }, status: 'needs_attention', findings: FINDINGS.slice(0, 1), error: 'The job crashed: stored text', continuations: 2, log_tail: 'stored log lines', stages: stagesOf('failed') },
  { ...LOAD, options: { until: '2024-06-30' }, status: 'needs_attention', findings: FINDINGS.slice(0, 2), plan: { patrols: null }, stages: { datamodel: { status: 'stopped', metrics: {} } } },
  { ...LOAD, status: 'planned', findings: [FINDINGS[1]] },
  { ...LOAD, status: 'failed', site: null, findings: [], error: 'Site was removed: stored' },
  { ...LOAD, status: 'done', mode: 'run', findings: [], plan: { universal_patrol_fields: 'x' }, progress: { done: 3, patrols_total: 3, failed: 1, skipped: 2 }, stages: stagesOf('done', { metrics: undefined }) },
  { ...LOAD, status: 'done', mode: 'run', progress: { done: 1234, patrols_total: 5000, failed: 0, skipped: 0 }, stages: { ...stagesOf('done'), import: { status: 'done', started_at: T0, finished_at: T2, metrics: { events_written: 1 } } } },
  { ...LOAD, status: 'running', held: true, mode: 'run', started_at: T0, claimed_at: T0, updated_at: T2, continuations: 0, progress: { done: 40, patrols_total: 100, failed: 0, skipped: 0, phase: 'events', phase_started_at: T0, phase_skipped: 0 },
    stages: { datamodel: { status: 'done', started_at: T0, finished_at: T1, metrics: {} }, patrol_datamodel: { status: 'running', started_at: T1, metrics: {} }, import: { status: 'running', started_at: T0, metrics: {} } } },
  { ...LOAD, status: 'running', held: true, mode: 'run', started_at: T0, updated_at: T2, continuations: 2, progress: { done: 40, patrols_total: 100, failed: 0, skipped: 0, phase: 'tracks', phase_started_at: T0 }, stages: { import: { status: 'running', started_at: T0, metrics: {} } } },
  { ...LOAD, status: 'continuing', held: true, mode: 'run', started_at: T0, updated_at: T2, progress: { done: 10, patrols_total: 100, failed: 0, skipped: 0 }, stages: { import: { status: 'running', started_at: T0, metrics: {} } } },
  { ...LOAD, status: 'running', held: false, mode: 'run', started_at: T0, updated_at: T2, stages: { datamodel: { status: 'running', started_at: T0, metrics: {} } } },
  { ...LOAD, status: 'queued', held: true, mode: null, claimed_at: T0, stages: {} },
  { ...LOAD, status: 'planning', held: true, mode: null, claimed_at: T0 },
  // loads from before the stage table: only `stage` and `status`
  { ...LOAD, status: 'needs_attention', mode: null, stage: 'preflight', stages: undefined },
  { ...LOAD, status: 'done', mode: null, stage: 'import', stages: undefined, progress: { done: 2, patrols_total: 2, failed: 0, skipped: 0 } },
  { ...LOAD, status: 'failed', mode: null, stage: 'datamodel', stages: undefined },
];
const CALLS = {
  renderBreadcrumb: [[[{ label: 'Crumb one', hash: '#/' }, { label: 'Crumb two' }]]],
  renderSignIn: [[{}], [{ allowed: ['@one.example.org'] }], [{ allowed: ['@a.example.org', '@b.example.org', '@c.example.org'] }], [{ allowed: '@str.example.org' }]],
  renderDatasetCard: DATASETS.map(d => [d]),
  renderCardList: [[DATASETS], [[]]],
  renderHome: [[DATASETS], [[]]],
  renderRangersSection: [[{ ...LOAD, rangers: RANGERS, rangers_total: 3 }, true], [{ ...LOAD, rangers: RANGERS, rangers_total: 9, options: { scope: 'datamodel' } }], [LOAD]],
  renderNotFound: [['load'], ['dataset'], []],
  renderSites: [[SITES], [[]]],
  renderTabs: [[ownDs, 'overview'], [DATASETS[0], 'loads'], [ownDs, 'rangers']],
  renderOverview: [...DATASETS.map(d => [d]), [ownDs], [{ ...DATASETS[2], export: [], cas: [] }], [{ ...DATASETS[2], export: [], cas: [{ id: 'c1', n: 'Old area' }] }]],
  renderLoadsTab: [[ownDs, LOADS], [ownDs, []], [DATASETS[1], []]],
  renderRangersTab: [[{ ...LOAD, rangers: RANGERS }], [{ ...LOAD, site: null, rangers: RANGERS }], [null], [{ ...LOAD, rangers: [] }]],
  renderDatasetPage: [[ownDs, 'overview'], [ownDs, 'loads', { loads: LOADS }], [DATASETS[1], 'rangers', { load: { ...LOAD, rangers: RANGERS } }], [DATASETS[0], 'overview']],
  renderLoadTitle: LOADS.map(l => [l]).concat([[{ ...LOADS[0], findings: FINDINGS.slice(0, 2) }], [{ ...LOADS[0], held: true }], [{ ...LOADS[0], status: 'planned', findings: [] }]]),
  renderFindings: [[FINDINGS, 'planned'], [[], 'done'], [[], 'running'], [undefined, 'planned']],
  renderProgress: LOADS.flatMap(l => [[l, true], [l, false]]),
  renderLoadPage: LOADS.flatMap(l => [[l, true], [l, false]]),
  renderStages: LOADS.flatMap(l => [[l, true], [l, false]]),
  renderPlan: [[PLAN], [{}], [{ patrols: { total: 1, events: 0, track_points: 0 }, roster: {}, subjects: { create: [], unchanged: 3 } }]],
};

function values(x, out) {
  if (typeof x === 'string') out.add(x);
  else if (x && typeof x === 'object') Object.values(x).forEach(v => values(v, out));
  return out;
}
// a status the page has no word for is shown as stored, with its underscores read as spaces
const FIXTURE_VALUES = [...values([CALLS, FILE_NAMES], new Set())].flatMap(v => [v, v.replace(/_/g, ' ')]).filter(v => v.length >= 3).sort((a, b) => b.length - a.length);

const decode = s => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
// keep what a reader can see or hear: the text, and the title, aria-label, alt and placeholder values
function visible(html) {
  return html.replace(/<span class="mi"[^>]*>[^<]*<\/span>/g, ' ')   // an icon's name is a glyph, not a word
    .replace(/<[^>]*>/g, tag => ' ' + [...tag.matchAll(/\s(?:title|aria-label|alt|placeholder)="([^"]*)"/g)].map(m => m[1]).join(' ') + ' ');
}
function leftover(html) {
  let s = decode(visible(html)).replace(/⟦[^⟧]*⟧/g, ' ');
  for (const v of FIXTURE_VALUES) s = s.split(v).join(' ');
  for (const w of ALLOWED) s = s.split(w).join(' ');
  return s.match(/\p{L}{3,}/gu) || [];
}

test('every render* builder has fixtures here', () => {
  const builders = Object.keys(P).filter(k => /^render/.test(k)).sort();
  assert.deepEqual(builders, Object.keys(CALLS).sort());
});
for (const [name, calls] of Object.entries(CALLS)) {
  test(name + ' holds no English once the messages and the data are taken out', () => {
    const left = new Set();
    for (const args of calls) {
      const html = P[name](...args);
      assert.equal(typeof html, 'string');
      assert.doesNotMatch(html, /undefined|\bnull\b|NaN|\[object/, name + ' wrote a missing value');
      for (const w of leftover(html)) left.add(w);
    }
    assert.deepEqual([...left], [], name + ' still holds English');
  });
}
