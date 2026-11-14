// smart-able web: sign in, list datasets, upload + extract, share, open.
const $ = (s, el = document) => el.querySelector(s);
let CONFIG = null, ME = null, pollTimer = null;

async function api(path, opts = {}) {
  const r = await fetch(path, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) }, ...opts });
  if (r.status === 401) { showSignIn(); const err = new Error('Sign in required'); err.status = 401; throw err; }
  if (!r.ok) { let d = ''; try { d = (await r.json()).detail; } catch (e) {} const err = new Error(d || r.statusText); err.status = r.status; throw err; }
  return r.status === 204 ? null : r.json();
}

function showSignIn(err) {
  clearTimeout(pollTimer); clearTimeout(loadTimer); currentLoad = null;
  listGen++; datasetGen++; loadGen++; sitesGen++;   // a page fetch still in flight cannot paint over the form
  mountHeader(false); setBreadcrumb(null);
  mountPage(renderSignIn(CONFIG));
  $('#signInBtn').onclick = signIn;
  $('#signInError').textContent = err || '';
}
function showApp() {
  mountHeader(true);
  $('#whoEmail').textContent = ME.email; $('#menuEmail').textContent = ME.email;   // the menu shows it where the band has no room
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
// one show* per page
function renderRoute(route) {
  clearTimeout(pollTimer); clearTimeout(loadTimer); listGen++;   // leaving a page: its poll and any response in flight stop
  if (route.page === 'home') showHome();
  else if (route.page === 'dataset') showDataset(route);
  else if (route.page === 'load') showLoad(route);
  else if (route.page === 'sites') showSites();
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
  } catch (e) { if (e.status !== 401 && location.hash === mine) navigate({ page: 'home' }, 'replace'); }
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
  // an open dialog takes the keys first (it sits above the help drawer); Escape closes one layer at a time
  document.addEventListener('keydown', e => { if (!$('#modal').hidden) modalKeydown(e); else if (e.key === 'Escape' && !$('#help').hidden) closeHelp(); });
  document.querySelectorAll('input[name="theme"]').forEach(r => { r.onchange = () => setTheme(r.value); });
  $('#menuSites').onclick = () => { $('#account').open = false; navigate({ page: 'sites' }); };
  // the menu closes on a click outside it or Escape, like any menu
  document.addEventListener('click', e => { if ($('#account').open && !$('#account').contains(e.target)) $('#account').open = false; });
  $('#account').onkeydown = e => { if (e.key === 'Escape') { $('#account').open = false; $('#whoEmail').focus(); } };
  $('#signOut').onclick = async () => { $('#account').open = false; await api('/api/signout', { method: 'POST' }); if (!CONFIG.authDisabled) await firebase.auth().signOut(); showSignIn(); };
  $('#modalClose').onclick = closeDialog;
  // the title goes home from anywhere in the app; signed in, without reloading the page
  $('#home').onclick = e => { if (ME) { e.preventDefault(); if (!$('#help').hidden) closeHelp(); if (!$('#modal').hidden) closeDialog(); showDatasets(); } };
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
  try { list = await api('/api/datasets'); } catch (e) { if (gen === listGen && e.status !== 401) mountPage('<p class="empty">' + esc(e.message) + '</p>'); return; }
  if (gen !== listGen) return;
  mountPage(renderHome(list));
  $('#uploadBtn').onclick = uploadDialog;
  pollHome(list, gen);
}
// while any dataset is queued or running, refetch every 5 s and replace only the card list
// ('uploading' is not polled: the tab doing the upload shows its own progress, and an abandoned one never changes)
function pollHome(list, gen, fails = 0) {
  clearTimeout(pollTimer);
  if (!list.some(d => ['queued', 'running'].includes(d.status))) return;
  pollTimer = setTimeout(async () => {
    let next;
    try { next = await api('/api/datasets'); }
    catch (e) {
      if (gen !== listGen || e.status === 401) return;
      retryNote($('#page .page-head'), fails + 1 >= 2);
      return pollHome(list, gen, fails + 1);
    }
    const host = $('#cards');
    if (gen !== listGen || !host) return;
    retryNote($('#page .page-head'), false);
    const html = renderCardList(next);
    if (html !== host.dataset.html) { host.innerHTML = html; host.dataset.html = html; }
    pollHome(next, gen);
  }, 5000);
}
// a poll that fails keeps the last render and retries; from the second failure in a row a note under `after` says so
function retryNote(after, show) {
  if (!after) return;
  const next = after.nextElementSibling, shown = !!(next && next.hasAttribute('data-retry'));
  if (show && !shown) after.insertAdjacentHTML('afterend', '<p class="tiny" data-retry>Could not refresh; retrying…</p>');
  else if (!show && shown) next.remove();
}

// a form that brings its own Close beside its submit button (data-close) hides the dialog's own.
// Focus moves to the first field, Tab stays inside, Escape is the visible Close, and closing returns
// focus to what opened it. A dialog that replaces an open one (a re-render, the add-a-site detour)
// keeps the first opener. Closing only hides: an upload in flight carries on.
let modalOpener = null;
function dialog(title, bodyHtml) {
  if ($('#modal').hidden) modalOpener = document.activeElement;
  $('#modalTitle').textContent = title; $('#modalBody').innerHTML = bodyHtml;
  const own = $('#modalBody').querySelector('[data-close]');
  $('#modalFoot').hidden = !!own; if (own) own.onclick = closeDialog;
  $('#modal').hidden = false;
  const first = modalFocusables()[0]; if (first) first.focus();
}
function closeDialog() {
  $('#modal').hidden = true;
  const back = modalOpener; modalOpener = null;
  if (back && back.focus && document.contains(back)) back.focus();
}
function modalFocusables() {
  return Array.from($('#modal').querySelectorAll('button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])'))
    .filter(x => !x.disabled && x.offsetParent !== null);
}
function modalKeydown(e) {   // the helpKeydown pattern, plus Escape and a focus that has strayed outside
  if (e.key === 'Escape') {
    e.preventDefault(); e.stopPropagation();
    ($('#modalBody').querySelector('[data-close]') || $('#modalClose')).click();   // the site dialog's onCancel rides on its Close
    return;
  }
  if (e.key !== 'Tab') return;
  const f = modalFocusables();
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1], inside = $('#modal').contains(document.activeElement);
  if (!inside) { e.preventDefault(); (e.shiftKey ? last : first).focus(); }
  else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

function shareDialog(d, base = '/api/datasets/', note) {
  const refresh = () => { if (base === '/api/sites/') return showSites(); const r = parseRoute(location.hash); if (r.page === 'home') showHome(); else if (r.page === 'dataset') showDataset(r); };
  note = note || 'People you share with can open the dataset. Only you can share, re-extract, or delete it.';
  const allowed = Array.isArray(CONFIG.allowed) ? CONFIG.allowed : CONFIG.allowed ? [CONFIG.allowed] : [];
  const domain = allowed.find(e => e.startsWith('@'));   // the placeholder's suggestion; whole addresses give none
  const render = shared => {
    dialog('Share "' + d.name + '"',
      '<p class="muted tiny">' + esc(note) + (allowed.length ? ' Addresses must be ' + (allowed.length === 1 ? esc(allowed[0]) : 'one of ' + allowed.map(esc).join(', ')) + '.' : '') + '</p>' +
      '<form id="shareForm" class="row"><input type="email" id="shareEmail" placeholder="colleague' + esc(domain || '@example.org') + '" required><button type="submit" class="primary">Share</button></form>' +
      '<div class="shared"><ul>' + (shared.length ? shared.map(e => '<li><span class="mi" aria-hidden="true">person</span>' + esc(e) + ' <button class="ghost" data-unshare="' + esc(e) + '" title="Remove"><span class="mi" aria-hidden="true">close</span></button></li>').join('') : '<li class="tiny">Not shared with anyone yet.</li>') + '</ul></div>');
    $('#shareForm').onsubmit = async ev => { ev.preventDefault(); try { const r = await api(base + d.id + '/share', { method: 'POST', body: JSON.stringify({ email: $('#shareEmail').value }) }); render(r.shared_with); refresh(); } catch (e) { alert(e.message); } };
    $('#modalBody').querySelectorAll('[data-unshare]').forEach(b => b.onclick = async () => { try { const r = await api(base + d.id + '/share/' + encodeURIComponent(b.dataset.unshare), { method: 'DELETE' }); render(r.shared_with); refresh(); } catch (e) { alert(e.message); } });
  };
  render(d.shared_with || []);
}

// a dataset or load the reader cannot open: the dead route's entry becomes the list's address, so Back
// never lands on it; the page stays the not-found notice
function showNotFound(what) {
  history.replaceState({ from: (history.state || {}).from }, '', location.pathname + location.search + routeHash({ page: 'home' }));
  setBreadcrumb([{ label: 'Datasets', hash: '#/' }, { label: 'Not found' }]);
  mountPage(renderNotFound(what));
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
    if (e.status === 401) return;   // the sign-in form is already on the page
    if (e.status === 404) showNotFound('dataset'); else { setBreadcrumb(null); mountPage('<p class="empty">' + esc(e.message) + '</p>'); }
    return;
  }
  if (!current()) return;
  let tab = route.tab;
  if (tab !== 'overview' && !hasLoadTabs(d)) { tab = 'overview'; navigate({ page: 'dataset', id: d.id, tab }, 'replace'); return; }
  const extra = {};
  try {
    if (tab === 'loads') extra.loads = await api('/api/datasets/' + d.id + '/loads');
    else if (tab === 'rangers') {
      const loads = (await api('/api/datasets/' + d.id + '/loads')).slice().sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
      // the list items carry no rangers: the newest load that has some is found by fetching, newest first
      for (const l of loads) { if (!current()) return; const full = await api('/api/loads/' + l.id); if ((full.rangers || []).length) { extra.load = full; break; } }
    }
  } catch (e) { if (!current() || e.status === 401) return; mountPage('<p class="empty">' + esc(e.message) + '</p>'); return; }
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
  const lb = $('#loadBtn'); if (lb) lb.onclick = () => loadDialog(d, (d.export.find(hasBundle) || {}).dir);
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
    const onScreen = () => !$('#modal').hidden && $('#modalBody').contains(form);   // closed or replaced: the reader cannot see it
    btn.disabled = true; prog.hidden = false; fill.style.width = '0%'; text.textContent = 'Preparing…';
    try {
      const created = await api('/api/datasets', { method: 'POST', body: JSON.stringify({ name: $('#dsName', form).value, filename: file.name, size: file.size, content_type: file.type || 'application/zip' }) });
      if (parseRoute(location.hash).page === 'home') showHome();       // the new dataset appears, uploading, even if the dialog is closed
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
      if (onScreen()) closeDialog();                                   // still on screen: close it
      if (parseRoute(location.hash).page === 'home') showHome();       // the new dataset appears, extracting
    } catch (e) {
      if (onScreen()) { text.textContent = e.message; btn.disabled = false; }
      else if (e.status !== 401) alert(e.message);                     // the form is gone: a note there would never be seen
    }
  };
}

// ---- the sites page
let sitesGen = 0;
async function showSites() {
  clearTimeout(loadTimer); clearTimeout(pollTimer); currentLoad = null;
  const gen = ++sitesGen, mine = routeHash({ page: 'sites' });
  const current = () => gen === sitesGen && location.hash === mine;
  let list;
  try { list = await api('/api/sites'); }
  catch (e) {
    if (!current() || e.status === 401) return;
    setBreadcrumb(null); mountPage('<p class="empty">' + esc(e.message) + '</p>'); return;
  }
  if (!current()) return;
  setBreadcrumb([{ label: 'Datasets', hash: '#/' }, { label: 'EarthRanger sites' }]);
  mountPage(renderSites(list));
  $('#addSiteBtn').onclick = () => siteDialog();
  $('#page').querySelectorAll('button[data-act]').forEach(b => b.onclick = async () => {
    const s = list.find(x => x.id === b.dataset.id);
    try {
      if (b.dataset.act === 'siteShare') return shareDialog(s, '/api/sites/', 'People you share with can load datasets into this site using your token.');
      if (!confirm('Remove "' + s.name + '"? Loads that reference this site stay readable but cannot be continued; register the site again to load into it.')) return;
      await api('/api/sites/' + s.id, { method: 'DELETE' }); showSites();
    } catch (e) { if (e.status !== 401) alert(e.message); }
  });
}

// the add-site dialog. The token is read from the field on submit and goes only to the POST.
// onCreated(site) runs after a successful save; onCancel runs when the reader closes the dialog instead.
function siteDialog(onCreated, onCancel) {
  dialog('Add an EarthRanger site',
    '<p class="muted tiny">The token is checked against the site before it is saved.</p>' +
    '<form id="siteForm" class="col" autocomplete="off">' +
    '<label class="field"><span>Name</span><input type="text" id="siteName" required placeholder="phinney"></label>' +
    '<label class="field"><span>Host</span><input type="text" id="siteUrl" required placeholder="example.pamdas.org"></label>' +
    '<label class="field"><span>Token</span><input type="password" id="siteToken" autocomplete="off" required></label>' +
    '<p class="tiny" id="siteError" role="alert"></p>' +
    '<div class="row right"><button type="button" class="ghost" data-close>Close</button><button type="submit" class="primary" id="siteBtn">Add site</button></div></form>');
  const close = $('#modalBody').querySelector('[data-close]'), plain = close.onclick;
  close.onclick = () => { plain(); if (onCancel) onCancel(); };
  $('#siteForm').onsubmit = async ev => {
    ev.preventDefault();
    const btn = $('#siteBtn'), err = $('#siteError'); btn.disabled = true; err.textContent = 'Checking the token…';
    try {
      const site = await api('/api/sites', { method: 'POST', body: JSON.stringify({ name: $('#siteName').value, url: $('#siteUrl').value, token: $('#siteToken').value }) });
      closeDialog();
      if (parseRoute(location.hash).page === 'sites') showSites();
      if (onCreated) onCreated(site);
    } catch (e) { if (e.status === 401) return; err.textContent = e.message; btn.disabled = false; }
  };
}

// mirrors findings.ca_identifier: smart-<ca id>, 2-30 chars of [A-Za-z0-9_-]
function defaultEventCategory(caId) {
  const s = ('smart-' + (caId || 'ca')).toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
  return (s.length >= 2 ? s : 'smart-ca').slice(0, 30);
}

// keep: the form's values and site choice, when the dialog is reopened after the add-a-site detour
async function loadDialog(d, caId, keep) {
  let sites;
  try { sites = await api('/api/sites'); } catch (e) { if (e.status !== 401) alert(e.message); return; }   // 401: the sign-in form is up
  if (!sites.length) return siteDialog(() => loadDialog(d, caId));
  const addSite = kept => siteDialog(site => loadDialog(d, kept.ca || caId, { ...kept, site: site.id }), () => loadDialog(d, kept.ca || caId, kept));
  let lastDefault = null, autoDm = false;
  const render = () => {
    const ca = d.export.find(e => e.dir === $('#ldCa').value) || d.export[0];
    // an area with no patrols has only its data model to load; leaving it for one with patrols undoes that choice
    if (!ca.patrols) { $('#ldScope').value = 'datamodel'; autoDm = true; } else if (autoDm) { $('#ldScope').value = 'all'; autoDm = false; }
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
    '<label>Site <select id="ldSite">' + sites.map(s => '<option value="' + esc(s.id) + '">' + esc(s.name) + ' · ' + esc(s.url) + '</option>').join('') + '<option value="__add__">Add a site…</option></select></label>' +
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
  const ids = ['ldRoster', 'ldCategory', 'ldScope', 'ldSince', 'ldUntil'];
  if (keep && keep.ca) $('#ldCa').value = keep.ca;
  render();
  if (keep) { ids.forEach(i => { $('#' + i).value = keep[i]; }); $('#ldLang').value = keep.ldLang; $('#ldCm').value = keep.ldCm; if (keep.site) $('#ldSite').value = keep.site; lastDefault = $('#ldCategory').value; }
  scopeChanged(); $('#ldCa').onchange = () => { render(); scopeChanged(); }; $('#ldScope').onchange = scopeChanged;
  let prevSite = $('#ldSite').value;
  $('#ldSite').onchange = () => {
    if ($('#ldSite').value !== '__add__') { prevSite = $('#ldSite').value; return; }
    const kept = { ca: $('#ldCa').value, site: prevSite, ldLang: $('#ldLang').value, ldCm: $('#ldCm').value };
    ids.forEach(i => { kept[i] = $('#' + i).value; });
    addSite(kept);
  };
  $('#ldForm').onsubmit = async ev => {
    ev.preventDefault();
    const dm = $('#ldScope').value === 'datamodel', since = dm ? '' : $('#ldSince').value, until = dm ? '' : $('#ldUntil').value;
    if (since && until && since > until) return alert('The window starts after it ends.');
    try {
      const l = await api('/api/datasets/' + d.id + '/loads', { method: 'POST', body: JSON.stringify({ ca_id: $('#ldCa').value, site_id: $('#ldSite').value,
        options: { language: $('#ldLang').value, configurable_model: $('#ldCm').value || null, roster_group: $('#ldRoster').value,
        event_category: $('#ldCategory').value.trim(), scope: $('#ldScope').value, since: since || null, until: until || null } }) });
      closeDialog(); navigate({ page: 'load', id: d.id, load: l.id });
    } catch (e) { alert(e.message); }
  };
}

// ---- the load page
let loadTimer = null, currentLoad = null, loadGen = 0;
// the home link: from any other page it steps back when that page was opened from the list, else pushes
// the list, so Back returns to the page; on the list itself it only rewrites the entry
function showDatasets() {
  const onHome = parseRoute(location.hash).page === 'home';
  if (!onHome && (history.state || {}).from === '#/') { history.back(); return; }   // popstate shows the list
  navigate({ page: 'home' }, onHome ? 'replace' : 'push');
}

// the load, its dataset's name for the breadcrumb, then the page; polls every 4 s while the load is held
async function showLoad(route) {
  clearTimeout(loadTimer); clearTimeout(pollTimer);
  currentLoad = route.load;
  const gen = ++loadGen, mine = routeHash(route);
  const current = () => gen === loadGen && location.hash === mine;
  let l;
  try { l = await api('/api/loads/' + route.load); }
  catch (e) {
    if (!current() || e.status === 401) return;   // on 401 the sign-in form is already on the page
    if (e.status === 404) showNotFound('load'); else { setBreadcrumb(null); mountPage('<p class="empty">' + esc(e.message) + '</p>'); }
    return;
  }
  if (!current()) return;
  if (l.dataset_id !== route.id) { navigate({ page: 'load', id: l.dataset_id, load: l.id }, 'replace'); return; }   // the address names the wrong dataset
  let name = l.dataset_id;   // without the dataset's name the crumb shows its id rather than failing the page
  try { name = (await api('/api/datasets/' + l.dataset_id)).name || name; } catch (e) { if (e.status === 401) return; }
  if (!current()) return;
  const up = { page: 'dataset', id: l.dataset_id, tab: 'loads' };
  setBreadcrumb([{ label: 'Datasets', hash: '#/' }, { label: name, hash: routeHash(up) }, { label: loadName(l) }]);
  // the dataset crumb steps back when the reader came from that dataset's page, so Back after it does not return here
  const crumb = $('#crumbs a[href="' + routeHash(up) + '"]');
  if (crumb) crumb.onclick = ev => {
    ev.preventDefault();
    const from = parseRoute((history.state || {}).from);
    if (from.page === 'dataset' && from.id === l.dataset_id) history.back(); else navigate(up);
  };
  let fails = 0;
  const refresh = async () => {
    clearTimeout(loadTimer);
    let next;
    try { next = await api('/api/loads/' + route.load); }
    catch (e) {
      if (!current() || e.status === 401) return;
      if (e.status === 404) { showNotFound('load'); return; }
      // a failed poll keeps the last render and retries; from the second in a row a note says so
      retryNote($('#loadPage .title-block'), ++fails >= 2);
      clearTimeout(loadTimer); loadTimer = setTimeout(refresh, 4000);
      return;
    }
    if (!current()) return;
    fails = 0;
    paint(next);
  };
  const paint = x => {
    paintLoad(x, refresh, up);
    clearTimeout(loadTimer);   // a click's refresh and a poll can both land: one timer stays
    if (x.held) loadTimer = setTimeout(refresh, 4000);
  };
  paint(l);
}

// swaps in a fresh render: open sections stay open, the log keeps its place, and a rangers table whose rows
// are unchanged is left as it is (its rows change only when patrol setup runs)
function paintLoad(l, refresh, up) {
  const active = !!l.held, prev = $('#loadPage'), old = prev && prev.dataset.load === l.id ? prev : null;   // another load's page carries nothing over
  const box = document.createElement('div'); box.innerHTML = renderLoadPage(l, active);
  const page = box.firstElementChild;
  page.dataset.load = l.id;
  const rows = l.rangers || [], key = rows.length ? l.id + ':' + (l.rangers_total || rows.length) + ':' + JSON.stringify(rows) : '';
  let newRangers = true;
  const oldPre = old && $('#loadProgress pre.log', old);
  const atBottom = !oldPre || oldPre.scrollHeight - oldPre.scrollTop - oldPre.clientHeight < 12, scrollTop = oldPre ? oldPre.scrollTop : 0;
  if (old) {
    restoreOpen($('#loadPlan', page), openState($('#loadPlan', old)));
    const oldLog = $('#loadProgress details', old), log = $('#loadProgress details', page);
    if (oldLog && log) log.open = oldLog.open;
    const oldR = $('#loadRangers', old), r = $('#loadRangers', page);
    if (key && oldR.dataset.key === key && oldR.firstChild) { r.replaceWith(oldR); newRangers = false; }
    else restoreOpen(r, openState(oldR));
  }
  $('#loadRangers', page).dataset.key = key;
  $('#page').replaceChildren(page);
  const pre = $('#loadProgress pre.log', page);
  if (pre) pre.scrollTop = atBottom ? pre.scrollHeight : scrollTop;
  bindLoad(page, l, refresh, up, newRangers);
}

function bindLoad(page, l, refresh, up, newRangers) {
  $('.title-block [data-help]', page).onclick = () => openHelp('help-statuses');
  const run = $('[data-run]', page); if (run) run.onclick = async () => { try { await api('/api/loads/' + l.id + '/run', { method: 'POST' }); refresh(); } catch (e) { alert(e.message); } };
  const re = $('[data-replan]', page); if (re) re.onclick = async () => { try { await api('/api/loads/' + l.id + '/replan', { method: 'POST' }); refresh(); } catch (e) { alert(e.message); } };
  const del = $('[data-del]', page); if (del) del.onclick = async () => {
    if (!confirm('Delete this load\'s records? Nothing in EarthRanger is removed.')) return;
    try {
      await api('/api/loads/' + l.id, { method: 'DELETE' });
      // the deleted load's entry becomes its dataset's loads, so Back never lands on it; if the reader has
      // moved on meanwhile, the page they are on is left alone and a list they are on is refreshed
      if (location.hash === routeHash({ page: 'load', id: up.id, load: l.id })) navigate(up, 'replace');
      else { const r = parseRoute(location.hash); if (r.page === 'home') showHome(); else if (r.page === 'dataset') showDataset(r); }
    } catch (e) { alert(e.message); }
  };
  $('#loadFindings', page).querySelectorAll('[data-copy]').forEach(b => b.onclick = () => copyValue(b));
  $('#loadFindings', page).querySelectorAll('[data-help]').forEach(b => b.onclick = () => openHelp(b.dataset.help));
  if (newRangers && (l.rangers || []).length) bindRangers($('#loadRangers', page), l);
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

// ---- rangers: the markup is renderRangersSection (pages.js); this binds its help and CSV buttons
function bindRangers(host, l) {
  const rows = l.rangers || [];
  host.querySelector('[data-help]').onclick = ev => { ev.preventDefault(); openHelp('rangers-accounts'); };
  host.querySelector('[data-csv]').onclick = ev => { ev.preventDefault(); downloadCsv('rangers-' + l.ca_id + '.csv', ['name', 'smart_employee_id', 'smart_member_id', 'active', 'deleted_in_smart', 'patrols_this_load', 'patrols_all', 'subject_id', 'email'],
    rows.map(r => [r.name, r.smart_employee_id, r.smart_member_id, r.active, !!r.deleted, r.patrols, r.patrols_total, r.subject_id, ''])); };
}
function downloadCsv(filename, header, rows) {
  // a cell that a spreadsheet would read as a formula gets a leading quote (names and ids come from the SMART export)
  const cell = v => { let s = v == null ? '' : String(v); if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  // the byte-order mark makes Excel read the names as UTF-8, so an accented name copies out as it is on the site
  const blob = new Blob(['\ufeff' + [header, ...rows].map(r => r.map(cell).join(',')).join('\n') + '\n'], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

boot();
