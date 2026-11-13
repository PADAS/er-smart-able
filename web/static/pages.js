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
function renderNotFound() {
  return '<div class="panel"><h1>Not found or not shared with you</h1><p class="muted">This dataset does not exist, or its owner has not shared it with you.</p>' +
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
