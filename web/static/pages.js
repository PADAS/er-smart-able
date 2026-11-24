// Pure page builders: route parsing, HTML builders, status mapping. No DOM access, so Node can
// test it (tests/js). Top-level names are function declarations or var, never const/let, so the
// test shim can reach them. Loads before app.js.
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

function fmtBytes(n) {
  return n >= 1e9 ? t('units.gb', { n: (n / 1e9).toFixed(1) }) : n >= 1e6 ? t('units.mb', { n: (n / 1e6).toFixed(0) })
    : n >= 1e3 ? t('units.kb', { n: (n / 1e3).toFixed(0) }) : t('units.b', { n: n });
}

// what a load writes, in words (plain text: the caller escapes it): empty for the data model and every patrol (the default)
function loadScope(l) {
  var o = l.options || {};
  if (o.scope === 'datamodel') return t('dataset.scopeDatamodel');
  if (o.since && o.until) return t('dataset.scopeRange', { since: o.since, until: o.until });
  if (o.since) return t('dataset.scopeSince', { since: o.since });
  if (o.until) return t('dataset.scopeUntil', { until: o.until });
  return '';
}

// the words for a failed API call, as plain text for alert or textContent: in the reader's language when the
// server's code has a message, else the server's own English, else a generic line, else the status text.
// `values` are data from the server; t() inserts them as text.
function errorMessage(status, statusText, body) {
  var b = body && typeof body === 'object' ? body : {};
  var values = b.values && typeof b.values === 'object' ? b.values : {};
  if (typeof b.code === 'string' && hasMessage('errors.' + b.code)) return t('errors.' + b.code, values);
  if (typeof b.detail === 'string' && b.detail) return b.detail;
  if (b.code === 'invalid_request' || Array.isArray(b.detail)) return t('errors.invalid_request');
  return statusText || String(status);
}

// ---- routes: the location hash is the truth. Ids are [A-Za-z0-9]+; anything unrecognised is home.
function parseRoute(hash) {
  var h = String(hash || '');
  var m = /^#load\/([A-Za-z0-9]+)$/.exec(h);
  if (m) return { page: 'legacy-load', load: m[1] };
  if (h === '#/sites') return { page: 'sites' };
  if (h === '#/help') return { page: 'home', help: true };   // the data browser's Help: the list, with the help open
  m = /^#\/datasets\/([A-Za-z0-9]+)(?:\/(loads|rangers|backup))?$/.exec(h);
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
// a pill is text plus colour, never colour alone; the label defaults to the status in words (translated when the language has them)
function pill(status, label) {
  var words = label != null ? label : hasMessage('status.' + status) ? t('status.' + status) : String(status).replace(/_/g, ' ');
  return '<span class="pill st-' + statusClass(status) + '">' + esc(words) + '</span>';
}

// ---- the frame: what the sidebar (nav.js) shows for a route. route and me are null when signed out;
// extra: { dataset, lang, languages, theme, version, open }. A dataset not fetched yet (or refused) gives the
// list form with nothing marked. The name goes whole: the stylesheet cuts a long one.
function railState(route, me, extra) {
  extra = extra || {};
  var d = me && route && (route.page === 'dataset' || route.page === 'load') ? extra.dataset : null;
  var current = !me || !route ? null : route.page === 'home' ? 'home' : route.page === 'sites' ? 'sites'
    : !d ? null : route.page === 'load' ? 'migration:loads' : !route.tab || route.tab === 'overview' ? 'overview' : 'migration:' + route.tab;
  return { doc: 'app', hosted: true, signedIn: !!me, current: current, open: extra.open !== false,
    dataset: d ? { id: d.id, name: d.name, ready: d.status === 'ready', loadTabs: hasLoadTabs(d) } : null,
    lang: extra.lang || 'en', languages: extra.languages || [], theme: extra.theme || 'system', email: me && me.email || '', version: extra.version || '' };
}

// ---- sign-in: the band without Help or the account menu, and one centred panel
// The allow-list (whole addresses and @domain suffixes) as a phrase, in the language's own word order:
// "your @earthranger.com Google account", "a Google account at @a.org or @b.org", or "your Google account"
// when anyone may sign in. Returns HTML (the addresses are escaped).
function allowedPhrase(allowed) {
  const list = Array.isArray(allowed) ? allowed.filter(Boolean) : typeof allowed === 'string' && allowed ? [allowed] : [];
  if (!list.length) return T('signin.yourAccount');
  if (list.length === 1) return T('signin.yourDomainAccount', { domain: list[0] });
  return T('signin.accountAt', { list: list.slice(0, -1).join(', '), last: list[list.length - 1] });
}

function renderSignIn(config) {
  return '<section class="panel signin">' +
    '<img class="signin-lockup light-only" src="/static/img/er-lockup-h.svg" alt="EarthRanger">' +
    '<img class="signin-lockup dark-only" src="/static/img/er-lockup-white-h.svg" alt="EarthRanger">' +
    '<h1>' + T('shell.appName') + '</h1>' +
    '<p>' + T('signin.intro') + '</p>' +
    '<p class="muted">' + T('signin.prompt', null, { who: allowedPhrase((config || {}).allowed) }) + '</p>' +
    '<button id="signInBtn" class="btn primary"><span class="mi" aria-hidden="true">login</span>' + T('signin.button') + '</button>' +
    '<p id="signInError" class="tiny"></p>' +
    '</section>';
}

// ---- home: one card per dataset, newest first. The card is the link; actions live on the dataset page.
function renderDatasetCard(d) {
  var areas = (d.cas || []).map(c => esc(c.n || c.id) + ' <small>' + esc(c.id) + '</small>').join(', ');
  var counts = d.counts && d.counts.patrols != null
    ? '<div>' + tn('units.patrols', Number(d.counts.patrols)) + '</div><div>' + tn('units.waypoints', Number(d.counts.waypoints || 0)) + '</div>' : '';
  return '<a class="card dataset-card" href="#/datasets/' + esc(d.id) + '">' +
    '<div class="card-main">' +
      '<div class="card-title"><b>' + esc(d.name) + '</b> <span class="tiny">' + esc(d.source_name) + (d.source_size ? ' · ' + esc(fmtBytes(d.source_size)) : '') + '</span></div>' +
      '<div class="card-meta">' + pill(d.status) + (areas ? ' <span class="areas">' + areas + '</span>' : '') +
        (d.error ? ' <span class="card-error tiny">' + esc(d.error) + '</span>' : '') + '</div>' +
    '</div>' +
    '<div class="card-side tiny">' + counts + '<div>' + (d.mine ? T('home.you') : esc(d.owner_email)) + '</div>' +
      ((d.shared_with || []).length ? '<div class="shared-mark">' + T('home.shared') + '</div>' : '') + '</div>' +
    '</a>';
}
function renderCardList(datasets) {
  var list = (datasets || []).slice().sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  return list.length ? list.map(renderDatasetCard).join('') : '<p class="empty">' + T('home.empty') + '</p>';
}
// The home page: the datasets, then the EarthRanger sites they are loaded into. sites is null when
// they could not be fetched; the section then says why (sitesError) and the datasets still show.
// opts.support: the reader is support staff, who get a switch to list every user's datasets and sites
// (opts.all: it is on). Nobody else is shown it, and the server ignores the request from anyone else.
// the switch support staff have on the datasets and the sites pages: everyone's, or their own
function allUsersSwitch(opts) {
  return opts && opts.support ? '<label class="switch" title="' + T('home.allUsersTitle') + '"><input type="checkbox" id="allUsers"' + (opts.all ? ' checked' : '') + '>' + T('home.allUsers') + '</label>' : '';
}
// the upload form's Upload button: on with a file chosen, and off while an upload is on its way
function canUpload(file, uploading) { return !!file && !uploading; }

function renderHome(datasets, opts) {
  return '<div class="page-head"><h1>' + T('home.title') + '</h1>' + allUsersSwitch(opts) +
    '<button id="uploadBtn" class="btn primary"><span class="mi" aria-hidden="true">upload</span>' + T('home.upload') + '</button></div>' +
    '<div id="cards" class="cards">' + renderCardList(datasets) + '</div>';
}

// One section of the help drawer. s.html is the server's rendering of a help page. A section in another
// language than the reader's (the quirks reference, or a page with no translation yet) is marked with
// its language and says, in the reader's language, that it is only in English.
function helpSection(s) {
  var other = s.lang !== currentLang();
  return '<section id="help-' + esc(s.id) + '"' + (other ? ' lang="' + esc(s.lang) + '"' : '') + '><h2>' + esc(s.title) + '</h2>' +
    (other ? '<p class="tiny muted" lang="' + esc(currentLang()) + '">' + T('help.englishOnly') + '</p>' : '') + s.html + '</section>';
}

// The load page keeps its rangers table across refreshes while this key is unchanged (so a sort or a
// scroll survives a poll). The table's words are part of what is kept, so the key names the language:
// a change of language builds the table again.
function rangersKey(l) {
  var rows = l.rangers || [];
  return rows.length ? currentLang() + ':' + l.id + ':' + (l.rangers_total || rows.length) + ':' + JSON.stringify(rows) : '';
}


// ---- rangers: the people behind the subjects, for whoever creates their accounts. The table, summary,
// CSV button and help button, shared by the dataset page's tab (open) and the load page (closed).
function renderRangersSection(l, open) {
  var rows = l.rangers || [], total = l.rangers_total || rows.length;
  var dmOnly = !!(l.options && l.options.scope === 'datamodel');   // imports no patrols: one count is enough
  if (!rows.length) return '';
  return '<details' + (open ? ' open' : '') + '><summary><h3 style="display:inline">' + T('rangers.title') + '</h3> <span class="tiny">' + tn('rangers.people', total) +
    (total > rows.length ? ' ' + T('rangers.firstOnly', { shown: rows.length, file: 'rangers.json' }) : '') + ' · ' + T('rangers.forAccounts') + '</span> ' +
    '<button class="help" data-help="rangers-accounts" title="' + T('rangers.helpTitle') + '"><span class="mi" aria-hidden="true">help</span></button></summary>' +
    '<p class="tiny">' + T('rangers.createUser', null, { field: '<b>' + T('rangers.linkedSubject') + '</b>' }) + ' ' +
    '<button class="ghost" data-csv><span class="mi" aria-hidden="true">download</span>' + T('rangers.downloadCsv') + '</button></p>' +
    '<table class="rangers"><thead><tr><th>' + T('rangers.colName') + '</th><th>' + T('rangers.colSmartId') + '</th><th>' + T('rangers.colActive') + '</th>' +
    (dmOnly ? '<th title="' + T('rangers.colPatrolsAllTitle') + '">' + T('rangers.colPatrolsAll') + '</th>' : '<th title="' + T('rangers.colPatrolsTitle') + '">' + T('rangers.colPatrols') + '</th>') + '<th>' + T('rangers.colSubject') + '</th></tr></thead><tbody>' +
    rows.map(r => '<tr><td>' + esc(r.name) + (r.deleted ? ' <span class="tiny">' + T('rangers.deleted') + '</span>' : '') + '</td><td class="tiny">' + esc(r.smart_employee_id || '') + '</td><td class="tiny">' + (r.active === false ? T('rangers.no') : r.active ? T('rangers.yes') : '') + '</td><td>' + (dmOnly ? esc(r.patrols_total != null ? r.patrols_total : '') : esc(r.patrols) + (r.patrols_total != null && r.patrols_total !== r.patrols ? ' <span class="tiny">/ ' + esc(r.patrols_total) + '</span>' : '')) + '</td><td class="tiny">' + (r.subject_id ? esc(r.subject_id) : T('rangers.notCreated')) + '</td></tr>').join('') +
    '</tbody></table></details>';
}

// ---- the dataset page
// what: 'dataset' (the default) or 'load'; a load is shared through its dataset
// Shown on a dataset or load the reader reaches only as support staff: they may look, and the page
// draws none of its controls (the server refuses them in any case).
function supportLine(owner) { return '<p class="support-line"><span class="mi" aria-hidden="true">visibility</span>' + T('support.line', { owner: owner || '' }) + '</p>'; }
function renderNotFound(what) {
  return '<div class="panel"><h1>' + T('dataset.notFoundTitle') + '</h1><p class="muted">' + T(what === 'load' ? 'dataset.notFoundLoad' : 'dataset.notFoundDataset') + '</p>' +
    '<a class="btn primary" href="#/"><span class="mi" aria-hidden="true">arrow_back</span>' + T('dataset.backToDatasets') + '</a></div>';
}
function fmtDate(s) { return String(s || '').slice(0, 10); }
function fmtWhen(s) { return s ? String(s).slice(0, 16).replace('T', ' ') : ''; }
// every export entry has a bundle (a zero-patrol area loads its data model); legacy cas rows have no dir
function hasBundle(e) { return !!(e && e.dir); }
// Loads and Rangers open once an extraction has produced an export, so a failed re-extract keeps them
function hasLoadTabs(d) { return !!((d.export || []).length || d.status === 'ready'); }
// Whether a tab of the dataset page can be opened. Loads and Rangers need something extracted; Overview
// and Backup are there whatever the extraction did. The tab bar and the route both ask this, so a tab
// that is offered is a tab that opens.
function tabAllowed(d, tab) { return !(tab === 'loads' || tab === 'rangers') || hasLoadTabs(d); }
function areaName(d, dir) { var e = (d.export || []).find(x => x.dir === dir); return e ? (e.name || e.ca_id || dir) : dir; }

// ---- the sites page. Only the token hint is shown; the token itself never reaches the page.
// ---- sites: a page of their own. A row per site; its owner can edit, share and remove it.
// sites null: they could not be fetched, and error says why.
function renderSitesPage(sites, error, opts) {
  if (sites) return renderSites(sites, opts);
  return '<section id="sites"><div class="page-head"><h1>' + T('shell.sites') + '</h1>' + allUsersSwitch(opts) + '</div><p class="empty">' + esc(error) + '</p></section>';
}
function renderSites(sites, opts) {
  var rows = (sites || []).map(s => '<tr>' +
    '<td><b>' + esc(s.name) + '</b><div class="tiny">' + esc(s.url) + '</div></td>' +
    '<td class="tiny">' + (s.token_hint ? T('sites.tokenAs', { hint: s.token_hint, user: s.checked_as }) : s.checked_as ? T('sites.checkedAs', { user: s.checked_as }) : '—') + '</td>' +
    '<td>' + (s.mine ? T('sites.you') : esc(s.owner_email)) + '</td>' +
    '<td>' + ((s.shared_with || []).map(esc).join('<br>') || '<span class="tiny">—</span>') + '</td>' +
    '<td class="actions">' + (s.mine ?
      '<button data-act="siteEdit" data-id="' + esc(s.id) + '"><span class="mi" aria-hidden="true">edit</span>' + T('sites.edit') + '</button>' +
      '<button data-act="siteShare" data-id="' + esc(s.id) + '"><span class="mi" aria-hidden="true">share</span>' + T('sites.share') + '</button>' +
      '<button data-act="siteDelete" data-id="' + esc(s.id) + '" class="danger" title="' + T('sites.removeTitle') + '"><span class="mi" aria-hidden="true">delete</span>' + T('sites.remove') + '</button>' : '') + '</td></tr>').join('');
  return '<section id="sites"><div class="page-head"><h1>' + T('shell.sites') + '</h1>' + allUsersSwitch(opts) +
    '<button id="addSiteBtn" class="btn"><span class="mi" aria-hidden="true">add</span>' + T('sites.add') + '</button></div>' +
    ((sites || []).length ? '<div class="panel"><table><thead><tr><th>' + T('sites.colSite') + '</th><th>' + T('sites.colToken') + '</th><th>' + T('sites.colOwner') + '</th><th>' + T('sites.colShared') + '</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>'
      : '<p class="empty">' + T('sites.empty') + '</p>') + '</section>';
}
// The edit-a-site form. The name is the site's; the address is shown, not asked for (another address
// is another site); the token field is empty and stays optional: filled in, it replaces the token.
function siteEditBody(s) {
  return '<p class="muted tiny">' + T('siteEdit.hint') + '</p>' +
    '<form id="siteForm" class="col" autocomplete="off">' +
    '<label class="field"><span>' + T('siteDialog.name') + '</span><input type="text" id="siteName" required value="' + esc(s.name) + '"></label>' +
    '<div class="field"><span>' + T('siteDialog.host') + '</span><div><code>' + esc(s.url) + '</code> <span class="tiny">' + T('sites.tokenAs', { hint: s.token_hint, user: s.checked_as }) + '</span></div></div>' +
    '<label class="field"><span>' + T('siteEdit.token') + '</span><input type="password" id="siteToken" autocomplete="off" placeholder="' + T('siteEdit.tokenKeep') + '"></label>' +
    '<p class="tiny" id="siteError" role="alert"></p>' +
    '<div class="row right"><button type="button" class="ghost" data-close>' + T('shell.close') + '</button><button type="submit" class="primary" id="siteBtn">' + T('siteEdit.submit') + '</button></div></form>';
}
// the link into the data browser, which is not translated: another language is told so beside it
function browseLink(d) {
  return '<a class="btn" href="/d/' + esc(d.id) + '/"><span class="mi" aria-hidden="true">travel_explore</span>' + T('dataset.browse') + '</a>' +
    (currentLang() !== 'en' ? ' <span class="tiny">' + T('dataset.browseInEnglish') + '</span>' : '');
}

function renderOverview(d) {
  var running = !!d.extract_held;   // queued or running, and its job still holding
  var lapsed = ['queued', 'running'].includes(d.status) && !running;   // the job was killed outright and never reported
  var times = (d.started_at ? T('dataset.started', { when: fmtWhen(d.started_at) }) : '') + (d.finished_at ? (d.started_at ? ' · ' : '') + T('dataset.finished', { when: fmtWhen(d.finished_at) }) : '');
  // datasets extracted before the bundle existed have no export entries: list their areas from cas, browsable but not loadable
  var areaRows = (d.export || []).length ? d.export : (d.status === 'ready' ? (d.cas || []).map(c => ({ ca_id: c.id, name: c.n })) : []);
  var rows = areaRows.map(e => '<tr><td><b>' + esc(e.name || e.ca_id) + '</b></td><td class="tiny">' + esc(e.ca_id) + '</td><td class="tiny">' + esc(e.version || e.smart_version || d.db_version || '') + '</td>' +
    '<td class="tiny">' + (e.patrols != null ? tn('units.patrols', e.patrols) : '') + (e.waypoints != null ? ' · ' + tn('units.waypoints', e.waypoints) : '') + '</td>' +
    '<td class="actions"><div class="area-actions">' + (d.status === 'ready' ? browseLink(d) : '') +   // the viewer answers 409 unless ready
    (d.extract_held || d.access === 'support' ? '' : hasBundle(e) ? ' <button class="primary" data-act="load" data-ca="' + esc(e.dir) + '"><span class="mi" aria-hidden="true">upload</span>' + T('dataset.load') + '</button>' : ' <span class="tiny">' + T('dataset.reExtractToLoad') + '</span>') + '</div></td></tr>').join('');
  return '<div class="panel"><h2>' + T('dataset.extraction') + '</h2><p>' + pill(d.status) + (times ? ' <span class="tiny">' + times + '</span>' : '') + '</p>' +
    (d.error ? '<p class="card-error">' + esc(d.error) + '</p>' : '') + backupReminder(d) +
    (lapsed ? '<p class="tiny">' + T('dataset.lapsed') + (d.mine ? ' ' + T('dataset.lapsedRetry', {}, { action: T('dataset.reExtract') }) : '') + '</p>' : '') +
    (d.log_tail ? '<details' + (running ? ' open' : '') + '><summary class="tiny">' + T(running ? 'dataset.logLive' : 'dataset.logTail') + '</summary><pre class="log">' + esc(d.log_tail) + '</pre></details>' : '') + '</div>' +
    (!rows && d.status === 'ready' ? '<div class="panel"><h2>' + T('dataset.areas') + '</h2><p class="tiny">' + T('dataset.noAreas') + '</p>' + browseLink(d) + '</div>' : '') +
    (rows ? '<div class="panel"><h2>' + T('dataset.areas') + '</h2><table><thead><tr><th>' + T('dataset.colName') + '</th><th>' + T('dataset.colSmartId') + '</th><th>' + T('dataset.colVersion') + '</th><th>' + T('dataset.colContents') + '</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '');
}

// ---- the uploaded backup: stored apart from what was extracted from it, and only for a time. The panel
// says when it goes and that the extracted data does not go with it; the owner can delete it at once.
function daysUntil(iso) { return Math.ceil((Date.parse(iso) - now()) / 86400000); }
function backupPanel(d) {
  var u = d.upload;
  if (!u || d.status === 'uploading') return '';   // not asked for (the list), or still arriving
  var state;
  if (!u.present) state = u.deleted_at ? T('backup.deletedOn', { date: fmtDate(u.deleted_at) }) : T('backup.gone');
  else if (!u.expires_at) state = T('backup.kept');
  else { var n = daysUntil(u.expires_at); state = n > 0 ? tn('backup.expires', n, { date: fmtDate(u.expires_at) }) : T('backup.expiresSoon'); }
  return '<div class="panel" id="backup"><h2>' + T('backup.title') + '</h2>' +
    '<p><span class="tiny">' + esc(d.source_name) + (d.source_size ? ' · ' + esc(fmtBytes(d.source_size)) : '') + '</span></p>' +
    '<p>' + state + (u.present ? '' : ' ' + T('backup.reupload')) + '</p>' +
    '<p class="tiny">' + T('backup.extractedStays') + '</p>' +
    // the owner uploads it again: the same backup once it has gone, or a newer one in place of the one stored
    (d.mine ? '<div class="row"><button id="reuploadBtn"' + (d.extract_held ? ' disabled' : '') + '><span class="mi" aria-hidden="true">upload</span>' + T(u.present ? 'backup.replace' : 'backup.uploadAgain') + '</button>' +
      (u.present ? '<button id="deleteBackupBtn" class="danger"' + (d.extract_held ? ' disabled' : '') + '><span class="mi" aria-hidden="true">delete</span>' + T('backup.deleteNow') + '</button>' : '') + '</div>' : '') +
    '</div>';
}
// The Overview's one line about the backup, which has its own tab: only when it goes within a week,
// is due to go, or has gone. Otherwise the expiry would not be seen until someone thought to look.
function backupReminder(d) {
  var u = d.upload;
  if (!u || d.status === 'uploading') return '';
  var text;
  if (!u.present) text = T('backup.reminderGone');
  else if (!u.expires_at) return '';
  else { var n = daysUntil(u.expires_at); if (n > 7) return ''; text = n > 0 ? tn('backup.reminderSoon', n) : T('backup.reminderDue'); }
  return '<p class="tiny backup-reminder">' + text + ' <a href="#/datasets/' + esc(d.id) + '/backup">' + T('dataset.tabBackup') + '</a></p>';
}
// A dialog that asks before deleting: what goes, that it cannot be undone, Cancel first (it takes the focus).
function confirmBody(lines, go) {
  return lines.map(l => '<p>' + l + '</p>').join('') + '<p><b>' + T('confirm.cannotUndo') + '</b></p>' +
    '<div class="row right"><button type="button" class="ghost" data-close>' + T('confirm.cancel') + '</button>' +
    '<button type="button" class="danger" id="confirmGo"><span class="mi" aria-hidden="true">delete</span>' + go + '</button></div>';
}
function deleteDatasetBody() { return confirmBody([T('confirm.deleteDatasetWhat'), T('confirm.nothingInEr')], T('confirm.deleteDatasetGo')); }
function deleteBackupBody(d) { return confirmBody([T('confirm.deleteBackupWhat', { file: d.source_name }), T('confirm.deleteBackupAfter')], T('confirm.deleteBackupGo')); }

function renderLoadsTab(d, loads) {
  var list = (loads || []).slice().sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  var canLoad = d.access !== 'support' && !d.extract_held && (d.export || []).some(hasBundle);   // an extraction rewrites the bundle a load reads
  var btn = canLoad ? '<button id="loadBtn" class="primary"><span class="mi" aria-hidden="true">upload</span>' + T('dataset.load') + '</button>' : '';
  if (!list.length) return '<div class="page-head"><h2>' + T('dataset.tabLoads') + '</h2>' + btn + '</div><p class="empty">' + T('dataset.noLoads') + '</p>';
  return '<div class="page-head"><h2>' + T('dataset.tabLoads') + '</h2>' + btn + '</div><div class="panel"><table><thead><tr><th>' + T('dataset.colAreaSite') + '</th><th>' + T('dataset.colStatus') + '</th><th>' + T('dataset.colProgress') + '</th><th>' + T('dataset.colStarted') + '</th><th>' + T('dataset.colBy') + '</th></tr></thead><tbody>' +
    list.map(l => {
      var p = l.progress, prog = p && p.patrols_total ? T('dataset.progress', { done: fmtNum(p.done || 0) }, { total: tn('units.patrols', p.patrols_total) }) : '';
      return '<tr data-load="' + esc(l.id) + '"><td><a href="#/datasets/' + esc(d.id) + '/loads/' + esc(l.id) + '"><b>' + esc(areaName(d, l.ca_id)) + '</b> → ' + (l.site ? esc(l.site.name) : T('dataset.removedSite')) + '</a></td>' +
        '<td>' + pill(l.status) + (l.held ? ' <span class="tiny">' + T('dataset.held') + '</span>' : '') + (loadScope(l) ? '<div class="tiny">' + esc(loadScope(l)) + '</div>' : '') + '</td><td class="tiny">' + prog + '</td><td class="tiny">' + esc(fmtDate(l.created_at)) + '</td><td class="tiny">' + esc(l.owner_email || '') + '</td></tr>';
    }).join('') + '</tbody></table></div>';
}

function renderRangersTab(load) {
  var rows = load && load.rangers || [];
  if (!rows.length) return '<p class="empty">' + T('rangers.empty') + '</p>';
  return '<p class="tiny">' + T('rangers.fromLoad', { area: load.ca_id, date: fmtDate(load.created_at) }, { site: load.site ? esc(load.site.name) : T('rangers.removedSite') }) + '</p><div class="panel">' + renderRangersSection(load, true) + '</div>';
}

function renderDatasetPage(d, tab, extra) {
  extra = extra || {};
  var dis = d.extract_held ? ' disabled' : '';
  var actions = d.mine ? '<div class="actions row">' +
    '<button id="shareBtn"><span class="mi" aria-hidden="true">share</span>' + T('dataset.share') + '</button>' +
    (d.upload && !d.upload.present && d.status !== 'uploading' ? '' :   // nothing to extract from once the backup has gone
    '<button id="extractBtn"' + dis + '><span class="mi" aria-hidden="true">refresh</span>' + T('dataset.reExtract') + '</button>') +
    '<button id="deleteBtn" class="danger"' + dis + '><span class="mi" aria-hidden="true">delete</span>' + T('dataset.delete') + '</button></div>' : '';
  var shared = (d.shared_with || []).length ? ' · ' + T('dataset.sharedWith', { list: d.shared_with.join(', ') }) : '';
  var body = tab === 'loads' ? renderLoadsTab(d, extra.loads) : tab === 'rangers' ? renderRangersTab(extra.load)
    : tab === 'backup' ? (backupPanel(d) || '<div class="panel"><p class="tiny">' + T(d.status === 'uploading' ? 'backup.uploading' : 'backup.unknown') + '</p></div>') : renderOverview(d);
  return '<div class="page-head"><div><h1>' + esc(d.name) + '</h1>' +
    '<div class="tiny">' + esc(d.source_name) + (d.source_size ? ' · ' + esc(fmtBytes(d.source_size)) : '') + ' · ' + T('dataset.uploaded', { date: fmtDate(d.uploaded_at || d.created_at) }) + ' · ' + (d.mine ? T('dataset.ownedByYou') : esc(d.owner_email)) + shared + '</div>' + (d.access === 'support' ? supportLine(d.owner_email) : '') + '</div>' + actions + '</div>' +
    '<div id="tabBody">' + body + '</div>';
}

// ---- the load page. Time is read through now(), so a test can pin it (P.now = () => ...).
function now() { return Date.now(); }
var STAGES = ['datamodel', 'patrol_datamodel', 'preflight', 'import'];
var ACTIVE = ['planning', 'queued', 'running', 'continuing'];
var FINDING_RANK = { blocking: 0, warning: 1, info: 2 };
// the verbs that read "to create" rather than "created" while a plan has not run
var DRY_VERBS = ['created', 'updated', 'deactivated', 'migrated'];

function fmtDur(s) {
  s = Math.max(0, Math.round(s)); const m = Math.floor(s / 60), h = Math.floor(m / 60);
  return h ? t('units.hoursMinutes', { h: h, m: m % 60 }) : m ? t('units.minutesSeconds', { m: m, s: s % 60 }) : t('units.seconds', { s: s });
}
function secondsSince(iso) { return iso ? (now() - Date.parse(iso)) / 1000 : null; }
function notStarted(l) { return ['queued', 'planning'].includes(l.status); }   // claimed, but the job has not reset the rows yet
// plain text: the caller escapes it
function loadName(l) { return t('load.name', { area: l.ca_id, site: l.site ? l.site.name : t('dataset.removedSite') }); }

// the heading with its status, what the load was asked to do and by whom, and the actions it offers now
// the facts under a load's title, as plain text: the title block escapes each one (facts.map(esc))
function loadFacts(l) {
  const o = l.options || {}, set = l.event_type_set || {};
  // once the job has looked at the site: the category its event types are really in, and whether this
  // conservation area keeps event types of its own from before areas shared them
  return [l.site ? l.site.url : '', set.category ? t('load.setCategory', { value: set.category }) : o.event_category ? t('load.eventCategory', { value: o.event_category }) : '', o.language ? t('load.language', { value: o.language }) : '', loadScope(l),
    o.configurable_model ? t('load.configurableModel', { value: o.configurable_model }) : '',
    set.old ? t('load.oldSet') : (set.name || o.event_type_set) ? t('load.eventTypeSet', { value: set.name || o.event_type_set }) : '',   // set.name: a load made before set names has no option, and the job gave it the model's
    o.existing_event_types === 'keep' ? t('load.existingKeep') : o.existing_event_types === 'update' ? t('load.existingUpdate') : '',
    l.owner_email ? (l.created_at ? t('load.startedByWhen', { who: l.owner_email, when: fmtWhen(l.created_at) }) : t('load.startedBy', { who: l.owner_email })) : ''].filter(Boolean);
}
function renderLoadTitle(l) {
  const active = !!l.held, stale = !active && ACTIVE.includes(l.status), o = l.options || {};
  const blocking = (l.findings || []).filter(f => f.severity === 'blocking').length;
  const facts = loadFacts(l);
  let actions = '';
  const busy = l.dataset_extracting ? ' disabled title="' + T('load.extractingTitle') + '"' : '';   // the server refuses a run or a plan meanwhile
  const viewing = l.access === 'support';   // support staff look; they are offered nothing that acts
  if (!active && l.site && !viewing) {
    // a plan writes nothing, so a run gets further than its plan: confirm is offered even with blocking findings
    if (l.status === 'planned') actions += '<button class="primary" data-run' + busy + '><span class="mi" aria-hidden="true">play_arrow</span>' + (blocking ? T('load.confirmStops', { n: fmtNum(blocking) }) : T('load.confirm')) + '</button>';
    if (l.status === 'needs_attention' || stale) actions += '<button class="primary" data-run' + busy + '><span class="mi" aria-hidden="true">play_arrow</span>' + T('load.continue') + '</button>';
    if (stale || ['planned', 'needs_attention', 'failed', 'done'].includes(l.status)) actions += '<button data-replan' + busy + '><span class="mi" aria-hidden="true">refresh</span>' + T('load.planAgain') + '</button>';
  }
  if (!active && !viewing) actions += '<button class="danger" data-del><span class="mi" aria-hidden="true">delete</span>' + T('load.delete') + '</button>';
  let notes = '';
  if (!active && l.site && l.status === 'planned' && blocking) notes += '<div class="tiny">' + tn('load.stopsAt', blocking) + '</div>';
  if (busy && !active && l.site && !viewing) notes += '<div class="tiny">' + T('load.extractingNote') + '</div>';
  if (stale) notes += '<div class="tiny">' + T(viewing ? 'load.staleView' : 'load.stale') + '</div>';   // a viewer has no Continue to press
  if (l.error) notes += '<div class="tiny card-error">' + esc(l.error) + '</div>';
  return '<div class="title-block"><div><h1>' + esc(loadName(l)) + ' ' + pill(l.status) +
    ' <button class="help" data-help="help-statuses" title="' + T('load.statusesHelp') + '"><span class="mi" aria-hidden="true">help</span></button></h1>' +
    '<div class="tiny">' + facts.map(esc).join(' · ') + '</div>' + (viewing ? supportLine(l.owner_email) : '') + '</div>' +
    (actions || notes ? '<div>' + (actions ? '<div class="actions">' + actions + '</div>' : '') + notes + '</div>' : '') + '</div>';
}

// blocking first; each with its copyable values and a link to its help entry.
// The frame is translated, and so is a finding the server named (see findingText); its detail lines and copyable values are data, shown as stored.
// The words of one finding, as HTML-safe text: { title, fix, translated }. A finding is stored in
// English (f.title, f.fix). Where the server named its message (f.key) and the reader's language is
// not English, the title and fix are that message, filled from f.params; if the message is missing or
// leaves a placeholder unfilled, the stored English is shown whole. An English reader sees the stored
// text as it always was.
function findingText(f) {
  var stored = { title: esc(f.title), fix: esc(f.fix), translated: false };
  if (currentLang() === 'en' || typeof f.key !== 'string') return stored;
  var base = 'findingText.' + f.key, p = f.params || {}, counted = hasMessage(base + '.title_other');
  if (!(counted || hasMessage(base + '.title')) || !hasMessage(base + '.fix')) return stored;
  if (counted && typeof p.count !== 'number') return stored;
  var title = counted ? tn(base + '.title', p.count, p) : T(base + '.title', p), fix = T(base + '.fix', p);
  if (title.indexOf('{{') !== -1 || fix.indexOf('{{') !== -1) return stored;   // a value the sentence needs is missing
  if (f.created_by_run) title = T('findings.createdByRun', {}, { title: title });
  return { title: title, fix: fix, translated: true };
}
function renderFindings(findings, status) {
  const fs = (findings || []).slice().sort((a, b) => (FINDING_RANK[a.severity] ?? 1) - (FINDING_RANK[b.severity] ?? 1));
  if (!fs.length) return ['planned', 'done'].includes(status) ? '<p class="muted tiny">' + T('findings.none') + '</p>' : '';
  const severity = f => hasMessage('findings.severity.' + f.severity) ? t('findings.severity.' + f.severity) : f.severity;
  const stage = f => hasMessage('stages.' + f.stage) ? t('stages.' + f.stage) : f.stage;
  return '<h3>' + T('findings.title') + '</h3>' + fs.map(f => { const w = findingText(f); return '<div class="finding ' + esc(f.severity) + '"><b>' + w.title + '</b> <button class="help" data-help="finding-' + esc(f.code) + '" title="' + T('findings.howToFix') + '"><span class="mi" aria-hidden="true">help</span></button> <span class="tiny">' + esc(severity(f)) + ' · ' + esc(stage(f)) + (f.affected && f.affected.count ? ' · ' + tn('units.patrols', f.affected.count) : '') + '</span>' +
    ((f.values || []).length ? '<div class="values">' + f.values.map(v => '<span class="value"><span class="tiny">' + (v.label_key && hasMessage('findings.valueLabel.' + v.label_key) ? T('findings.valueLabel.' + v.label_key) : esc(v.label)) + '</span><code>' + esc(v.value) + '</code><button class="ghost" data-copy="' + esc(v.value) + '" title="' + T('findings.copy') + '"><span class="mi" aria-hidden="true">content_copy</span></button></span>').join('') + '</div>' : '') +
    (f.detail ? '<pre>' + esc(f.detail) + '</pre>' : '') + (w.fix ? '<div class="tiny"><b>' + T('findings.fix') + '</b> ' + w.fix + '</div>' : '') +
    // the stored English keeps what the translated sentence leaves out (a team's members, how many patrols name it)
    (w.translated ? '<details class="original" lang="en"><summary>' + T('findings.original') + '</summary><div class="tiny"><b>' + esc(f.title) + '</b></div>' + (f.fix ? '<pre>' + esc(f.fix) + '</pre>' : '') + '</details>' : '') +
    '</div>'; }).join('');
}

// the progress bar and import summary, the log (open while the load is active) and the load's files
function renderProgress(l, active) {
  const p = l.progress;
  return (p && p.patrols_total && l.mode !== 'plan' ? '<h3>' + T('progress.title') + '</h3><div class="bar"><div style="width:' + (100 * p.done / p.patrols_total).toFixed(1) + '%"></div></div><p class="tiny">' + importSummary(l, active) + '</p>' : '') +
    (l.continuations ? '<p class="tiny">' + tn('progress.continued', l.continuations) + '</p>' : '') +
    (l.log_tail ? '<details' + (active ? ' open' : '') + '><summary class="tiny">' + T(active ? 'progress.logLive' : 'progress.logTail') + '</summary><pre class="log">' + esc(l.log_tail) + '</pre></details>' : '') +
    '<p class="tiny">' + T('progress.files') + ' ' + ['plan.json', 'findings.json', 'checklist.json', 'checklist.md', 'rangers.json', 'import-ledger.json', 'log.txt'].map(n => '<a href="/api/loads/' + esc(l.id) + '/files/' + n + '" download>' + n + '</a>').join(' · ') + '</p>';
}

// the whole page; app.js swaps it in on every poll, keeping open sections, the log's scroll and an unchanged rangers table
function renderLoadPage(l, active) {
  return '<div id="loadPage">' + renderLoadTitle(l) + '<section class="panel">' + renderStages(l, active) +
    '<div id="loadFindings">' + renderFindings(l.findings, l.status) + '</div>' +
    '<div id="loadPlan">' + (l.plan ? '<h3>' + T('plan.title') + '</h3><div class="plan">' + renderPlan(l.plan) + '</div>' : '') + '</div>' +
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

// returns HTML: the counts are numbers and the words come from messages
function stageSummary(stage, row, l, active) {
  const m = row.metrics || {}, dry = l.mode === 'plan' || (!l.mode && ['planning', 'planned'].includes(l.status));
  const tally = (prefix, keys) => keys.filter(k => m[prefix + k]).map(k => T((dry && DRY_VERBS.includes(k) ? 'stages.tallyDry.' : 'stages.tally.') + k, { n: fmtNum(m[prefix + k]) }));
  const list = items => ({ list: items.join(', ') });
  const parts = [];
  if (stage === 'datamodel') {
    const cats = tally('categories_', ['created', 'existing']), types = tally('event_types_', ['created', 'updated', 'unchanged', 'migrated', 'skipped_by_mode', 'skipped_by_conflict', 'errored']), ch = tally('choices_', ['created', 'updated', 'unchanged', 'deactivated', 'skipped_by_mode', 'errored']);
    if (cats.length) parts.push(T('stages.summary.categories', null, list(cats)));
    if (types.length) parts.push(T('stages.summary.eventTypes', null, list(types)));
    if (ch.length) parts.push(T('stages.summary.choices', null, list(ch)));
  } else if (stage === 'patrol_datamodel') {
    const types = tally('types_', ['created', 'updated', 'unchanged']), subs = tally('subjects_', ['created', 'updated', 'deactivated', 'unchanged']);
    if (types.length) parts.push(T('stages.summary.patrolTypes', null, list(types)));
    if (subs.length) parts.push(T('stages.summary.subjects', null, list(subs)));
    if (m.subjects_grouped) parts.push(T('stages.summary.grouped', { count: fmtNum(m.subjects_grouped) }));
    if (m.schema_written) parts.push(dry ? T('stages.summary.schemaToWrite') : T('stages.summary.schemaWritten'));
    else if (m.schema_skipped) parts.push(T('stages.summary.schemaSkipped', { n: m.schema_skipped }));
  } else if (stage === 'preflight') {
    if ('blocking' in m) {
      const counts = { blocking: tn('units.blockingFindings', m.blocking), warnings: tn('units.warnings', m.warnings || 0) };
      parts.push(m.patrols != null ? T('stages.summary.preflightPatrols', null, { ...counts, patrols: tn('units.patrols', m.patrols) }) : T('stages.summary.preflight', null, counts));
    }
  } else if (stage === 'import') {
    if (dry) {
      if ('planned' in m) parts.push(m.already_done ? T('stages.summary.toLoadDone', { done: fmtNum(m.already_done) }, { patrols: tn('units.patrols', m.planned) }) : T('stages.summary.toLoad', null, { patrols: tn('units.patrols', m.planned) }));
    } else if (l.progress && l.progress.patrols_total) parts.push(importSummary(l, active && row.status === 'running'));
  }
  return parts.join(' · ');
}

// returns HTML, like stageSummary
function importSummary(l, live) {
  const p = l.progress;
  const counts = [tn('progress.of', p.patrols_total, { done: fmtNum(p.done) })];
  if (p.failed) counts.push(T('progress.failed', { n: fmtNum(p.failed) }));
  if (p.skipped) counts.push(T('progress.alreadyThere', { n: fmtNum(p.skipped) }));
  const of = counts.join(', ');
  const row = (l.stages || {}).import || {};
  if (!live) {   // a finished run reads as a whole: a per-minute rate would mix its two phases
    const secs = row.started_at && row.finished_at ? (Date.parse(row.finished_at) - Date.parse(row.started_at)) / 1000 : null;
    const m = row.metrics || {};
    // what this execution did (a continuation's counts are its own, not the load's): the events it wrote,
    // how many of the events it handled (written or already there) report who made them, and the ones
    // from an earlier load it gave a reporter
    const did = m.events_written != null ? ' · ' + T('progress.wrote', null, { events: tn('units.events', m.events_written) }) +
      (m.events_reported_by ? '; ' + T('progress.reportedBy', { count: fmtNum(m.events_reported_by) }) : '') +
      (m.events_reported_by_backfilled ? ', ' + T('progress.backfilled', { count: fmtNum(m.events_reported_by_backfilled) }) : '') : '';
    return of + (secs != null ? ' · ' + esc(fmtDur(secs)) : '') + did;
  }
  // the import runs every patrol's events, then every patrol's tracks; done restarts with each phase
  const since = p.phase ? p.phase_started_at : row.started_at;
  let s = p.phase ? T(p.phase === 'tracks' ? 'progress.tracks' : 'progress.events', null, { of: of }) : of;
  const mins = since ? (now() - Date.parse(since)) / 60000 : null;
  const written = p.done - ((p.phase ? p.phase_skipped : p.skipped) || 0);   // skips take no time; a phase also skips what a stopped run left half done
  if (mins && mins > 0.5 && written > 0) {
    const rate = written / mins;
    s += ' · ' + T('progress.rate', { rate: rate.toFixed(1) });
    if (p.done < p.patrols_total) {
      const left = fmtDur((p.patrols_total - p.done) / rate * 60);
      s += ' · ' + (p.phase === 'events' ? T('progress.leftPhase', { dur: left }) : T('progress.left', { dur: left }));
    }
  }
  return s;
}

// the words for a stage that was never reached, as plain text for pill(), which escapes its label
function stageLabel(status, active) { return status === 'pending' && !active ? t('status.notReached') : undefined; }
function renderStages(l, active) {
  const rows = stageRows(l);
  let html = '<table class="stagetable"><thead><tr><th>' + T('stages.colStage') + '</th><th>' + T('stages.colStatus') + '</th><th>' + T('stages.colTook') + '</th><th>' + T('stages.colWhat') + '</th></tr></thead><tbody>';
  for (const s of ((l.options || {}).scope === 'datamodel' ? STAGES.slice(0, 2) : STAGES)) {
    const r = rows[s], status = r ? r.status : 'pending';
    const running = status === 'running' && active;
    const took = r && r.started_at && r.finished_at ? fmtDur((Date.parse(r.finished_at) - Date.parse(r.started_at)) / 1000) : running && r.started_at ? fmtDur(secondsSince(r.started_at)) + '…' : '';
    const shown = running ? 'running' : status === 'running' ? 'interrupted' : status;
    html += '<tr class="' + esc(status) + '"><td>' + T('stages.' + s) + '</td><td>' +
      pill(shown, stageLabel(shown, active)) + '</td><td class="tiny">' + esc(took) + '</td><td class="tiny">' + (r ? stageSummary(s, r, l, active) : '') + '</td></tr>';
  }
  html += '</tbody></table>';
  if (active) html += notStarted(l) ? '<p class="tiny heartbeat">' + T('stages.waiting', { dur: fmtDur(secondsSince(l.claimed_at)) }) + '</p>'
    : '<p class="tiny heartbeat">' + (l.continuations
      ? T('stages.heartbeatContinued', { n: l.continuations, dur: fmtDur(secondsSince(l.started_at || l.claimed_at)), ago: fmtDur(secondsSince(l.updated_at)) })
      : T('stages.heartbeat', { dur: fmtDur(secondsSince(l.started_at || l.claimed_at)), ago: fmtDur(secondsSince(l.updated_at)) })) + '</p>';
  return html;
}

function renderPlan(plan) {
  // title: HTML. opts.noIdOnCreate: the group's creates have no identifier yet (plans saved before that rule carried a placeholder there)
  const group = (title, g, opts = {}) => {
    if (!g) return '';
    const parts = [];
    for (const k of ['create', 'update', 'deactivate']) if (Array.isArray(g[k]) && g[k].length) {
      const more = typeof g.more === 'object' && g.more ? g.more[k] || 0 : (g.more || 0);   // per list now; a number in older plans
      const showValue = e => e.value && e.value !== e.label && !(opts.noIdOnCreate && k === 'create');
      parts.push('<details><summary>' + T('plan.' + k, { n: g[k].length + (more ? '+' : '') }) + '</summary><ul>' + g[k].map(e => '<li>' + esc(e.label) + (showValue(e) ? ' <span class="tiny">' + esc(e.value) + '</span>' : '') + '</li>').join('') + (more ? '<li class="tiny">' + T('plan.more', { n: more }) + '</li>' : '') + '</ul></details>');
    }
    if (opts.extra) parts.push(opts.extra);
    if (g.unchanged) parts.push('<span class="tiny">' + T('plan.unchanged', { n: g.unchanged }) + '</span>');
    return '<div><b>' + title + '</b> ' + (parts.join(' ') || '<span class="tiny">' + T('plan.nothing') + '</span>') + '</div>';
  };
  // event types the site already has that differ from SMART, and what the load does with them: each with what
  // differs (the field keys are the site's and SMART's own, shown as they are)
  const differs = () => {
    const g = plan.event_types || {}, list = Array.isArray(g.differ) ? g.differ : [];
    if (!list.length) return '';
    const more = typeof g.more === 'object' && g.more ? g.more.differ || 0 : 0;
    const what = d => [d.name ? T('plan.diffName') : '', d.active ? T('plan.diffActive') : '',
      (d.site_only || []).length ? T('plan.diffSiteOnly', { fields: d.site_only.join(', ') }) : '',
      (d.smart_only || []).length ? T('plan.diffSmartOnly', { fields: d.smart_only.join(', ') }) : '',
      (d.changed || []).length ? T('plan.diffChanged', { fields: d.changed.join(', ') }) : '', d.other ? T('plan.diffOther') : ''].filter(Boolean).join('; ');
    return '<details><summary>' + T(plan.existing_event_types === 'keep' ? 'plan.differKept' : 'plan.differUpdated', { n: list.length + (more ? '+' : '') }) + '</summary><ul>' +
      list.map(d => '<li>' + esc(d.label) + (d.value && d.value !== d.label ? ' <span class="tiny">' + esc(d.value) + '</span>' : '') + ' <span class="tiny">' + what(d) + '</span></li>').join('') +
      (more ? '<li class="tiny">' + T('plan.more', { n: more }) + '</li>' : '') + '</ul></details>';
  };
  const p = plan.patrols;   // absent from a data-model-only plan
  const roster = plan.roster || {};
  const rosterAdd = roster.group ? T('plan.rosterGroupAdd', { group: roster.group, n: roster.add || 0 }) : T('plan.rosterAdd', { n: roster.add || 0 });
  // the line's wording depends on whether the plan has a date window and patrols already imported
  const patrolsLine = p => T(p.first ? (p.already_done ? 'plan.patrolsFromDone' : 'plan.patrolsFrom') : (p.already_done ? 'plan.patrolsDone' : 'plan.patrolsLine'),
    { total: fmtNum(p.total || 0), first: p.first, last: p.last, done: fmtNum(p.already_done || 0) }, { events: tn('units.observations', p.events || 0), points: tn('units.trackPoints', p.track_points || 0) });
  return group(T('plan.eventCategories'), plan.event_categories) + group(T('plan.eventTypes'), plan.event_types, { extra: differs() }) + group(T('plan.patrolTypes'), plan.patrol_types) +
    '<div><b>' + T('plan.universalFields') + '</b> ' + esc(plan.universal_patrol_fields) + '</div>' + group(T('plan.choices'), plan.choices) + group(T('plan.subjects'), plan.subjects, { noIdOnCreate: true }) +
    '<div><b>' + T('plan.roster') + '</b> ' + rosterAdd + '</div>' +
    (!p ? '<div><b>' + T('plan.patrols') + '</b> <span class="tiny">' + T('plan.none') + '</span></div>' :
    '<div><b>' + T('plan.patrols') + '</b> ' + patrolsLine(p) + '</div>');
}
