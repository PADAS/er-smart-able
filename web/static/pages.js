// Pure page builders: route parsing, HTML builders, status mapping. No DOM access, so Node can
// test it (tests/js). Top-level names are function declarations or var, never const/let, so the
// test shim can reach them. Loads before app.js.
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

function fmtBytes(n) { return n >= 1e9 ? (n / 1e9).toFixed(1) + ' GB' : n >= 1e6 ? (n / 1e6).toFixed(0) + ' MB' : n >= 1e3 ? (n / 1e3).toFixed(0) + ' kB' : n + ' B'; }

// what a load writes, in words: empty for the data model and every patrol (the default)
function loadScope(l) {
  var o = l.options || {};
  if (o.scope === 'datamodel') return 'Data model only';
  if (o.since && o.until) return 'Patrols from ' + o.since + ' to ' + o.until;
  if (o.since) return 'Patrols from ' + o.since;
  if (o.until) return 'Patrols up to ' + o.until;
  return '';
}

// ---- routes: the location hash is the truth. Ids are [A-Za-z0-9]+; anything unrecognised is home.
function parseRoute(hash) {
  var h = String(hash || '');
  var m = /^#load\/([A-Za-z0-9]+)$/.exec(h);
  if (m) return { page: 'legacy-load', load: m[1] };
  if (h === '#/sites') return { page: 'sites' };
  m = /^#\/datasets\/([A-Za-z0-9]+)(?:\/(loads|rangers))?$/.exec(h);
  if (m) return { page: 'dataset', id: m[1], tab: m[2] || 'overview' };
  m = /^#\/datasets\/([A-Za-z0-9]+)\/loads\/([A-Za-z0-9]+)$/.exec(h);
  if (m) return { page: 'load', id: m[1], load: m[2] };
  return { page: 'home' };
}
function routeHash(route) {
  switch (route && route.page) {
    case 'sites': return '#/sites';
    case 'dataset': return '#/datasets/' + route.id + (route.tab && route.tab !== 'overview' ? '/' + route.tab : '');
    case 'load': return '#/datasets/' + route.id + '/loads/' + route.load;
    case 'legacy-load': return '#load/' + route.load;
    default: return '#/';
  }
}

// ---- status: every job status maps to one of the design system's status colours (spec §8)
var STATUS_CLASS = {
  running: 'running', continuing: 'running', extracting: 'running',
  done: 'success', ready: 'success', success: 'success',
  needs_attention: 'warning', warning: 'warning', stopped: 'warning',
  failed: 'error', blocking: 'error', error: 'error',
  planned: 'ready',
  queued: 'pending', planning: 'pending', uploading: 'pending', pending: 'pending',
  interrupted: 'interrupted',
};
function statusClass(status) { return Object.prototype.hasOwnProperty.call(STATUS_CLASS, status) ? STATUS_CLASS[status] : 'pending'; }
// a pill is text plus colour, never colour alone; the label defaults to the status in words
function pill(status, label) {
  return '<span class="pill st-' + statusClass(status) + '">' + esc(label != null ? label : String(status).replace(/_/g, ' ')) + '</span>';
}

// ---- the frame: a breadcrumb under the header, the last part where the reader is
function renderBreadcrumb(parts) {
  return (parts || []).map((p, i, all) => i < all.length - 1 && p.hash
    ? '<a href="' + esc(p.hash) + '">' + esc(p.label) + '</a>'
    : '<span>' + esc(p.label) + '</span>').join('<span class="sep" aria-hidden="true">›</span>');
}

// ---- sign-in: the band without Help or the account menu, and one centred panel
function renderSignIn(config) {
  return '<section class="panel signin">' +
    '<img class="signin-lockup light-only" src="/static/img/er-lockup-h.svg" alt="EarthRanger">' +
    '<img class="signin-lockup dark-only" src="/static/img/er-lockup-white-h.svg" alt="EarthRanger">' +
    '<h1>SMART migration</h1>' +
    '<p>Upload a SMART conservation-area backup, browse it, and load it into an EarthRanger site.</p>' +
    '<p class="muted">Sign in with your ' + esc((config || {}).allowed) + ' Google account.</p>' +
    '<button id="signInBtn" class="btn primary"><span class="mi" aria-hidden="true">login</span>Sign in with Google</button>' +
    '<p id="signInError" class="tiny"></p>' +
    '</section>';
}

// ---- home: one card per dataset, newest first. The card is the link; actions live on the dataset page.
function renderDatasetCard(d) {
  var areas = (d.cas || []).map(c => esc(c.n || c.id) + ' <small>' + esc(c.id) + '</small>').join(', ');
  var counts = d.counts && d.counts.patrols != null
    ? '<div>' + Number(d.counts.patrols).toLocaleString('en-US') + ' patrols</div><div>' + Number(d.counts.waypoints || 0).toLocaleString('en-US') + ' waypoints</div>' : '';
  return '<a class="card dataset-card" href="#/datasets/' + esc(d.id) + '">' +
    '<div class="card-main">' +
      '<div class="card-title"><b>' + esc(d.name) + '</b> <span class="tiny">' + esc(d.source_name) + (d.source_size ? ' · ' + fmtBytes(d.source_size) : '') + '</span></div>' +
      '<div class="card-meta">' + pill(d.status) + (areas ? ' <span class="areas">' + areas + '</span>' : '') +
        (d.error ? ' <span class="card-error tiny">' + esc(d.error) + '</span>' : '') + '</div>' +
    '</div>' +
    '<div class="card-side tiny">' + counts + '<div>' + (d.mine ? 'you' : esc(d.owner_email)) + '</div>' +
      ((d.shared_with || []).length ? '<div class="shared-mark">shared</div>' : '') + '</div>' +
    '</a>';
}
function renderCardList(datasets) {
  var list = (datasets || []).slice().sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  return list.length ? list.map(renderDatasetCard).join('') : '<p class="empty">No datasets yet. Upload a backup or export to begin.</p>';
}
function renderHome(datasets) {
  return '<div class="page-head"><h1>Datasets</h1>' +
    '<button id="uploadBtn" class="btn primary"><span class="mi" aria-hidden="true">upload</span>Upload a backup or export</button></div>' +
    '<div id="cards" class="cards">' + renderCardList(datasets) + '</div>';
}

// ---- rangers: the people behind the subjects, for whoever creates their accounts. The table, summary,
// CSV button and help button, shared by the dataset page's tab and the load page.
function plural(n, one, many) { return Number(n).toLocaleString('en-US') + ' ' + (n === 1 ? one : (many || one + 's')); }
function renderRangersSection(l) {
  var rows = l.rangers || [], total = l.rangers_total || rows.length;
  var dmOnly = !!(l.options && l.options.scope === 'datamodel');   // imports no patrols: one count is enough
  if (!rows.length) return '';
  return '<details><summary><h3 style="display:inline">Rangers</h3> <span class="tiny">' + plural(total, 'person', 'people') + (total > rows.length ? ' (the first ' + rows.length + ' here; rangers.json has all)' : '') + ' · for their EarthRanger accounts</span> ' +
    '<button class="help" data-help="rangers-accounts" title="How to give rangers accounts"><span class="mi" aria-hidden="true">help</span></button></summary>' +
    '<p class="tiny">Create each ranger\'s user with this name and pick their subject in the user form\'s <b>linked subject</b> field, so tracks and reports from EarthRanger Mobile land on the subject that holds their patrol history. ' +
    '<button class="ghost" data-csv><span class="mi" aria-hidden="true">download</span>Download CSV</button></p>' +
    '<table class="rangers"><thead><tr><th>Name</th><th>SMART id</th><th>Active in SMART</th>' + (dmOnly ? '<th title="In the whole dataset; this load imports no patrols">Patrols (all)</th>' : '<th title="On patrols this load imports / in the whole dataset">Patrols (this load / all)</th>') + '<th>Subject</th></tr></thead><tbody>' +
    rows.map(r => '<tr><td>' + esc(r.name) + (r.deleted ? ' <span class="tiny">(employee record deleted in SMART)</span>' : '') + '</td><td class="tiny">' + esc(r.smart_employee_id || '') + '</td><td class="tiny">' + (r.active === false ? 'no' : r.active ? 'yes' : '') + '</td><td>' + (dmOnly ? esc(r.patrols_total != null ? r.patrols_total : '') : esc(r.patrols) + (r.patrols_total != null && r.patrols_total !== r.patrols ? ' <span class="tiny">/ ' + esc(r.patrols_total) + '</span>' : '')) + '</td><td class="tiny">' + (r.subject_id ? esc(r.subject_id) : 'not created yet') + '</td></tr>').join('') +
    '</tbody></table></details>';
}

// ---- the dataset page
// what: 'dataset' (the default) or 'load'; a load is shared through its dataset
function renderNotFound(what) {
  return '<div class="panel"><h1>Not found or not shared with you</h1><p class="muted">' + (what === 'load' ? 'This load does not exist, or its dataset\'s owner has not shared the dataset with you.' : 'This dataset does not exist, or its owner has not shared it with you.') + '</p>' +
    '<a class="btn primary" href="#/"><span class="mi" aria-hidden="true">arrow_back</span>Back to datasets</a></div>';
}
function fmtDate(s) { return String(s || '').slice(0, 10); }
function fmtWhen(s) { return s ? String(s).slice(0, 16).replace('T', ' ') : ''; }
function hasBundle(e) { return !!e.patrols; }
function areaName(d, dir) { var e = (d.export || []).find(x => x.dir === dir); return e ? (e.name || e.ca_id || dir) : dir; }

function renderTabs(d, tab) {
  var ready = d.status === 'ready';
  return '<nav class="tabs">' + [['overview', 'Overview', ''], ['loads', 'Loads', '/loads'], ['rangers', 'Rangers', '/rangers']].map(t => {
    var off = t[0] !== 'overview' && !ready;
    return '<a href="#/datasets/' + esc(d.id) + t[2] + '"' + (tab === t[0] ? ' class="active" aria-current="page"' : '') + (off ? ' aria-disabled="true" tabindex="-1"' : '') + '>' + t[1] + '</a>';
  }).join('') + '</nav>';
}

function renderOverview(d) {
  var running = ['running', 'queued', 'pending'].includes(d.status);
  var times = (d.started_at ? 'Started ' + esc(fmtWhen(d.started_at)) : '') + (d.finished_at ? (d.started_at ? ' · ' : '') + 'Finished ' + esc(fmtWhen(d.finished_at)) : '');
  var rows = (d.export || []).map(e => '<tr><td><b>' + esc(e.name || e.ca_id) + '</b></td><td class="tiny">' + esc(e.ca_id) + '</td><td class="tiny">' + esc(e.version || e.smart_version || d.db_version || '') + '</td>' +
    '<td class="tiny">' + (e.patrols != null ? plural(e.patrols, 'patrol') : '') + (e.waypoints != null ? ' · ' + plural(e.waypoints, 'waypoint') : '') + '</td>' +
    '<td class="actions"><a class="btn" href="/d/' + esc(d.id) + '/"><span class="mi" aria-hidden="true">travel_explore</span>Browse</a>' +
    (hasBundle(e) ? ' <button class="primary" data-act="load" data-ca="' + esc(e.dir) + '"><span class="mi" aria-hidden="true">upload</span>Load into EarthRanger</button>' : ' <span class="tiny">re-extract to enable loading</span>') + '</td></tr>').join('');
  return '<div class="panel"><h2>Extraction</h2><p>' + pill(d.status) + (times ? ' <span class="tiny">' + times + '</span>' : '') + '</p>' +
    (d.error ? '<p class="card-error">' + esc(d.error) + '</p>' : '') +
    (d.log_tail ? '<details' + (running ? ' open' : '') + '><summary class="tiny">Log' + (running ? ' (live)' : ' tail') + '</summary><pre class="log">' + esc(d.log_tail) + '</pre></details>' : '') + '</div>' +
    (rows ? '<div class="panel"><h2>Conservation areas</h2><table><thead><tr><th>Name</th><th>SMART id</th><th>Version</th><th>Contents</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '');
}

function renderLoadsTab(d, loads) {
  var list = (loads || []).slice().sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  var canLoad = (d.export || []).some(hasBundle);
  var btn = canLoad ? '<button id="loadBtn" class="primary"><span class="mi" aria-hidden="true">upload</span>Load into EarthRanger</button>' : '';
  if (!list.length) return '<div class="page-head"><h2>Loads</h2>' + btn + '</div><p class="empty">No loads yet.</p>';
  return '<div class="page-head"><h2>Loads</h2>' + btn + '</div><table><thead><tr><th>Area and site</th><th>Status</th><th>Progress</th><th>Started</th><th>By</th></tr></thead><tbody>' +
    list.map(l => {
      var p = l.progress, prog = p && p.patrols_total ? Number(p.done || 0).toLocaleString('en-US') + ' of ' + plural(p.patrols_total, 'patrol') : '';
      return '<tr data-load="' + esc(l.id) + '"><td><a href="#/datasets/' + esc(d.id) + '/loads/' + esc(l.id) + '"><b>' + esc(areaName(d, l.ca_id)) + '</b> → ' + esc(l.site ? l.site.name : 'removed site') + '</a></td>' +
        '<td>' + pill(l.status) + (l.held ? ' <span class="tiny">held</span>' : '') + '</td><td class="tiny">' + esc(prog) + '</td><td class="tiny">' + esc(fmtDate(l.created_at)) + '</td><td class="tiny">' + esc(l.owner_email || '') + '</td></tr>';
    }).join('') + '</tbody></table>';
}

function renderRangersTab(load) {
  var rows = load && load.rangers || [];
  if (!rows.length) return '<p class="empty">No rangers listed yet: a load that reaches patrol setup fills this; the viewer\'s Rangers tab lists the people in the dataset meanwhile.</p>';
  return '<p class="tiny">From the load of ' + esc(load.ca_id) + ' into ' + esc(load.site ? load.site.name : 'a removed site') + ', ' + esc(fmtDate(load.created_at)) + '</p>' + renderRangersSection(load);
}

function renderDatasetPage(d, tab, extra) {
  extra = extra || {};
  var dis = d.extract_held ? ' disabled' : '';
  var actions = d.mine ? '<div class="actions row">' +
    '<button id="shareBtn"' + dis + '><span class="mi" aria-hidden="true">share</span>Share</button>' +
    '<button id="extractBtn"' + dis + '><span class="mi" aria-hidden="true">refresh</span>Re-extract</button>' +
    '<button id="deleteBtn" class="danger"' + dis + '><span class="mi" aria-hidden="true">delete</span>Delete</button></div>' : '';
  var shared = (d.shared_with || []).length ? ' · shared with ' + d.shared_with.map(esc).join(', ') : '';
  var body = tab === 'loads' ? renderLoadsTab(d, extra.loads) : tab === 'rangers' ? renderRangersTab(extra.load) : renderOverview(d);
  return '<div class="page-head"><div><h1>' + esc(d.name) + '</h1>' +
    '<div class="tiny">' + esc(d.source_name) + (d.source_size ? ' · ' + fmtBytes(d.source_size) : '') + ' · uploaded ' + esc(fmtDate(d.created_at)) + ' · ' + (d.mine ? 'owned by you' : esc(d.owner_email)) + shared + '</div></div>' + actions + '</div>' +
    renderTabs(d, tab) + '<div id="tabBody">' + body + '</div>';
}

// ---- the load page. Time is read through now(), so a test can pin it (P.now = () => ...).
function now() { return Date.now(); }
var STAGES = ['datamodel', 'patrol_datamodel', 'preflight', 'import'];
var STAGE_LABEL = { datamodel: 'Event types', patrol_datamodel: 'Patrol setup', preflight: 'Preflight', import: 'Patrols' };
var ACTIVE = ['planning', 'queued', 'running', 'continuing'];
var FINDING_RANK = { blocking: 0, warning: 1, info: 2 };

function fmtDur(s) { s = Math.max(0, Math.round(s)); const m = Math.floor(s / 60), h = Math.floor(m / 60); return h ? h + ' h ' + (m % 60) + ' min' : m ? m + ' min ' + (s % 60) + ' s' : s + ' s'; }
function secondsSince(iso) { return iso ? (now() - Date.parse(iso)) / 1000 : null; }
function count(n, one, many) { return n.toLocaleString() + ' ' + (n === 1 ? one : (many || one + 's')); }
function notStarted(l) { return ['queued', 'planning'].includes(l.status); }   // claimed, but the job has not reset the rows yet
function loadName(l) { return l.ca_id + ' → ' + (l.site ? l.site.name : 'removed site'); }

// the heading with its status, what the load was asked to do and by whom, and the actions it offers now
function renderLoadTitle(l) {
  const active = !!l.held, stale = !active && ACTIVE.includes(l.status), o = l.options || {};
  const blocking = (l.findings || []).filter(f => f.severity === 'blocking').length;
  const facts = [l.site ? l.site.url : '', o.event_category ? 'event category ' + o.event_category : '', o.language ? 'language ' + o.language : '', loadScope(l),
    o.configurable_model ? 'configurable model ' + o.configurable_model : '', l.owner_email ? 'started by ' + l.owner_email + (l.created_at ? ', ' + fmtWhen(l.created_at) : '') : ''].filter(Boolean);
  let actions = '';
  if (!active && l.site) {
    // a plan writes nothing, so a run gets further than its plan: confirm is offered even with blocking findings
    if (l.status === 'planned') actions += '<button class="primary" data-run><span class="mi" aria-hidden="true">play_arrow</span>Confirm and load' + (blocking ? ' (stops at ' + blocking + ' blocking)' : '') + '</button>';
    if (l.status === 'needs_attention' || stale) actions += '<button class="primary" data-run><span class="mi" aria-hidden="true">play_arrow</span>Continue</button>';
    if (stale || ['planned', 'needs_attention', 'failed', 'done'].includes(l.status)) actions += '<button data-replan><span class="mi" aria-hidden="true">refresh</span>Plan again</button>';
  }
  if (!active) actions += '<button class="danger" data-del><span class="mi" aria-hidden="true">delete</span>Delete this load</button>';
  let notes = '';
  if (!active && l.site && l.status === 'planned' && blocking) notes += '<div class="tiny">The run will write what the plan lists, then stop at the ' +
    (blocking === 1 ? 'blocking finding' : blocking + ' blocking findings') + ' below until they are fixed.</div>';
  if (stale) notes += '<div class="tiny">The job stopped without reporting; continue to resume from the last checkpoint.</div>';
  if (l.error) notes += '<div class="tiny card-error">' + esc(l.error) + '</div>';
  return '<div class="title-block"><div><h1>' + esc(loadName(l)) + ' ' + pill(l.status) +
    ' <button class="help" data-help="help-statuses" title="What the statuses mean"><span class="mi" aria-hidden="true">help</span></button></h1>' +
    '<div class="tiny">' + facts.map(esc).join(' · ') + '</div></div>' +
    (actions || notes ? '<div>' + (actions ? '<div class="actions">' + actions + '</div>' : '') + notes + '</div>' : '') + '</div>';
}

// blocking first; each with its copyable values and a link to its help entry
function renderFindings(findings, status) {
  const fs = (findings || []).slice().sort((a, b) => (FINDING_RANK[a.severity] ?? 1) - (FINDING_RANK[b.severity] ?? 1));
  if (!fs.length) return ['planned', 'done'].includes(status) ? '<p class="muted tiny">No findings.</p>' : '';
  return '<h3>Findings</h3>' + fs.map(f => '<div class="finding ' + esc(f.severity) + '"><b>' + esc(f.title) + '</b> <button class="help" data-help="finding-' + esc(f.code) + '" title="How to fix this"><span class="mi" aria-hidden="true">help</span></button> <span class="tiny">' + esc(f.severity) + ' · ' + esc(STAGE_LABEL[f.stage] || f.stage) + (f.affected && f.affected.count ? ' · ' + esc(f.affected.count) + ' patrols' : '') + '</span>' +
    ((f.values || []).length ? '<div class="values">' + f.values.map(v => '<span class="value"><span class="tiny">' + esc(v.label) + '</span><code>' + esc(v.value) + '</code><button class="ghost" data-copy="' + esc(v.value) + '" title="Copy to clipboard"><span class="mi" aria-hidden="true">content_copy</span></button></span>').join('') + '</div>' : '') +
    (f.detail ? '<pre>' + esc(f.detail) + '</pre>' : '') + (f.fix ? '<div class="tiny"><b>Fix:</b> ' + esc(f.fix) + '</div>' : '') + '</div>').join('');
}

// the progress bar and import summary, the log (open while the load is active) and the load's files
function renderProgress(l, active) {
  const p = l.progress;
  return (p && p.patrols_total && l.mode !== 'plan' ? '<h3>Progress</h3><div class="bar"><div style="width:' + (100 * p.done / p.patrols_total).toFixed(1) + '%"></div></div><p class="tiny">' + esc(importSummary(l, active)) + '</p>' : '') +
    (l.continuations ? '<p class="tiny">Continued ' + esc(l.continuations) + ' time(s) past the job limit.</p>' : '') +
    (l.log_tail ? '<details' + (active ? ' open' : '') + '><summary class="tiny">Log' + (active ? ' (live)' : ' tail') + '</summary><pre class="log">' + esc(l.log_tail) + '</pre></details>' : '') +
    '<p class="tiny">Files: ' + ['plan.json', 'findings.json', 'checklist.json', 'checklist.md', 'rangers.json', 'import-ledger.json', 'log.txt'].map(n => '<a href="/api/loads/' + esc(l.id) + '/files/' + n + '" download>' + n + '</a>').join(' · ') + '</p>';
}

// the whole page; app.js swaps it in on every poll, keeping open sections, the log's scroll and an unchanged rangers table
function renderLoadPage(l, active) {
  return '<div id="loadPage">' + renderLoadTitle(l) + '<section class="panel">' + renderStages(l, active) +
    '<div id="loadFindings">' + renderFindings(l.findings, l.status) + '</div>' +
    '<div id="loadPlan">' + (l.plan ? '<h3>Plan</h3><div class="plan">' + renderPlan(l.plan) + '</div>' : '') + '</div>' +
    '<div id="loadRangers">' + renderRangersSection(l) + '</div>' +
    '<div id="loadProgress">' + renderProgress(l, active) + '</div></section></div>';
}

// ---- the stage table: one row per stage, what it did, and how long it took
function stageRows(l) {
  if (notStarted(l)) return {};
  if (l.mode) return l.stages || {};   // written by a job that records rows; empty means it has not begun one
  // loads from before the stage table have only `stage` and `status`
  if (l.stages && Object.keys(l.stages).length) return l.stages;
  const rows = {}, idx = STAGES.indexOf(l.stage);
  STAGES.forEach((s, i) => {
    if (i < idx || (i === idx && ['done', 'planned'].includes(l.status))) rows[s] = { status: 'done', metrics: {} };
    else if (i === idx) rows[s] = { status: l.status === 'failed' ? 'failed' : l.status === 'needs_attention' ? 'stopped' : 'running', metrics: {} };
  });
  return rows;
}

function stageSummary(stage, row, l, active) {
  const m = row.metrics || {}, dry = l.mode === 'plan' || (!l.mode && ['planning', 'planned'].includes(l.status));
  const v = dry ? { created: 'to create', updated: 'to update', deactivated: 'to deactivate', migrated: 'to migrate' } : { created: 'created', updated: 'updated', deactivated: 'deactivated', migrated: 'migrated' };
  v.skipped_by_mode = 'skipped by mode'; v.skipped_by_conflict = 'skipped on conflict'; v.errored = 'errored';
  const tally = (prefix, keys) => keys.filter(k => m[prefix + k]).map(k => m[prefix + k] + ' ' + (v[k] || k));
  const parts = [];
  if (stage === 'datamodel') {
    const cats = tally('categories_', ['created', 'existing']), types = tally('event_types_', ['created', 'updated', 'unchanged', 'migrated', 'skipped_by_mode', 'skipped_by_conflict', 'errored']), ch = tally('choices_', ['created', 'updated', 'unchanged', 'deactivated', 'errored']);
    if (cats.length) parts.push('categories: ' + cats.join(', '));
    if (types.length) parts.push('event types: ' + types.join(', '));
    if (ch.length) parts.push('choices: ' + ch.join(', '));
  } else if (stage === 'patrol_datamodel') {
    const types = tally('types_', ['created', 'updated', 'unchanged']), subs = tally('subjects_', ['created', 'updated', 'deactivated', 'unchanged']);
    if (types.length) parts.push('patrol types: ' + types.join(', '));
    if (subs.length) parts.push('subjects: ' + subs.join(', '));
    if (m.subjects_grouped) parts.push(m.subjects_grouped + ' in the roster group');
    if (m.schema_written) parts.push(dry ? 'patrol fields to write' : 'patrol fields written');
    else if (m.schema_skipped) parts.push('patrol fields skipped: ' + m.schema_skipped);
  } else if (stage === 'preflight') {
    if ('blocking' in m) parts.push(count(m.blocking, 'blocking finding') + ', ' + count(m.warnings || 0, 'warning') + (m.patrols != null ? ' · ' + count(m.patrols, 'patrol') + ' checked' : ''));
  } else if (stage === 'import') {
    if (dry) { if ('planned' in m) parts.push(count(m.planned, 'patrol') + ' to load' + (m.already_done ? ', ' + m.already_done + ' already done' : '')); }
    else if (l.progress && l.progress.patrols_total) parts.push(importSummary(l, active && row.status === 'running'));
  }
  return parts.join(' · ');
}

function importSummary(l, live) {
  const p = l.progress;
  const counts = (p.failed ? ', ' + p.failed + ' failed' : '') + (p.skipped ? ', ' + p.skipped + ' already there' : '');
  const of = p.done.toLocaleString() + ' of ' + p.patrols_total.toLocaleString() + ' patrols' + counts;
  const row = (l.stages || {}).import || {};
  if (!live) {   // a finished run reads as a whole: a per-minute rate would mix its two phases
    const secs = row.started_at && row.finished_at ? (Date.parse(row.finished_at) - Date.parse(row.started_at)) / 1000 : null;
    const m = row.metrics || {};
    // what this execution did (a continuation's counts are its own, not the load's): the events it wrote,
    // how many of the events it handled (written or already there) report who made them, and the ones
    // from an earlier load it gave a reporter
    const did = m.events_written != null ? ' · this execution wrote ' + count(m.events_written, 'event') +
      (m.events_reported_by ? '; ' + m.events_reported_by.toLocaleString() + ' of the events it handled report who made them' : '') +
      (m.events_reported_by_backfilled ? ', ' + m.events_reported_by_backfilled.toLocaleString() + ' of them from an earlier load, given one now' : '') : '';
    return of + (secs != null ? ' · ' + fmtDur(secs) : '') + did;
  }
  // the import runs every patrol's events, then every patrol's tracks; done restarts with each phase
  const since = p.phase ? p.phase_started_at : row.started_at;
  let s = p.phase ? (p.phase === 'tracks' ? 'Tracks: ' : 'Events: ') + of : of;
  const mins = since ? (now() - Date.parse(since)) / 60000 : null;
  const written = p.done - ((p.phase ? p.phase_skipped : p.skipped) || 0);   // skips take no time; a phase also skips what a stopped run left half done
  if (mins && mins > 0.5 && written > 0) {
    const rate = written / mins;
    s += ' · ' + rate.toFixed(1) + ' per minute';
    if (p.done < p.patrols_total) s += ' · about ' + fmtDur((p.patrols_total - p.done) / rate * 60) + ' left' + (p.phase === 'events' ? ' in this phase, then tracks' : '');
  }
  return s;
}

function renderStages(l, active) {
  const rows = stageRows(l);
  let html = '<table class="stagetable"><thead><tr><th>Stage</th><th>Status</th><th>Took</th><th>What happened</th></tr></thead><tbody>';
  for (const s of ((l.options || {}).scope === 'datamodel' ? STAGES.slice(0, 2) : STAGES)) {
    const r = rows[s], status = r ? r.status : 'pending';
    const running = status === 'running' && active;
    const took = r && r.started_at && r.finished_at ? fmtDur((Date.parse(r.finished_at) - Date.parse(r.started_at)) / 1000) : running && r.started_at ? fmtDur(secondsSince(r.started_at)) + '…' : '';
    html += '<tr class="' + esc(status) + '"><td>' + esc(STAGE_LABEL[s]) + '</td><td>' +
      pill(running ? 'running' : status === 'running' ? 'interrupted' : status, running ? 'running' : status === 'running' ? 'interrupted' : status === 'pending' && !active ? 'not reached' : status) + '</td><td class="tiny">' + esc(took) + '</td><td class="tiny">' + esc(r ? stageSummary(s, r, l, active) : '') + '</td></tr>';
  }
  html += '</tbody></table>';
  if (active) html += notStarted(l) ? '<p class="tiny heartbeat">Waiting for the job to start · ' + esc(fmtDur(secondsSince(l.claimed_at))) + ' since it was queued</p>'
    : '<p class="tiny heartbeat">' + (l.continuations ? 'Continuation ' + esc(l.continuations) + ' running for ' : 'Running for ') + esc(fmtDur(secondsSince(l.started_at || l.claimed_at))) + ' · the job last reported ' + esc(fmtDur(secondsSince(l.updated_at))) + ' ago</p>';
  return html;
}

function renderPlan(plan) {
  // opts.noIdOnCreate: the group's creates have no identifier yet (plans saved before that rule carried a placeholder there)
  const group = (title, g, opts = {}) => {
    if (!g) return '';
    const parts = [];
    for (const k of ['create', 'update', 'deactivate']) if (Array.isArray(g[k]) && g[k].length) {
      const more = typeof g.more === 'object' && g.more ? g.more[k] || 0 : (g.more || 0);   // per list now; a number in older plans
      const showValue = e => e.value && e.value !== e.label && !(opts.noIdOnCreate && k === 'create');
      parts.push('<details><summary>' + k + ' ' + g[k].length + (more ? '+' : '') + '</summary><ul>' + g[k].map(e => '<li>' + esc(e.label) + (showValue(e) ? ' <span class="tiny">' + esc(e.value) + '</span>' : '') + '</li>').join('') + (more ? '<li class="tiny">and ' + esc(more) + ' more</li>' : '') + '</ul></details>');
    }
    if (g.unchanged) parts.push('<span class="tiny">' + esc(g.unchanged) + ' unchanged</span>');
    return '<div><b>' + title + '</b> ' + (parts.join(' ') || '<span class="tiny">nothing to do</span>') + '</div>';
  };
  const p = plan.patrols;   // absent from a data-model-only plan
  return group('Event categories', plan.event_categories) + group('Event types', plan.event_types) + group('Patrol types', plan.patrol_types) +
    '<div><b>Universal patrol fields</b> ' + esc(plan.universal_patrol_fields) + '</div>' + group('Choices', plan.choices) + group('Subjects', plan.subjects, { noIdOnCreate: true }) +
    '<div><b>Roster</b> ' + (plan.roster && plan.roster.group ? esc(plan.roster.group) + ': ' : '') + esc((plan.roster || {}).add || 0) + ' to add</div>' +
    (!p ? '<div><b>Patrols</b> <span class="tiny">none: this load is the data model only</span></div>' :
    '<div><b>Patrols</b> ' + esc(p.total) + (p.first ? ' from ' + esc(p.first) + ' to ' + esc(p.last) : '') + (p.already_done ? ', ' + esc(p.already_done) + ' already imported' : '') + ' · ' + esc(p.events) + ' observations · ' + esc(p.track_points) + ' track points</div>');
}
