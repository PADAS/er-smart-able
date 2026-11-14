const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
const d = { id: 'a1', name: 'R5 Lawin', source_name: 'r5.zip', source_size: 1000, created_at: '2026-10-07T00:00:00+00:00', status: 'ready', mine: true, shared_with: [],
            export: [{ dir: 'ALPHA', ca_id: '050500', name: 'Albay', patrols: 1527, waypoints: 30000 }, { dir: 'BETA', ca_id: '050504', name: 'Guinobatan', patrols: 0 }],
            counts: { patrols: 1527, waypoints: 30000 }, log_tail: 'done' };
test('overview offers Browse and Load for every export entry, a zero-patrol area included', () => {
  const h = P.renderDatasetPage(d, 'overview', {});
  assert.match(h, /href="\/d\/a1\/"/); assert.match(h, /data-act="load" data-ca="ALPHA"/); assert.match(h, /data-act="load" data-ca="BETA"/);
  assert.match(h, /Guinobatan[\s\S]*0 patrols/); assert.doesNotMatch(h, /re-extract to enable loading/); assert.match(h, /id="shareBtn"/); assert.match(h, /id="deleteBtn"/);
});
test('an area with no patrols alone still gets a Load button and the Loads tab its button', () => {
  const zero = { ...d, export: [{ dir: 'BETA', ca_id: '050504', name: 'Guinobatan', patrols: 0 }] };
  assert.match(P.renderDatasetPage(zero, 'overview', {}), /data-act="load" data-ca="BETA"/);
  assert.match(P.renderDatasetPage(zero, 'loads', { loads: [] }), /id="loadBtn"/);
  assert.equal(P.hasBundle({ dir: 'BETA', patrols: 0 }), true); assert.equal(P.hasBundle({ ca_id: '050500', name: 'Albay' }), false);
});
test('Browse shows only once the dataset is ready (the viewer answers 409 otherwise)', () => {
  const h = P.renderDatasetPage({ ...d, status: 'running', extract_held: true }, 'overview', {});
  assert.doesNotMatch(h, /href="\/d\/a1\/"/); assert.match(h, /data-act="load" data-ca="ALPHA"/);
});
test('a failed re-extract keeps the Loads and Rangers tabs reachable while the export is there', () => {
  const h = P.renderDatasetPage({ ...d, status: 'failed', error: 'boom' }, 'overview', {});
  assert.doesNotMatch(h, /href="#\/datasets\/a1\/loads"[^>]*aria-disabled/); assert.doesNotMatch(h, /href="#\/datasets\/a1\/rangers"[^>]*aria-disabled/);
  assert.equal(P.hasLoadTabs({ status: 'failed', export: [] }), false); assert.equal(P.hasLoadTabs({ status: 'ready' }), true);
});
test('a ready dataset without export entries still lists its areas for Browse', () => {
  const h = P.renderDatasetPage({ ...d, export: null, cas: [{ id: '050500', n: 'Albay' }] }, 'overview', {});
  assert.match(h, /Albay/); assert.match(h, /href="\/d\/a1\/"/); assert.match(h, /re-extract to enable loading/); assert.doesNotMatch(h, /data-act="load"/);
});
test('a dataset still extracting disables the actions and the other tabs', () => {
  const h = P.renderDatasetPage({ ...d, status: 'running', extract_held: true, export: [] }, 'overview', {});
  assert.match(h, /id="deleteBtn"[^>]*disabled/); assert.match(h, /href="#\/datasets\/a1\/loads"[^>]*aria-disabled="true"/); assert.match(h, /<details open/);
});
test('a failed extraction still opens, with its error', () => {
  assert.match(P.renderDatasetPage({ ...d, status: 'failed', error: 'boom', export: [] }, 'overview', {}), /st-error[\s\S]*boom/);
});
test('the actions belong to the owner only', () => {
  assert.doesNotMatch(P.renderDatasetPage({ ...d, mine: false, owner_email: 'o@x.org' }, 'overview', {}), /id="shareBtn"/);
});
test('the loads tab lists loads newest first with an empty state', () => {
  const loads = [{ id: 'l1', ca_id: 'ALPHA', status: 'done', site: { name: 'phinney', url: 'p.pamdas.org' }, created_at: '2026-11-01T00:00:00+00:00', progress: { done: 10, patrols_total: 10 } },
                 { id: 'l2', ca_id: 'ALPHA', status: 'running', site: { name: 'phinney', url: 'p.pamdas.org' }, created_at: '2026-11-02T00:00:00+00:00', progress: { done: 3, patrols_total: 10 } }];
  const h = P.renderDatasetPage(d, 'loads', { loads });
  assert.ok(h.indexOf('data-load="l2"') < h.indexOf('data-load="l1"')); assert.match(h, /3 of 10 patrols/); assert.match(h, /id="loadBtn"/);
  assert.match(P.renderDatasetPage(d, 'loads', { loads: [] }), /No loads yet\./);
});
test('a loads tab row names what the load wrote after its status', () => {
  const loads = [{ id: 'l1', ca_id: 'ALPHA', status: 'done', site: { name: 'phinney' }, created_at: '2026-11-01T00:00:00+00:00', options: { scope: 'datamodel' } },
                 { id: 'l2', ca_id: 'ALPHA', status: 'done', site: { name: 'phinney' }, created_at: '2026-11-02T00:00:00+00:00', options: { since: '2024-01-01', until: '2024-12-31' } },
                 { id: 'l3', ca_id: 'ALPHA', status: 'done', site: { name: 'phinney' }, created_at: '2026-11-03T00:00:00+00:00', options: {} }];
  const h = P.renderDatasetPage(d, 'loads', { loads });
  assert.match(h, /data-load="l1"[\s\S]*st-success[^<]*<\/span><div class="tiny">Data model only<\/div>/);
  assert.match(h, /data-load="l2"[\s\S]*<div class="tiny">Patrols from 2024-01-01 to 2024-12-31<\/div>/);
  assert.doesNotMatch(h.slice(h.indexOf('data-load="l3"')).split('</tr>')[0], /<div class="tiny">/);
});
test('the loads and rangers tables sit inside a panel, so a phone scrolls the panel, not the page', () => {
  const inPanel = (h, table) => { const at = h.indexOf(table), open = h.lastIndexOf('<div class="panel">', at); return at > 0 && open >= 0 && !h.slice(open, at).includes('</div>'); };
  const loads = [{ id: 'l1', ca_id: 'ALPHA', status: 'done', site: { name: 'phinney' }, created_at: '2026-11-01T00:00:00+00:00' }];
  assert.ok(inPanel(P.renderDatasetPage(d, 'loads', { loads }), '<table>'));
  const l = { id: 'l1', ca_id: 'ALPHA', site: { name: 'phinney' }, created_at: '2026-11-01T00:00:00+00:00', rangers: [{ name: 'Ana', patrols: 3, subject_id: '0f6c1d1e-2b3a-4c5d-8e9f-0a1b2c3d4e5f' }], rangers_total: 1 };
  assert.ok(inPanel(P.renderDatasetPage(d, 'rangers', { load: l }), '<table class="rangers">'));
});
test('the rangers tab names its source load, or points at the viewer when there are none', () => {
  const l = { id: 'l1', ca_id: 'ALPHA', site: { name: 'phinney' }, created_at: '2026-11-01T00:00:00+00:00', rangers: [{ name: 'Ana', patrols: 3 }], rangers_total: 1 };
  const h = P.renderDatasetPage(d, 'rangers', { load: l });
  assert.match(h, /From the load of ALPHA into phinney, 2026-11-01/); assert.match(h, /Ana/); assert.match(h, /data-csv/);
  assert.match(h, /<details open><summary><h3[^>]*>Rangers/);   // the tab's only content is not behind a click
  assert.match(P.renderRangersSection(l), /^<details><summary>/);   // the load page keeps it closed
  assert.match(P.renderDatasetPage(d, 'rangers', { load: null }), /No rangers listed yet/);
});
test('not found names the problem and links home', () => { assert.match(P.renderNotFound(), /Not found or not shared with you[\s\S]*href="#\/"/); });
