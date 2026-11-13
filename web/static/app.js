// smart-able web: sign in, list datasets, upload + extract, share, open.
const $ = (s, el = document) => el.querySelector(s);
let CONFIG = null, ME = null, pollTimer = null;

async function api(path, opts = {}) {
  const r = await fetch(path, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) }, ...opts });
  if (r.status === 401) { showSignIn(); throw new Error('Sign in required'); }
  if (!r.ok) { let d = ''; try { d = (await r.json()).detail; } catch (e) {} throw new Error(d || r.statusText); }
  return r.status === 204 ? null : r.json();
}

function showSignIn(err) {
  clearTimeout(pollTimer); clearTimeout(loadTimer); currentLoad = null;
  mountHeader(false); setBreadcrumb(null);
  mountPage(renderSignIn(CONFIG));
  $('#signInBtn').onclick = signIn;
  $('#signInError').textContent = err || '';
}
function showApp() {
  mountHeader(true);
  $('#whoEmail').textContent = ME.email;
  navigate(parseRoute(location.hash), 'replace');   // the address says which page; the first entry is that page
}

// ---- the shell: the header band, the breadcrumb under it, and one page container
// signed out, the band shows only the lockup, the name and the version
function mountHeader(signedIn) {
  $('#helpBtn').hidden = !signedIn; $('#account').hidden = !signedIn;
  $('#account').open = false;
}
function mountPage(html) { $('#page').innerHTML = html; }
// parts: [{label, hash?}], the last one where the reader is; none hides the bar
function setBreadcrumb(parts) {
  const bar = $('#crumbs');
  bar.hidden = !(parts && parts.length);
  bar.innerHTML = parts && parts.length ? renderBreadcrumb(parts) : '';
}
// data-theme is always 'light' or 'dark'. 'system' resolves it from the OS and follows a switch
// while the page is open; 'light' and 'dark' pin it. The choice (system|light|dark) is remembered.
let themeChoice = 'system', themeQuery = null;
function setTheme(choice) {
  if (choice !== 'light' && choice !== 'dark') choice = 'system';
  themeChoice = choice;
  if (!themeQuery && window.matchMedia) {   // registered once; it acts only while the choice is system
    themeQuery = matchMedia('(prefers-color-scheme: dark)');
    themeQuery.addEventListener('change', () => { if (themeChoice === 'system') applyTheme(); });
  }
  applyTheme();
  try { localStorage.theme = choice; } catch (e) { /* storage blocked: the choice lasts this page */ }
  document.querySelectorAll('input[name="theme"]').forEach(r => { r.checked = r.value === choice; });
}
function applyTheme() {
  document.documentElement.dataset.theme = themeChoice !== 'system' ? themeChoice : themeQuery && themeQuery.matches ? 'dark' : 'light';
}

// ---- routes are history entries, so Back and Forward move between pages and a page's link can be
// shared or reloaded. The hash is the truth; history.state.from is the hash of the page the reader
// came from, so a Back button can step back when that is its parent, and navigate there otherwise.
// nav: 'push' adds an entry, 'replace' rewrites this one (keeping its from), 'none' leaves history alone.
function navigate(route, nav = 'push') {
  const hash = routeHash(route);
  if (nav === 'push') history.pushState({ from: location.hash || '#/' }, '', location.pathname + location.search + hash);
  else if (nav === 'replace') history.replaceState({ from: (history.state || {}).from }, '', location.pathname + location.search + hash);
  renderRoute(route);
}
// one show* per page; the sites page arrives in a later task
function renderRoute(route) {
  clearTimeout(pollTimer); listGen++;   // leaving the home page: its poll and any response in flight stop
  if (route.page === 'home') showHome();
  else if (route.page === 'dataset') showDataset(route);
  else if (route.page === 'load') openLoad(route.load);
  else if (route.page === 'legacy-load') openLegacyLoad(route.load);
  else console.log('no page built yet for', route);
}
// an old #load/<id> link: look up the load's dataset and swap the entry for the load's route
async function openLegacyLoad(id) {
  const mine = routeHash({ page: 'legacy-load', load: id });
  try {
    const l = await api('/api/loads/' + id);
    if (location.hash !== mine) return;   // the reader moved on while it loaded
    navigate({ page: 'load', id: l.dataset_id, load: id }, 'replace');
  } catch (e) { if (location.hash === mine) navigate({ page: 'home' }, 'replace'); }
}
window.addEventListener('popstate', () => { if (ME) renderRoute(parseRoute(location.hash)); });

async function boot() {
  let theme = 'system';
  try { theme = localStorage.theme || 'system'; } catch (e) { /* storage blocked */ }
  setTheme(theme);   // before the first fetch, so the page never flashes the other theme
  CONFIG = await (await fetch('/api/config')).json();
  if (!CONFIG.authDisabled) {
    firebase.initializeApp({ apiKey: CONFIG.apiKey, authDomain: CONFIG.authDomain, projectId: CONFIG.projectId });
    if (CONFIG.authEmulatorUrl) firebase.auth().useEmulator(CONFIG.authEmulatorUrl);
  }
  $('#helpBtn').onclick = () => openHelp();
  $('#helpClose').onclick = closeHelp;
  $('#helpBody').onscroll = helpScrolled;
  $('#help').onkeydown = helpKeydown;
  $('#helpBackdrop').onclick = closeHelp;
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('#help').hidden) closeHelp(); });
  document.querySelectorAll('input[name="theme"]').forEach(r => { r.onchange = () => setTheme(r.value); });
  $('#menuSites').onclick = () => { $('#account').open = false; navigate({ page: 'sites' }); };
  // the menu closes on a click outside it or Escape, like any menu
  document.addEventListener('click', e => { if ($('#account').open && !$('#account').contains(e.target)) $('#account').open = false; });
  $('#account').onkeydown = e => { if (e.key === 'Escape') { $('#account').open = false; $('#whoEmail').focus(); } };
  $('#signOut').onclick = async () => { $('#account').open = false; await api('/api/signout', { method: 'POST' }); if (!CONFIG.authDisabled) await firebase.auth().signOut(); showSignIn(); };
  $('#modalClose').onclick = () => { $('#modal').hidden = true; };
  // the title goes home from anywhere in the app; signed in, without reloading the page
  $('#home').onclick = e => { if (ME) { e.preventDefault(); if (!$('#help').hidden) closeHelp(); $('#modal').hidden = true; showDatasets(); } };
  try { ME = await api('/api/me'); showApp(); } catch (e) { /* not signed in yet */ }
}

async function signIn() {
  try {
    let idToken = '';
    if (!CONFIG.authDisabled) {
      const cred = await firebase.auth().signInWithPopup(new firebase.auth.GoogleAuthProvider());
      idToken = await cred.user.getIdToken();
    }
    ME = await api('/api/session', { method: 'POST', body: JSON.stringify({ idToken }) });
    showApp();
  } catch (e) { showSignIn(e.message); }
}

// ---- datasets
let listGen = 0;   // which render of the home page is current

// the home page's polling: a fetch is current only while its gen is, so a superseded response is dropped
async function showHome() {
  clearTimeout(loadTimer); clearTimeout(pollTimer); currentLoad = null;
  const gen = ++listGen;
  setBreadcrumb(null);
  let list;
  try { list = await api('/api/datasets'); } catch (e) { if (gen === listGen) mountPage('<p class="empty">' + esc(e.message) + '</p>'); return; }
  if (gen !== listGen) return;
  mountPage(renderHome(list));
  $('#uploadBtn').onclick = uploadDialog;
  pollHome(list, gen);
}
// while any dataset is queued or running, refetch every 5 s and replace only the card list
// ('uploading' is not polled: the tab doing the upload shows its own progress, and an abandoned one never changes)
function pollHome(list, gen) {
  clearTimeout(pollTimer);
  if (!list.some(d => ['queued', 'running'].includes(d.status))) return;
  pollTimer = setTimeout(async () => {
    let next;
    try { next = await api('/api/datasets'); } catch (e) { return pollHome(list, gen); }
    const host = $('#cards');
    if (gen !== listGen || !host) return;
    const html = renderCardList(next);
    if (html !== host.dataset.html) { host.innerHTML = html; host.dataset.html = html; }
    pollHome(next, gen);
  }, 5000);
}

// a form that brings its own Close beside its submit button (data-close) hides the dialog's own
function dialog(title, bodyHtml) {
  $('#modalTitle').textContent = title; $('#modalBody').innerHTML = bodyHtml;
  const own = $('#modalBody').querySelector('[data-close]');
  $('#modalFoot').hidden = !!own; if (own) own.onclick = () => { $('#modal').hidden = true; };
  $('#modal').hidden = false;
}

function shareDialog(d, base = '/api/datasets/', note) {
  const refresh = () => { if (base === '/api/sites/') return loadSites(); const r = parseRoute(location.hash); if (r.page === 'home') showHome(); else if (r.page === 'dataset') showDataset(r); };
  note = note || 'People you share with can open the dataset. Only you can share, re-extract, or delete it.';
  const render = shared => {
    dialog('Share "' + d.name + '"',
      '<p class="muted tiny">' + esc(note) + ' Addresses must be ' + esc(CONFIG.allowed) + '.</p>' +
      '<form id="shareForm" class="row"><input type="email" id="shareEmail" placeholder="colleague' + esc(CONFIG.allowed.startsWith('@') ? CONFIG.allowed : '@example.org') + '" required><button type="submit" class="primary">Share</button></form>' +
      '<div class="shared"><ul>' + (shared.length ? shared.map(e => '<li><span class="mi" aria-hidden="true">person</span>' + esc(e) + ' <button class="ghost" data-unshare="' + esc(e) + '" title="Remove"><span class="mi" aria-hidden="true">close</span></button></li>').join('') : '<li class="tiny">Not shared with anyone yet.</li>') + '</ul></div>');
    $('#shareForm').onsubmit = async ev => { ev.preventDefault(); try { const r = await api(base + d.id + '/share', { method: 'POST', body: JSON.stringify({ email: $('#shareEmail').value }) }); render(r.shared_with); refresh(); } catch (e) { alert(e.message); } };
    $('#modalBody').querySelectorAll('[data-unshare]').forEach(b => b.onclick = async () => { try { const r = await api(base + d.id + '/share/' + encodeURIComponent(b.dataset.unshare), { method: 'DELETE' }); render(r.shared_with); refresh(); } catch (e) { alert(e.message); } });
  };
  render(d.shared_with || []);
}

// ---- the dataset page: the dataset, the tab's data, the actions; polls while it extracts
let datasetGen = 0;
async function showDataset(route) {
  clearTimeout(loadTimer); clearTimeout(pollTimer); currentLoad = null;
  const gen = ++datasetGen, mine = routeHash(route);
  const current = () => gen === datasetGen && location.hash === mine;
  let d;
  try { d = await api('/api/datasets/' + route.id); }
  catch (e) {
    if (!current()) return;
    setBreadcrumb([{ label: 'Datasets', hash: '#/' }, { label: 'Not found' }]);
    mountPage(renderNotFound());
    return;
  }
  if (!current()) return;
  let tab = route.tab;
  if (tab !== 'overview' && d.status !== 'ready') { tab = 'overview'; navigate({ page: 'dataset', id: d.id, tab }, 'replace'); return; }
  const extra = {};
  try {
    if (tab === 'loads') extra.loads = await api('/api/datasets/' + d.id + '/loads');
    else if (tab === 'rangers') {
      const loads = (await api('/api/datasets/' + d.id + '/loads')).slice().sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
      // the list items carry no rangers: the newest load that has some is found by fetching, newest first
      for (const l of loads) { if (!current()) return; const full = await api('/api/loads/' + l.id); if ((full.rangers || []).length) { extra.load = full; break; } }
    }
  } catch (e) { if (!current()) return; mountPage('<p class="empty">' + esc(e.message) + '</p>'); return; }
  if (!current()) return;
  setBreadcrumb([{ label: 'Datasets', hash: '#/' }, { label: d.name }]);
  mountPage(renderDatasetPage(d, tab, extra));
  bindDataset(d, tab, route, extra);
  if (['running', 'queued', 'pending'].includes(d.status) || (tab === 'loads' && (extra.loads || []).some(l => l.held)))
    pollTimer = setTimeout(() => { if (current()) showDataset(route); }, 5000);
}
function bindDataset(d, tab, route, extra) {
  document.querySelectorAll('.tabs [aria-disabled="true"]').forEach(a => { a.onclick = ev => ev.preventDefault(); });
  const share = $('#shareBtn'); if (share) share.onclick = () => shareDialog(d);
  const ex = $('#extractBtn'); if (ex) ex.onclick = async () => {
    try { await api('/api/datasets/' + d.id + '/extract', { method: 'POST' }); showDataset(route); } catch (e) { alert(e.message); }
  };
  const del = $('#deleteBtn'); if (del) del.onclick = async () => {
    if (!confirm('Delete "' + d.name + '" and all its extracted data, bundles and load records? Nothing in EarthRanger is removed.')) return;
    try { await api('/api/datasets/' + d.id, { method: 'DELETE' }); navigate({ page: 'home' }, 'replace'); } catch (e) { alert(e.message); }
  };
  document.querySelectorAll('[data-act="load"]').forEach(b => { b.onclick = () => loadDialog(d, b.dataset.ca); });
  const lb = $('#loadBtn'); if (lb) lb.onclick = () => loadDialog(d);
  if (tab === 'rangers' && extra.load) bindRangers($('#tabBody'), extra.load);
}

// ---- upload: create the dataset, PUT the file where the server says (a signed
// GCS URL in production, the service itself locally), then start extraction. The XHR keeps
// running if the dialog is closed; the elements it updates are then just detached.
function uploadDialog() {
  dialog('Upload a backup or export',
    '<form id="uploadForm" class="stack">' +
    '<label>Name <input id="dsName" required placeholder="e.g. Lawin R5"></label>' +
    '<label>File <input id="dsFile" type="file" accept=".zip,.sql,.gz,.bak" required></label>' +
    '<div id="progress" class="progress" hidden><div class="bar"><div id="progressFill"></div></div><div id="progressText" class="tiny"></div></div>' +
    '<div class="row right"><button type="submit" id="uploadSubmit" class="btn primary">Upload</button></div></form>');
  const form = $('#uploadForm');
  form.onsubmit = async ev => {
    ev.preventDefault();
    const file = $('#dsFile', form).files[0]; if (!file) return;
    const btn = $('#uploadSubmit', form), prog = $('#progress', form), fill = $('#progressFill', form), text = $('#progressText', form);
    btn.disabled = true; prog.hidden = false; fill.style.width = '0%'; text.textContent = 'Preparing…';
    try {
      const created = await api('/api/datasets', { method: 'POST', body: JSON.stringify({ name: $('#dsName', form).value, filename: file.name, size: file.size, content_type: file.type || 'application/zip' }) });
      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open(created.upload.method, created.upload.url);
        for (const [k, v] of Object.entries(created.upload.headers || {})) xhr.setRequestHeader(k, v);
        xhr.withCredentials = created.upload.url.startsWith('/');
        xhr.upload.onprogress = e => { if (e.lengthComputable) { fill.style.width = (100 * e.loaded / e.total).toFixed(1) + '%'; text.textContent = 'Uploading ' + fmtBytes(e.loaded) + ' of ' + fmtBytes(e.total); } };
        xhr.onload = () => xhr.status < 300 ? resolve() : reject(new Error('Upload failed (' + xhr.status + ')'));
        xhr.onerror = () => reject(new Error('Upload failed (network)'));
        xhr.send(file);
      });
      text.textContent = 'Uploaded. Starting extraction…';
      await api('/api/datasets/' + created.id + '/extract', { method: 'POST' });
      if ($('#modalBody').contains(form)) $('#modal').hidden = true;   // still on screen: close it
      if (parseRoute(location.hash).page === 'home') showHome();       // the new dataset appears, extracting
    } catch (e) { text.textContent = e.message; btn.disabled = false; }
  };
}

// ---- sites
async function loadSites() {
  const list = await api('/api/sites');
  const host = $('#sites');
  if (!list.length) { host.innerHTML = '<p class="muted tiny">No sites yet.</p>'; return list; }
  host.innerHTML = '<table><thead><tr><th>Site</th><th>Host</th><th>Token</th><th>Owner</th><th>Shared with</th><th></th></tr></thead><tbody>' +
    list.map(s => '<tr data-id="' + esc(s.id) + '">' +
      '<td><b>' + esc(s.name) + '</b></td><td>' + esc(s.url) + '</td>' +
      '<td class="tiny">…' + esc(s.token_hint) + ' as ' + esc(s.checked_as) + '</td>' +
      '<td>' + (s.mine ? 'you' : esc(s.owner_email)) + '</td>' +
      '<td>' + ((s.shared_with || []).map(esc).join('<br>') || '<span class="tiny">—</span>') + '</td>' +
      '<td class="actions">' +
        (s.mine ? '<button data-act="siteShare"><span class="mi" aria-hidden="true">share</span>Share</button> ' : '') +
        (s.mine ? '<button data-act="siteDelete" class="danger" title="Remove this site and its token"><span class="mi" aria-hidden="true">delete</span></button>' : '') +
      '</td></tr>').join('') + '</tbody></table>';
  host.querySelectorAll('button[data-act]').forEach(b => b.onclick = () => siteAction(b.dataset.act, list.find(s => s.id === b.closest('tr').dataset.id)));
  return list;
}

async function siteAction(act, s) {
  try {
    if (act === 'siteShare') return shareDialog(s, '/api/sites/', 'People you share with can load datasets into this site using your token.');
    if (act === 'siteDelete') { if (!confirm('Remove "' + s.name + '"? Loads already made keep their records but cannot be continued.')) return; await api('/api/sites/' + s.id, { method: 'DELETE' }); return loadSites(); }
  } catch (e) { alert(e.message); }
}

async function addSite(ev) {
  ev.preventDefault();
  const btn = $('#siteBtn'); btn.disabled = true; $('#siteError').textContent = 'Checking the token…';
  try {
    await api('/api/sites', { method: 'POST', body: JSON.stringify({ name: $('#siteName').value, url: $('#siteUrl').value, token: $('#siteToken').value }) });
    $('#siteForm').reset(); $('#siteError').textContent = '';
    loadSites();
  } catch (e) { $('#siteError').textContent = e.message; }
  finally { btn.disabled = false; }
}

// mirrors findings.ca_identifier: smart-<ca id>, 2-30 chars of [A-Za-z0-9_-]
function defaultEventCategory(caId) {
  const s = ('smart-' + (caId || 'ca')).toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
  return (s.length >= 2 ? s : 'smart-ca').slice(0, 30);
}

async function loadDialog(d, caId) {
  const sites = await api('/api/sites');
  if (!sites.length) return alert('Register an EarthRanger site first.');
  let lastDefault = null;
  const render = () => {
    const ca = d.export.find(e => e.dir === $('#ldCa').value) || d.export[0];
    const def = defaultEventCategory(ca.ca_id);   // what the server defaults to
    if (lastDefault === null || $('#ldCategory').value === lastDefault) $('#ldCategory').value = def;
    lastDefault = def;
    $('#ldLang').innerHTML = ca.languages.map(l => '<option' + (l === ca.default_language ? ' selected' : '') + '>' + esc(l) + '</option>').join('');
    $('#ldCm').innerHTML = '<option value="">none</option>' + ca.configurable_models.map(m => '<option value="' + esc(m.uuid) + '">' + esc(m.label) + '</option>').join('');
  };
  dialog('Load "' + d.name + '" into EarthRanger',
    '<p class="muted tiny">First a plan is made without writing anything. You confirm it before the site is changed.</p>' +
    '<form id="ldForm" class="col">' +
    '<label>Conservation area <select id="ldCa">' + d.export.map(e => '<option value="' + esc(e.dir) + '">' + esc(e.name || e.ca_id) + ' (' + esc(e.patrols) + ' patrols)</option>').join('') + '</select></label>' +
    '<label>Site <select id="ldSite">' + sites.map(s => '<option value="' + esc(s.id) + '">' + esc(s.name) + ' · ' + esc(s.url) + '</option>').join('') + '</select></label>' +
    '<label>Label language <select id="ldLang"></select></label>' +
    '<label>Configurable model <select id="ldCm"></select></label>' +
    '<p class="muted tiny">none: event types for the whole data model. A configurable model (the subset a SMART mobile form uses) makes only its categories and dropdown options active; others that older observations used are kept, inactive, so those observations still load.</p>' +
    '<label>Roster group <input type="text" id="ldRoster" placeholder="optional; default: the patrol configuration\'s first member group"></label>' +
    '<label>Event category <input type="text" id="ldCategory" maxlength="30" pattern="[A-Za-z0-9_\\-]{2,30}" required></label>' +
    '<p class="muted tiny">Use the identifier an earlier CLI push used, if any (for example, site-xyz).</p>' +
    '<label>What to load <select id="ldScope"><option value="all">The data model and patrols</option><option value="datamodel">The data model only</option></select></label>' +
    '<div class="row" id="ldWindow"><label>Patrols from <input type="date" id="ldSince"></label><label>to <input type="date" id="ldUntil"></label></div>' +
    '<p class="muted tiny" id="ldScopeHint"></p>' +
    '<div class="row right"><button type="button" class="ghost" data-close>Close</button><button type="submit" class="primary">Make the plan</button></div></form>');
  const scopeChanged = () => {
    const dm = $('#ldScope').value === 'datamodel';
    $('#ldWindow').hidden = dm;
    $('#ldScopeHint').textContent = dm
      ? 'Event types, patrol types and fields, rangers and the roster: what a team needs to patrol and record in EarthRanger. No patrols, observations or tracks.'
      : 'Leave the dates empty to load every patrol. A patrol is in the window when it starts on or between the dates.';
  };
  if (caId) $('#ldCa').value = caId;
  render(); scopeChanged(); $('#ldCa').onchange = render; $('#ldScope').onchange = scopeChanged;
  $('#ldForm').onsubmit = async ev => {
    ev.preventDefault();
    const dm = $('#ldScope').value === 'datamodel', since = dm ? '' : $('#ldSince').value, until = dm ? '' : $('#ldUntil').value;
    if (since && until && since > until) return alert('The window starts after it ends.');
    try {
      const l = await api('/api/datasets/' + d.id + '/loads', { method: 'POST', body: JSON.stringify({ ca_id: $('#ldCa').value, site_id: $('#ldSite').value,
        options: { language: $('#ldLang').value, configurable_model: $('#ldCm').value || null, roster_group: $('#ldRoster').value,
        event_category: $('#ldCategory').value.trim(), scope: $('#ldScope').value, since: since || null, until: until || null } }) });
      $('#modal').hidden = true; showLoad(l.id);
    } catch (e) { alert(e.message); }
  };
}

// ---- the load page
let loadTimer = null, currentLoad = null;
// 'auto' steps back to the list when a load was opened from it, else goes to it; 'push' and 'replace'
// say so. showLoad (replaced by the load page in a later task) goes through navigate as well.
function showDatasets(nav = 'auto') {
  if (nav === 'auto') {
    if (currentLoad && (history.state || {}).from === '#/') { history.back(); return; }   // popstate shows the list
    nav = currentLoad ? 'push' : 'replace';   // already on the list: no entry
  }
  navigate({ page: 'home' }, nav);
}
function showLoad(id, nav = 'push') { navigate({ page: 'legacy-load', load: id }, nav); }

async function openLoad(id) {
  clearTimeout(pollTimer);
  currentLoad = id;
  // the load page is rebuilt in a later task; until then it keeps its old containers
  mountPage('<section id="loadPage" class="panel"><h2 id="loadTitle"></h2><div id="loadStages" class="stages"></div><div id="loadActions" class="row"></div>' +
    '<div id="loadFindings"></div><div id="loadPlan"></div><div id="loadRangers"></div><div id="loadProgress"></div></section>');
  try { await renderLoad(); }
  catch (e) {   // a gone load leaves the list in its place
    alert(e.message);
    navigate({ page: 'home' }, 'replace');
  }
}

const STAGES = ['datamodel', 'patrol_datamodel', 'preflight', 'import'];
const STAGE_LABEL = { datamodel: 'Event types', patrol_datamodel: 'Patrol setup', preflight: 'Preflight', import: 'Patrols' };
const ACTIVE = ['planning', 'queued', 'running', 'continuing'];

async function renderLoad() {
  const id = currentLoad;
  clearTimeout(loadTimer);
  let l;
  try { l = await api('/api/loads/' + id); }
  catch (e) {
    if (currentLoad !== id) return;
    if (/not found/i.test(e.message)) throw e;
    $('#loadActions').insertAdjacentHTML('beforeend', '<div class="tiny" data-retry>Could not refresh; retrying…</div>');
    loadTimer = setTimeout(() => renderLoad().catch(() => {}), 4000);
    return;
  }
  if (currentLoad !== id) return;
  const active = !!l.held;
  const stale = !active && ACTIVE.includes(l.status);
  $('#loadTitle').innerHTML = esc(l.ca_id + ' → ' + (l.site ? l.site.name + ' (' + l.site.url + ')' : 'removed site')) +
    (loadScope(l) ? ' <span class="scope">' + esc(loadScope(l)) + '</span>' : '') +
    ' ' + pill(l.status) +
    ' <button class="help" data-help="help-statuses" title="What the statuses mean"><span class="mi" aria-hidden="true">help</span></button>';
  $('#loadTitle [data-help]').onclick = () => openHelp('help-statuses');
  $('#loadStages').innerHTML = renderStages(l, active);
  const blocking = (l.findings || []).filter(f => f.severity === 'blocking').length;
  let actions = '';
  if (!active && l.site) {
    // a plan writes nothing, so a run gets further than its plan: confirm is offered even with blocking findings
    if (l.status === 'planned') actions += '<button class="primary" data-run><span class="mi" aria-hidden="true">play_arrow</span>Confirm and load' +
      (blocking ? ' (stops at ' + blocking + ' blocking)' : '') + '</button> ';
    if (l.status === 'needs_attention' || stale) actions += '<button class="primary" data-run><span class="mi" aria-hidden="true">play_arrow</span>Continue</button> ';
    if (stale || ['planned', 'needs_attention', 'failed', 'done'].includes(l.status)) actions += '<button data-replan><span class="mi" aria-hidden="true">refresh</span>Plan again</button> ';
  }
  if (!active) actions += '<button class="danger" data-del><span class="mi" aria-hidden="true">delete</span>Delete this load</button>';
  if (!active && l.site && l.status === 'planned' && blocking) actions += '<div class="tiny">The run will write what the plan lists, then stop at the ' +
    (blocking === 1 ? 'blocking finding' : blocking + ' blocking findings') + ' below until they are fixed.</div>';
  if (stale) actions += '<div class="tiny">The job stopped without reporting; continue to resume from the last checkpoint.</div>';
  if (l.error) actions += '<div class="tiny" style="color:var(--danger)">' + esc(l.error) + '</div>';
  $('#loadActions').innerHTML = actions;
  const run = $('#loadActions [data-run]'); if (run) run.onclick = async () => { try { await api('/api/loads/' + l.id + '/run', { method: 'POST' }); renderLoad(); } catch (e) { alert(e.message); } };
  const re = $('#loadActions [data-replan]'); if (re) re.onclick = async () => { try { await api('/api/loads/' + l.id + '/replan', { method: 'POST' }); renderLoad(); } catch (e) { alert(e.message); } };
  const del = $('#loadActions [data-del]'); if (del) del.onclick = async () => { if (!confirm('Delete this load\'s records? Nothing in EarthRanger is removed.')) return; try {
      await api('/api/loads/' + l.id, { method: 'DELETE' });
      // the deleted load's entry becomes the list, so Back never lands on it; if the reader has moved on
      // meanwhile, the page they are on is left alone and a list they are on is refreshed
      if (currentLoad === l.id) showDatasets('replace'); else if (parseRoute(location.hash).page === 'home') showHome();
    } catch (e) { alert(e.message); } };
  const RANK = { blocking: 0, warning: 1, info: 2 };
  const fs = (l.findings || []).slice().sort((a, b) => (RANK[a.severity] ?? 1) - (RANK[b.severity] ?? 1));
  $('#loadFindings').innerHTML = fs.length ? '<h3>Findings</h3>' + fs.map(f => '<div class="finding ' + esc(f.severity) + '"><b>' + esc(f.title) + '</b> <button class="help" data-help="finding-' + esc(f.code) + '" title="How to fix this"><span class="mi" aria-hidden="true">help</span></button> <span class="tiny">' + esc(f.severity) + ' · ' + esc(STAGE_LABEL[f.stage] || f.stage) + (f.affected && f.affected.count ? ' · ' + esc(f.affected.count) + ' patrols' : '') + '</span>' +
    ((f.values || []).length ? '<div class="values">' + f.values.map(v => '<span class="value"><span class="tiny">' + esc(v.label) + '</span><code>' + esc(v.value) + '</code><button class="ghost" data-copy="' + esc(v.value) + '" title="Copy to clipboard"><span class="mi" aria-hidden="true">content_copy</span></button></span>').join('') + '</div>' : '') +
    (f.detail ? '<pre>' + esc(f.detail) + '</pre>' : '') + (f.fix ? '<div class="tiny"><b>Fix:</b> ' + esc(f.fix) + '</div>' : '') + '</div>').join('') :
    (['planned', 'done'].includes(l.status) ? '<p class="muted tiny">No findings.</p>' : '');
  $('#loadFindings').querySelectorAll('[data-copy]').forEach(b => b.onclick = () => copyValue(b));
  $('#loadFindings').querySelectorAll('[data-help]').forEach(b => b.onclick = () => openHelp(b.dataset.help));
  // the page re-renders on every poll: what the reader opened stays open, and the log keeps its place
  const planOpen = openState($('#loadPlan'));
  $('#loadPlan').innerHTML = l.plan ? '<h3>Plan</h3><div class="plan">' + renderPlan(l.plan) + '</div>' : '';
  restoreOpen($('#loadPlan'), planOpen);
  renderRangers(l);
  const p = l.progress;
  const prevLog = $('#loadProgress details'), prevPre = prevLog && prevLog.querySelector('pre');
  const logOpen = prevLog ? prevLog.open : active;
  const atBottom = !prevPre || prevPre.scrollHeight - prevPre.scrollTop - prevPre.clientHeight < 12, scrollTop = prevPre ? prevPre.scrollTop : 0;
  $('#loadProgress').innerHTML = (p && p.patrols_total && l.mode !== 'plan' ? '<h3>Progress</h3><div class="bar"><div style="width:' + (100 * p.done / p.patrols_total).toFixed(1) + '%"></div></div><p class="tiny">' + esc(importSummary(l, active)) + '</p>' : '') +
    (l.continuations ? '<p class="tiny">Continued ' + esc(l.continuations) + ' time(s) past the job limit.</p>' : '') +
    (l.log_tail ? '<details' + (logOpen ? ' open' : '') + '><summary class="tiny">Log' + (active ? ' (live)' : ' tail') + '</summary><pre class="log">' + esc(l.log_tail) + '</pre></details>' : '') +
    '<p class="tiny">Files: ' + ['plan.json', 'findings.json', 'checklist.json', 'checklist.md', 'rangers.json', 'import-ledger.json', 'log.txt'].map(n => '<a href="/api/loads/' + esc(l.id) + '/files/' + n + '" download>' + n + '</a>').join(' · ') + '</p>';
  const pre = $('#loadProgress pre.log');
  if (pre) pre.scrollTop = atBottom ? pre.scrollHeight : scrollTop;
  if (active) loadTimer = setTimeout(() => renderLoad().catch(() => {}), 4000);
}

const openState = host => Array.from(host.querySelectorAll('details')).map(d => d.open);
const restoreOpen = (host, state) => host.querySelectorAll('details').forEach((d, i) => { if (state[i] !== undefined) d.open = state[i]; });

async function copyValue(btn) {
  const icon = btn.querySelector('.mi');
  try { await navigator.clipboard.writeText(btn.dataset.copy); icon.textContent = 'check'; }
  catch (e) { window.prompt('Copy this value:', btn.dataset.copy); return; }
  setTimeout(() => { icon.textContent = 'content_copy'; }, 1500);
}

// ---- help: a drawer of sections, deep-linked by heading id (a finding opens finding-<code>)
let HELP = null, helpLoading = null, helpOpener = null;
async function openHelp(anchor) {
  const drawer = $('#help'), body = $('#helpBody');
  // the opener is remembered by its help id: the load page re-renders its buttons on every poll
  const a = document.activeElement;
  helpOpener = a && a.dataset && a.dataset.help ? { help: a.dataset.help } : { node: a };
  if (!HELP) {
    // one fetch, however many clicks arrive while it is pending; a failure alerts once and resolves null for all
    helpLoading = helpLoading || api('/api/help').then(r => r.sections, e => { helpLoading = null; alert(e.message); return null; });
    const sections = await helpLoading;
    if (!sections) return;
    if (!HELP) {
      HELP = sections;
      body.innerHTML = HELP.map(s => '<section id="help-' + esc(s.id) + '"><h2>' + esc(s.title) + '</h2>' + s.html + '</section>').join('');
      $('#helpToc').innerHTML = HELP.map(s => '<button class="link" data-goto="help-' + esc(s.id) + '">' + esc(s.title) + '</button>').join('');
      $('#helpToc').querySelectorAll('button').forEach(b => b.onclick = () => gotoHelp(b.dataset.goto));
      body.querySelectorAll('a[href^="#"]').forEach(a => a.onclick = ev => { ev.preventDefault(); gotoHelp(a.getAttribute('href').slice(1)); });
    }
  }
  drawer.hidden = false; $('#helpBackdrop').hidden = false;
  if (anchor) gotoHelp(anchor);
  else {
    $('#helpNote').hidden = true;
    let saved = 0; try { saved = Number(localStorage.getItem('help.scroll') || 0); } catch (e) {}
    body.scrollTo({ top: saved, behavior: 'instant' }); helpScrolled();
  }
  $('#helpClose').focus();
}

function gotoHelp(id) {
  const body = $('#helpBody'), note = $('#helpNote');
  let el = body.querySelector('#' + CSS.escape(id));
  note.hidden = true;
  if (!el && /^finding-/.test(id)) {   // a finding without an entry yet: say so rather than land silently
    el = body.querySelector('#help-stops');
    note.textContent = 'No help entry yet for the finding "' + id.slice(8) + '". The finding\'s own fix text is the guidance.';
    note.hidden = false;
  }
  if (!el) return;
  body.querySelectorAll('.target').forEach(t => t.classList.remove('target'));
  if (/^finding-/.test(id)) { el.classList.add('target'); }
  body.scrollTo({ top: el.offsetTop - 8, behavior: 'instant' });   // a jump, so the highlight below reads the new position
  helpScrolled();
}

function closeHelp() {
  try { localStorage.setItem('help.scroll', String($('#helpBody').scrollTop)); } catch (e) {}
  $('#helpNote').hidden = true;
  $('#helpBody').querySelectorAll('.target').forEach(t => t.classList.remove('target'));
  $('#help').hidden = true; $('#helpBackdrop').hidden = true;
  const back = helpOpener && (helpOpener.help ? $('[data-help="' + CSS.escape(helpOpener.help) + '"]') : helpOpener.node);
  if (back && back.focus && document.contains(back)) back.focus();
}

function helpScrolled() {
  const body = $('#helpBody'), top = body.scrollTop + 40;
  let current = null;
  body.querySelectorAll('section').forEach(s => { if (s.offsetTop <= top) current = s.id; });
  $('#helpToc').querySelectorAll('button').forEach(b => b.classList.toggle('current', b.dataset.goto === current));
}

function helpKeydown(e) {   // a dialog keeps Tab inside it
  if (e.key !== 'Tab') return;
  const drawer = $('#help');
  const f = Array.from(drawer.querySelectorAll('button, a[href], [tabindex]:not([tabindex="-1"])')).filter(x => x.offsetParent !== null);
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

// ---- the stage table: one row per stage, what it did, and how long it took
const fmtDur = s => { s = Math.max(0, Math.round(s)); const m = Math.floor(s / 60), h = Math.floor(m / 60); return h ? h + ' h ' + (m % 60) + ' min' : m ? m + ' min ' + (s % 60) + ' s' : s + ' s'; };
const secondsSince = iso => iso ? (Date.now() - Date.parse(iso)) / 1000 : null;
const count = (n, one, many) => n.toLocaleString() + ' ' + (n === 1 ? one : (many || one + 's'));

const notStarted = l => ['queued', 'planning'].includes(l.status);   // claimed, but the job has not reset the rows yet

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
  const mins = since ? (Date.now() - Date.parse(since)) / 60000 : null;
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

// ---- rangers: the markup is renderRangersSection (pages.js); this binds its help and CSV buttons
function bindRangers(host, l) {
  const rows = l.rangers || [];
  host.querySelector('[data-help]').onclick = ev => { ev.preventDefault(); openHelp('rangers-accounts'); };
  host.querySelector('[data-csv]').onclick = ev => { ev.preventDefault(); downloadCsv('rangers-' + l.ca_id + '.csv', ['name', 'smart_employee_id', 'smart_member_id', 'active', 'deleted_in_smart', 'patrols_this_load', 'patrols_all', 'subject_id', 'email'],
    rows.map(r => [r.name, r.smart_employee_id, r.smart_member_id, r.active, !!r.deleted, r.patrols, r.patrols_total, r.subject_id, ''])); };
}
function renderRangers(l) {
  const host = $('#loadRangers'), rows = l.rangers || [], total = l.rangers_total || rows.length;
  if (!rows.length) { host.innerHTML = ''; host.dataset.key = ''; return; }
  // the rows change only when patrol setup runs: a poll that brings the same list leaves the table alone
  const key = l.id + ':' + total + ':' + JSON.stringify(rows);
  if (host.dataset.key === key && host.firstChild) return;
  host.dataset.key = key;
  const open = openState(host);
  host.innerHTML = renderRangersSection(l);
  restoreOpen(host, open);
  bindRangers(host, l);
}

function downloadCsv(filename, header, rows) {
  // a cell that a spreadsheet would read as a formula gets a leading quote (names and ids come from the SMART export)
  const cell = v => { let s = v == null ? '' : String(v); if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  // the byte-order mark makes Excel read the names as UTF-8, so an accented name copies out as it is on the site
  const blob = new Blob(['\ufeff' + [header, ...rows].map(r => r.map(cell).join(',')).join('\n') + '\n'], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
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

boot();
