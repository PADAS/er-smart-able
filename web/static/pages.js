// Pure page builders: route parsing, HTML builders, status mapping. No DOM access, so Node can
// test it (tests/js). Top-level names are function declarations or var, never const/let, so the
// test shim can reach them. Loads before app.js.
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

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
