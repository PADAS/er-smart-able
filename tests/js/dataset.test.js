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
  assert.doesNotMatch(h, /href="\/d\/a1\/"/);
});
test('no Load is offered while the dataset is being extracted: the bundle is being rewritten', () => {
  const held = { ...d, status: 'running', extract_held: true };
  assert.doesNotMatch(P.renderDatasetPage(held, 'overview', {}), /data-act="load"/);
  assert.doesNotMatch(P.renderDatasetPage(held, 'loads', { loads: [] }), /id="loadBtn"/);
  // a run that died without reporting stops holding: Load is back with the export it left
  assert.match(P.renderDatasetPage({ ...d, status: 'running', extract_held: false }, 'overview', {}), /data-act="load" data-ca="ALPHA"/);
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
  assert.match(h, /id="deleteBtn"[^>]*disabled/); assert.match(h, /id="extractBtn"[^>]*disabled/); assert.doesNotMatch(h, /id="shareBtn"[^>]*disabled/);   // sharing changes nothing the job touches
  assert.match(h, /href="#\/datasets\/a1\/loads"[^>]*aria-disabled="true"/); assert.match(h, /<details open/);
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
test('overview says when the extraction started and finished', () => {
  const h = P.renderDatasetPage({ ...d, started_at: '2026-11-13T10:00:00+00:00', finished_at: '2026-11-13T10:07:00+00:00' }, 'overview', {});
  assert.match(h, /Started 2026-11-13 10:00 · Finished 2026-11-13 10:07/);
});
test('a run that stopped reporting is not shown as live, and says what to do', () => {
  const h = P.renderDatasetPage({ ...d, status: 'running', extract_held: false, log_tail: 'unzipping' }, 'overview', {});
  assert.match(h, /stopped without reporting\. Run it again with Re-extract/); assert.match(h, /Log tail/); assert.doesNotMatch(h, /<details open/);
  assert.doesNotMatch(P.renderDatasetPage({ ...d, status: 'running', extract_held: true }, 'overview', {}), /stopped without reporting/);
});
test('a ready dataset that lists no areas still has its way into the viewer', () => {
  const h = P.renderDatasetPage({ ...d, export: [], cas: [] }, 'overview', {});
  assert.match(h, /None listed[\s\S]*href="\/d\/a1\/"/);
  assert.doesNotMatch(P.renderDatasetPage({ ...d, status: 'failed', export: [], cas: [] }, 'overview', {}), /href="\/d\/a1\/"/);
});
test('the Browse link says the data browser is in English when the language is not', () => {
  const { load: ld } = require('./shim');
  const d = { id: 'a1', name: 'R5', status: 'ready', export: [{ ca_id: '1', name: 'A', dir: 'x' }] };
  assert.doesNotMatch(ld().renderOverview(d), /in English/);
  assert.match(ld({ lang: 'xx', messages: { dataset: { browseInEnglish: 'EN' } } }).renderOverview(d), />Browse<\/a> <span class="tiny">EN<\/span>/);
});

// ---- the uploaded backup
const DAY = 86400000, T0 = Date.parse('2026-11-18T00:00:00Z');
function at(P) { P.now = () => T0; return P; }
const own = { id: 'a1', name: 'North', source_name: 'north.zip', source_size: 5000000, status: 'ready', mine: true, created_at: '2026-11-01T00:00:00+00:00', export: [] };
test('the backup panel says when the backup goes and that the extracted data stays', () => {
  const P = at(load());
  const h = P.backupPanel({ ...own, upload: { present: true, expires_at: '2026-12-01T00:00:00+00:00', deleted_at: null } });
  assert.match(h, /<h2>Uploaded backup<\/h2>/); assert.match(h, /north\.zip · 5 MB/);
  assert.match(h, /Deleted automatically on 2026-12-01 \(in 13 days\)\./);
  assert.match(h, /The extracted data is not affected\. It stays until you delete the dataset\./);
  assert.match(h, /<button id="deleteBackupBtn" class="danger">.*Delete the backup now<\/button>/);
  assert.match(P.backupPanel({ ...own, upload: { present: true, expires_at: new Date(T0 + DAY - 1000).toISOString() } }), /\(in 1 day\)/);
  assert.match(P.backupPanel({ ...own, upload: { present: true, expires_at: new Date(T0 - 1000).toISOString() } }), /Due for automatic deletion/);
  assert.match(P.backupPanel({ ...own, upload: { present: true, expires_at: null } }), /Stored until you delete it\./);
});
test('a backup that has gone says so, offers no delete, and the page offers no re-extract', () => {
  const P = at(load());
  const gone = { ...own, upload: { present: false, expires_at: '2026-12-01T00:00:00+00:00', deleted_at: '2026-11-10T08:00:00+00:00' } };
  const h = P.backupPanel(gone);
  assert.match(h, /Deleted on 2026-11-10\. To extract again, upload the backup again as a new dataset\./);
  assert.match(h, /The extracted data is not affected/); assert.doesNotMatch(h, /deleteBackupBtn/);
  assert.match(P.backupPanel({ ...gone, upload: { present: false } }), /No longer stored\./);
  assert.doesNotMatch(P.renderDatasetPage(gone, 'overview'), /id="extractBtn"/);
  assert.match(P.renderDatasetPage({ ...own, upload: { present: true } }, 'overview'), /id="extractBtn"/);
  assert.match(P.renderDatasetPage(own, 'overview'), /id="extractBtn"/, 'no word about the backup: the button stays');
});
test('only the owner is offered the delete, not while it is being extracted, and nothing shows while it is uploading', () => {
  const P = at(load()), up = { present: true, expires_at: '2026-12-01T00:00:00+00:00' };
  assert.doesNotMatch(P.backupPanel({ ...own, mine: false, upload: up }), /deleteBackupBtn/);
  assert.match(P.backupPanel({ ...own, extract_held: true, upload: up }), /id="deleteBackupBtn" class="danger" disabled/);
  assert.equal(P.backupPanel({ ...own, status: 'uploading', upload: { present: false } }), '');
  assert.equal(P.backupPanel(own), '');
  assert.match(P.renderDatasetPage({ ...own, upload: up }, 'backup'), /id="backup"/);
});
test('the delete dialogs say what goes and that it cannot be undone, with Cancel first', () => {
  const P = load();
  const ds = P.deleteDatasetBody();
  assert.match(ds, /uploaded backup, the extracted data, the migration bundles and the load records/);
  assert.match(ds, /<b>This cannot be undone\.<\/b>/); assert.match(ds, /Nothing in EarthRanger is removed\./);
  assert.match(ds, /<button type="button" class="ghost" data-close>Cancel<\/button><button type="button" class="danger" id="confirmGo">.*Delete dataset<\/button>/);
  const b = P.deleteBackupBody({ source_name: 'a<b>.zip' });
  assert.match(b, /deletes the file a&lt;b&gt;\.zip now\. The extracted data, the bundles and the loads stay\./);
  assert.match(b, /This cannot be undone/); assert.match(b, /Delete backup<\/button>/);
});

// ---- the Backup tab
test('the uploaded backup has its own tab, and the Overview no longer carries the panel', () => {
  const P = at(load()), up = { present: true, expires_at: '2026-12-20T00:00:00+00:00' };
  const ds = { ...own, upload: up };
  assert.equal(JSON.stringify(P.parseRoute('#/datasets/a1/backup')), JSON.stringify({ page: 'dataset', id: 'a1', tab: 'backup' }));
  assert.equal(P.routeHash({ page: 'dataset', id: 'a1', tab: 'backup' }), '#/datasets/a1/backup');
  const tabs = P.renderTabs(ds, 'backup');
  assert.match(tabs, /<a href="#\/datasets\/a1\/backup" class="active" aria-current="page">Backup<\/a>/);
  assert.ok(tabs.indexOf('/rangers') < tabs.indexOf('/backup'), 'Overview, Loads, Rangers, Backup');
  assert.match(P.renderDatasetPage(ds, 'backup'), /id="backup"/); assert.match(P.renderDatasetPage(ds, 'backup'), /Delete the backup now/);
  assert.doesNotMatch(P.renderDatasetPage(ds, 'overview'), /id="backup"/);
  assert.doesNotMatch(P.renderTabs({ ...own, status: 'failed', export: [] }, 'overview'), /backup"[^>]*aria-disabled/, 'the tab is there whatever the extraction did');
});
test('the Overview reminds the reader only when the backup goes within a week or has gone', () => {
  const P = at(load()), on = (u, extra) => P.renderOverview({ ...own, upload: u, ...extra });
  assert.doesNotMatch(on({ present: true, expires_at: new Date(T0 + 20 * DAY).toISOString() }), /backup/i, 'weeks away: nothing');
  assert.doesNotMatch(on({ present: true, expires_at: null }), /backup/i);
  const soon = on({ present: true, expires_at: new Date(T0 + 3 * DAY).toISOString() });
  assert.match(soon, /The uploaded backup is deleted in 3 days\. <a href="#\/datasets\/a1\/backup">Backup<\/a>/);
  assert.match(on({ present: true, expires_at: new Date(T0 + DAY - 1000).toISOString() }), /deleted in 1 day\./);
  assert.match(on({ present: true, expires_at: new Date(T0 - 1000).toISOString() }), /The uploaded backup is due for automatic deletion\. <a href/);
  assert.match(on({ present: false }), /The uploaded backup is no longer stored\. <a href="#\/datasets\/a1\/backup">Backup<\/a>/);
  assert.doesNotMatch(on({ present: false }, { status: 'uploading' }), /no longer stored/);
  assert.doesNotMatch(P.renderOverview(own), /backup/i, 'no word about the backup from the server: nothing');
});
test('the Backup tab says so while the file is still uploading', () => {
  const P = at(load());
  assert.match(P.renderDatasetPage({ ...own, status: 'uploading', upload: { present: false } }, 'backup'), /The backup is still uploading\./);
});

test('a tab the bar offers is a tab the route opens: Backup on a dataset that failed before extracting anything', () => {
  const P = at(load()), failed = { ...own, status: 'failed', export: [], cas: [], upload: { present: true, expires_at: '2026-12-20T00:00:00+00:00' } };
  assert.equal(P.tabAllowed(failed, 'backup'), true); assert.equal(P.tabAllowed(failed, 'overview'), true);
  assert.equal(P.tabAllowed(failed, 'loads'), false); assert.equal(P.tabAllowed(failed, 'rangers'), false);
  assert.equal(P.tabAllowed({ ...failed, status: 'ready' }, 'loads'), true);
  const tabs = P.renderTabs(failed, 'backup');
  for (const [tab, off] of [['', false], ['/loads', true], ['/rangers', true], ['/backup', false]])
    assert.equal(new RegExp('href="#/datasets/a1' + tab + '"[^>]*aria-disabled="true"').test(tabs), off, tab || 'overview');
  assert.match(P.renderDatasetPage(failed, 'backup'), /Delete the backup now/, 'the owner can still delete the backup of a dataset that never extracted');
  const src = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', '..', 'web', 'static', 'app.js'), 'utf8');
  assert.match(src, /if \(!tabAllowed\(d, tab\)\) \{ tab = 'overview';/, 'the route asks the same question as the tab bar');
  assert.doesNotMatch(src, /hasLoadTabs\(/, 'and no second rule of its own');
});
// ---- support view: support staff may open any dataset and are drawn nothing that changes it
const viewed = { ...d, mine: false, access: 'support', owner_email: 'owner@example.org', upload: { present: true, expires_at: '2099-01-01T00:00:00+00:00' } };
test('a dataset in support view says so and draws no controls, on every tab', () => {
  for (const tab of ['overview', 'loads', 'backup']) {
    const h = P.renderDatasetPage(viewed, tab, { loads: [] });
    assert.match(h, /class="support-line">.*Support view: read-only\. Owned by owner@example\.org\./, tab);
    for (const id of ['shareBtn', 'extractBtn', 'deleteBtn', 'deleteBackupBtn', 'loadBtn']) assert.ok(!h.includes('id="' + id + '"'), tab + ' ' + id);
    assert.doesNotMatch(h, /data-act="load"/, tab);
  }
  assert.match(P.renderDatasetPage(viewed, 'overview', {}), /href="\/d\/a1\/"/);   // browsing is looking
});
test('the same dataset shared with the reader keeps its Load button and has no support line', () => {
  const h = P.renderDatasetPage({ ...viewed, access: 'shared' }, 'loads', { loads: [] });
  assert.match(h, /id="loadBtn"/); assert.doesNotMatch(h, /support-line/);
});
test('a failed dataset in support view still shows its error and log', () => {
  const h = P.renderDatasetPage({ ...viewed, status: 'failed', export: [], error: 'zip is not a SMART backup', log_tail: 'the log' }, 'overview', {});
  assert.match(h, /support-line/); assert.match(h, /zip is not a SMART backup/); assert.match(h, /the log/);
});
