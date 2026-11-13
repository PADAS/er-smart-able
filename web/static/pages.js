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
