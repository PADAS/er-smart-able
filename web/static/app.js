// smart-able web: sign in, list datasets, upload + extract, share, open.
const $ = (s, el = document) => el.querySelector(s);
let CONFIG = null, ME = null, pollTimer = null;

async function api(path, opts = {}) {
  const r = await fetch(path, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) }, ...opts });
  if (r.status === 401) { showSignIn(); const err = new Error(t('errors.signin_required')); err.status = 401; throw err; }
  if (!r.ok) { let b = null; try { b = await r.json(); } catch (e) {} const err = new Error(errorMessage(r.status, r.statusText, b)); err.status = r.status; throw err; }
  return r.status === 204 ? null : r.json();
}

// a dialog or the help drawer belongs to the page it was opened on: leaving that page closes it
function closeLayers() { if (!$('#modal').hidden) closeDialog(); if (!$('#help').hidden) closeHelp(); }
// an action that failed says why; on a 401 the sign-in form is already up and says it
function oops(e) { if (e.status !== 401) alert(e.message); }
function showSignIn(err) {
  ME = null;       // signed out: Back, the lockup and Help do nothing until the next sign-in
  closeLayers();   // the form must not sit behind a dialog's scrim
  clearTimeout(pollTimer); clearTimeout(loadTimer); currentLoad = null;
  listGen++; datasetGen++; loadGen++;   // a page fetch still in flight cannot paint over the form
  setRail(null);
  mountPage(renderSignIn(CONFIG));
  $('#signInBtn').onclick = signIn;
  $('#signInError').textContent = err || '';
}
function showApp() {
  navigate(parseRoute(location.hash), 'replace');   // the address says which page; the first entry is that page
}

// ---- the shell: the sidebar (nav.js) and one page container
function mountPage(html) { $('#page').innerHTML = html; }
// What the sidebar shows: the route, and the dataset once it is known. Signed out (route null) it holds
// only the theme and the language. Drawn again whenever the route, the dataset, the language or the theme changes.
let railRoute = null, railDataset = null, railHtml = null;
function setRail(route, dataset) { railRoute = route || null; railDataset = dataset || null; drawRail(); }
function drawRail() {
  const html = renderRail(railState(ME ? railRoute : null, ME, { dataset: railDataset, lang: currentLang(), languages: LANGS, theme: themeChoice, version: $('meta[name="app-version"]').content, open: document.documentElement.dataset.nav !== 'closed' }), k => T(k));
  if (html === railHtml) return;   // a page's refresh draws nothing new: an open menu and the scroll place stay
  railHtml = html;
  $('#rail').innerHTML = html;
  $('#railToggle').onclick = () => setNav(document.documentElement.dataset.nav === 'closed' ? 'open' : 'closed');
  $('#rail').querySelectorAll('input[name="theme"]').forEach(r => { r.onchange = () => setTheme(r.value); });
  $('#lang').onchange = async () => {
    await useLang($('#lang').value, true);
    closeLayers();   // a dialog or the drawer holds the old language
    if (ME) renderRoute(parseRoute(location.hash)); else showSignIn();
    $('#lang').focus();   // the menu was drawn again in the new language: the keyboard stays on it
  };
  // folded, a menu has no room to open: its icon opens the sidebar first
  $('#rail').querySelectorAll('.rail-menu > summary, .rail-lang').forEach(el => el.addEventListener('click', () => { if (document.documentElement.dataset.nav === 'closed') setNav('open'); }));
  // on a narrow screen the open sidebar lies over the page: choosing an entry folds it
  $('#rail').querySelectorAll('a[data-nav]').forEach(a => a.addEventListener('click', () => { if (narrow()) setNav('closed'); }));
  if (!$('#helpBtn')) return;   // signed out: no help, no account
  $('#helpBtn').onclick = () => openHelp();
  $('#account').onkeydown = e => { if (e.key === 'Escape') { $('#account').open = false; $('#whoEmail').focus(); } };
  $('#signOut').onclick = async () => { await api('/api/signout', { method: 'POST' }); if (!CONFIG.authDisabled) await firebase.auth().signOut(); showSignIn(); };
}
// the sidebar is open (icons and words) or closed (icons); the choice is remembered, and shared with the data browser
function narrow() { return window.innerWidth < 700; }
function setNav(state, remember) {
  document.documentElement.dataset.nav = state === 'closed' ? 'closed' : 'open';
  if (remember !== false) { try { localStorage.sidenav = document.documentElement.dataset.nav; } catch (e) { /* storage blocked: the choice lasts this page */ } }
  const toggle = $('#railToggle');
  if (toggle) toggle.setAttribute('aria-expanded', String(state !== 'closed'));
  railHtml = null;   // the markup on the page no longer matches the last draw
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
  closeLayers();
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
// In-app links. A link to the address already shown changes nothing, so no popstate fires and the router never runs.
// That is the not-found notice's case: its entry was rewritten to #/ and its links point at #/. Render it here.
document.addEventListener('click', e => {
  if (!ME || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.target.closest && e.target.closest('a[href^="#/"]');
  if (!a || a.getAttribute('aria-disabled') === 'true' || a.target) return;
  e.preventDefault();
  // every in-app link goes through navigate, so its entry records where the reader came from (the
  // home link and the load page's dataset crumb step back on that); the address already shown just renders
  if (a.getAttribute('href') === (location.hash || '#/')) renderRoute(parseRoute(location.hash));
  else navigate(parseRoute(a.getAttribute('href')));
});

// ---- language: the shell's fixed phrases carry data-i18n marks; English stays in the template as the first paint
const LANGS = JSON.parse($('#languages').textContent);
const loadedLangs = new Set();
async function loadMessages(lang) {
  const v = $('meta[name="locales-v"]').content;
  for (const l of lang === 'en' ? ['en'] : ['en', lang]) {
    if (loadedLangs.has(l)) continue;
    try {
      const r = await fetch('/static/locales/' + l + '.json?v=' + v);
      if (!r.ok) continue;   // no file: that language reads as English
      setMessages(l, await r.json()); loadedLangs.add(l);
    } catch (e) { /* offline or bad file: English stays */ }
  }
}
function applyShell() {
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-title]').forEach(el => el.setAttribute('title', t(el.dataset.i18nTitle)));
  document.querySelectorAll('[data-i18n-aria]').forEach(el => el.setAttribute('aria-label', t(el.dataset.i18nAria)));
}
async function useLang(lang, remember) {
  await loadMessages(lang);
  setLang(lang);
  document.documentElement.lang = lang;
  applyShell();
  drawRail();
  const entry = LANGS.find(l => l.code === lang);
  $('#langNote').hidden = !entry || entry.reviewed !== false;
  HELP = null; helpLoading = null; helpGen++;   // the help text is per language: fetched again on the next open, and a fetch still pending is dropped
  if (remember) { try { localStorage.lang = lang; } catch (e) { /* storage blocked: the choice lasts this page */ } }
}

async function boot() {
  let theme = 'system';
  try { theme = localStorage.theme || 'system'; } catch (e) { /* storage blocked */ }
  setTheme(theme);   // before the first fetch, so the page never flashes the other theme
  let stored = null;
  try { stored = localStorage.lang; } catch (e) { /* storage blocked */ }
  await useLang(pickLang(stored, navigator.languages, LANGS.map(l => l.code)), false);
  $('#railScrim').onclick = () => setNav('closed');
  CONFIG = await (await fetch('/api/config')).json();
  if (!CONFIG.authDisabled) {
    firebase.initializeApp({ apiKey: CONFIG.apiKey, authDomain: CONFIG.authDomain, projectId: CONFIG.projectId });
    if (CONFIG.authEmulatorUrl) firebase.auth().useEmulator(CONFIG.authEmulatorUrl);
  }
  $('#helpClose').onclick = closeHelp;
  $('#helpBody').onscroll = helpScrolled;
  $('#help').onkeydown = helpKeydown;
  $('#helpBackdrop').onclick = closeHelp;
  // an open dialog takes the keys first (it sits above the help drawer); Escape closes one layer at a time
  document.addEventListener('keydown', e => { if (!$('#modal').hidden) modalKeydown(e); else if (e.key === 'Escape' && !$('#help').hidden) closeHelp(); });
  // a menu in the sidebar closes on a click outside it, like any menu
  document.addEventListener('click', e => { document.querySelectorAll('#rail details[open]').forEach(m => { if (!m.contains(e.target)) m.open = false; }); });
  $('#modalClose').onclick = closeDialog;
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

// Support staff (ME.support) may list every user's datasets and sites; the switch on the home page
// says whether they are. The choice is kept in the browser. From anyone else it means nothing: the
// stored choice is ignored here, and the server ignores ?all=1.
function seesAll() {
  if (!(ME && ME.support)) return false;
  try { return localStorage.allUsers === '1'; } catch (e) { return false; }
}
function listQuery() { return seesAll() ? '?all=1' : ''; }

// the home page's polling: a fetch is current only while its gen is, so a superseded response is dropped
// toSites: arrived by the sites' own address (#/sites), so the page opens at that section
async function showHome() {
  clearTimeout(loadTimer); clearTimeout(pollTimer); currentLoad = null;
  const gen = ++listGen;
  setRail({ page: 'home' });
  let list;
  try { list = await api('/api/datasets' + listQuery()); } catch (e) { if (gen === listGen && e.status !== 401) mountPage('<p class="empty">' + esc(e.message) + '</p>'); return; }
  if (gen !== listGen) return;
  mountPage(renderHome(list, { support: !!(ME && ME.support), all: seesAll() }));
  $('#uploadBtn').onclick = uploadDialog;
  bindAllUsers(showHome);
  pollHome(list, gen);
}
// the sites page: its own address (#/sites), opened from the sidebar
async function showSites() {
  clearTimeout(loadTimer); clearTimeout(pollTimer); currentLoad = null;
  const gen = ++listGen;
  setRail({ page: 'sites' });
  let sites = null, error = '';
  try { sites = await api('/api/sites' + listQuery()); } catch (e) { if (e.status === 401) return; error = e.message; }
  if (gen !== listGen) return;
  mountPage(renderSitesPage(sites, error, { support: !!(ME && ME.support), all: seesAll() }));
  bindAllUsers(showSites);
  bindSites(sites || []);
}
// the support switch: one stored choice, which both lists follow
function bindAllUsers(redraw) {
  const everyone = $('#allUsers');
  if (everyone) everyone.onchange = () => {
    try { if (everyone.checked) localStorage.allUsers = '1'; else localStorage.removeItem('allUsers'); } catch (e) { /* storage blocked: the switch cannot be kept, so it stays off */ }
    redraw();
  };
}
// the sites section's buttons: add, and for a site's owner edit, share and remove. Each change redraws the page.
function bindSites(list) {
  const add = $('#addSiteBtn'); if (add) add.onclick = () => siteDialog();
  $('#page').querySelectorAll('#sites button[data-act]').forEach(b => b.onclick = async () => {
    const s = list.find(x => x.id === b.dataset.id);
    try {
      if (b.dataset.act === 'siteEdit') return siteEditDialog(s);
      if (b.dataset.act === 'siteShare') return shareDialog(s, '/api/sites/');
      if (!confirm(t('confirm.removeSite', { name: s.name }))) return;
      await api('/api/sites/' + s.id, { method: 'DELETE' }); showSites();
    } catch (e) { if (e.status !== 401) alert(e.message); }
  });
}
// while any dataset is queued or running, refetch every 5 s and replace only the card list
// ('uploading' is not polled: the tab doing the upload shows its own progress, and an abandoned one never changes)
function pollHome(list, gen, fails = 0) {
  clearTimeout(pollTimer);
  if (!list.some(d => ['queued', 'running'].includes(d.status))) return;
  pollTimer = setTimeout(async () => {
    let next;
    try { next = await api('/api/datasets' + listQuery()); }
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
  if (show && !shown) after.insertAdjacentHTML('afterend', '<p class="tiny" data-retry>' + T('retry.note') + '</p>');
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

function shareDialog(d, base = '/api/datasets/') {
  const refresh = () => { if (base === '/api/sites/') return showSites(); const r = parseRoute(location.hash); if (r.page === 'home') showHome(); else if (r.page === 'dataset') showDataset(r); };
  const allowed = Array.isArray(CONFIG.allowed) ? CONFIG.allowed : CONFIG.allowed ? [CONFIG.allowed] : [];
  const domain = allowed.find(e => e.startsWith('@'));   // the placeholder's suggestion; whole addresses give none
  const render = shared => {
    dialog(t('share.title', { name: d.name }),
      '<p class="muted tiny">' + T(base === '/api/sites/' ? 'share.siteNote' : 'share.note') + (allowed.length ? ' ' + (allowed.length === 1 ? T('share.addressOne', { address: allowed[0] }) : T('share.addressMany', { list: allowed.join(', ') })) : '') + '</p>' +
      '<form id="shareForm" class="row"><input type="email" id="shareEmail" placeholder="' + T('share.emailPlaceholder', { domain: domain || '@example.org' }) + '" required><button type="submit" class="primary">' + T('share.submit') + '</button></form>' +
      '<div class="shared"><ul>' + (shared.length ? shared.map(e => '<li><span class="mi" aria-hidden="true">person</span>' + esc(e) + ' <button class="ghost" data-unshare="' + esc(e) + '" title="' + T('share.remove') + '"><span class="mi" aria-hidden="true">close</span></button></li>').join('') : '<li class="tiny">' + T('share.none') + '</li>') + '</ul></div>');
    $('#shareForm').onsubmit = async ev => { ev.preventDefault(); try { const r = await api(base + d.id + '/share', { method: 'POST', body: JSON.stringify({ email: $('#shareEmail').value }) }); render(r.shared_with); refresh(); } catch (e) { oops(e); } };
    $('#modalBody').querySelectorAll('[data-unshare]').forEach(b => b.onclick = async () => { try { const r = await api(base + d.id + '/share/' + encodeURIComponent(b.dataset.unshare), { method: 'DELETE' }); render(r.shared_with); refresh(); } catch (e) { oops(e); } });
  };
  render(d.shared_with || []);
}

// a dataset or load the reader cannot open: the dead route's entry becomes the list's address, so Back
// never lands on it; the page stays the not-found notice
function showNotFound(what) {
  history.replaceState({ from: (history.state || {}).from }, '', location.pathname + location.search + routeHash({ page: 'home' }));
  setRail({ page: 'home' });
  mountPage(renderNotFound(what));
}

// ---- the dataset page: the dataset, the tab's data, the actions; polls while it extracts
// poll: {fails}, when this is the 5 s refresh of a page already shown. A refresh that fails keeps the page
// and retries (from the second failure in a row a note says so); one that succeeds repaints in place.
let datasetGen = 0;
async function showDataset(route, poll) {
  clearTimeout(loadTimer); clearTimeout(pollTimer); currentLoad = null;
  const gen = ++datasetGen, mine = routeHash(route);
  const current = () => gen === datasetGen && location.hash === mine;
  if (!poll) setRail(route, railDataset && railDataset.id === route.id ? railDataset : null);   // moving within a dataset keeps its entries while the page loads
  const again = fails => { clearTimeout(pollTimer); pollTimer = setTimeout(() => { if (current()) showDataset(route, { fails }); }, 5000); };
  const failed = e => {
    if (poll) { retryNote($('#page .page-head'), poll.fails + 1 >= 2); again(poll.fails + 1); }
    else { setRail(route); mountPage('<p class="empty">' + esc(e.message) + '</p>'); }
  };
  let d;
  try { d = await api('/api/datasets/' + route.id); }
  catch (e) {
    if (!current()) return;
    if (e.status === 401) return;   // the sign-in form is already on the page
    if (e.status === 404) showNotFound('dataset'); else failed(e);
    return;
  }
  if (!current()) return;
  let tab = route.tab;
  if (!tabAllowed(d, tab)) { tab = 'overview'; navigate({ page: 'dataset', id: d.id, tab }, 'replace'); return; }
  const extra = {};
  try {
    if (tab === 'loads') extra.loads = await api('/api/datasets/' + d.id + '/loads');
    else if (tab === 'rangers') {
      const loads = (await api('/api/datasets/' + d.id + '/loads')).slice().sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
      // the list items carry no rangers: the newest load that has some is found by fetching, newest first
      for (const l of loads) { if (!current()) return; const full = await api('/api/loads/' + l.id); if ((full.rangers || []).length) { extra.load = full; break; } }
    }
  } catch (e) { if (!current() || e.status === 401) return; failed(e); return; }
  if (!current()) return;
  setRail(route, d);
  if (paintDataset(renderDatasetPage(d, tab, extra), !!poll)) bindDataset(d, tab, route, extra);
  if (d.extract_held || (tab === 'loads' && (extra.loads || []).some(l => l.held))) again(0);
}
// Mounts the dataset page; false when the page already shows exactly this, which is then left alone.
// A refresh (keep) carries over what the reader did: open and closed sections, the element with focus,
// and the log's place. A log read at its end stays at its end, so a live one follows the newest lines.
function paintDataset(html, keep) {
  const page = $('#page'), old = page.firstElementChild;
  if (keep && old && old._html === html) { retryNote($('#page .page-head'), false); return false; }
  const opens = keep ? Array.from(page.querySelectorAll('details')).map(x => x.open) : [];
  const oldPre = keep ? $('pre.log', page) : null;
  const atBottom = !oldPre || oldPre.scrollHeight - oldPre.scrollTop - oldPre.clientHeight < 12, scrollTop = oldPre ? oldPre.scrollTop : 0;
  const f = keep && page.contains(document.activeElement) ? document.activeElement : null;
  const q = s => '"' + String(s).replace(/["\\]/g, '\\$&') + '"';
  const focus = !f ? '' : f.id ? '#' + f.id : f.dataset.ca ? '[data-act="load"][data-ca=' + q(f.dataset.ca) + ']' : f.matches('a[href]') ? 'a[href=' + q(f.getAttribute('href')) + ']' : '';
  mountPage(html);
  if (page.firstElementChild) page.firstElementChild._html = html;
  const details = Array.from(page.querySelectorAll('details'));
  if (details.length === opens.length) details.forEach((x, i) => { x.open = opens[i]; });
  const pre = $('pre.log', page);
  if (pre) pre.scrollTop = atBottom ? pre.scrollHeight : scrollTop;
  const el = focus && $(focus, page); if (el) el.focus();
  return true;
}
function bindDataset(d, tab, route, extra) {
  document.querySelectorAll('.tabs [aria-disabled="true"]').forEach(a => { a.onclick = ev => ev.preventDefault(); });
  const share = $('#shareBtn'); if (share) share.onclick = () => shareDialog(d);
  const ex = $('#extractBtn'); if (ex) ex.onclick = async () => {
    try { await api('/api/datasets/' + d.id + '/extract', { method: 'POST' }); showDataset(route); } catch (e) { oops(e); }
  };
  // deleting asks first, in the app's own dialog: what goes, and that it cannot be undone
  const del = $('#deleteBtn'); if (del) del.onclick = () => {
    dialog(t('confirm.deleteDatasetTitle', { name: d.name }), deleteDatasetBody());
    $('#confirmGo').onclick = async () => {
      closeDialog();
      try { await api('/api/datasets/' + d.id, { method: 'DELETE' }); navigate({ page: 'home' }, 'replace'); } catch (e) { oops(e); }
    };
  };
  const delBackup = $('#deleteBackupBtn'); if (delBackup) delBackup.onclick = () => {
    dialog(t('confirm.deleteBackupTitle'), deleteBackupBody(d));
    $('#confirmGo').onclick = async () => {
      closeDialog();
      try { await api('/api/datasets/' + d.id + '/upload', { method: 'DELETE' }); showDataset(route); } catch (e) { oops(e); }
    };
  };
  document.querySelectorAll('[data-act="load"]').forEach(b => { b.onclick = () => loadDialog(d, b.dataset.ca); });
  const lb = $('#loadBtn'); if (lb) lb.onclick = () => loadDialog(d, (d.export.find(hasBundle) || {}).dir);
  if (tab === 'rangers' && extra.load) bindRangers($('#tabBody'), extra.load);
}

// ---- upload: create the dataset, PUT the file where the server says (a signed
// GCS URL in production, the service itself locally), then start extraction. The XHR keeps
// running if the dialog is closed; the elements it updates are then just detached.
function uploadDialog() {
  dialog(t('home.upload'),
    '<form id="uploadForm" class="stack">' +
    '<label>' + T('upload.name') + ' <input id="dsName" required placeholder="' + T('upload.namePlaceholder') + '"></label>' +
    '<label>' + T('upload.file') + ' <input id="dsFile" type="file" accept=".zip,.bak" required></label>' +
    '<div id="progress" class="progress" hidden><div class="bar"><div id="progressFill"></div></div><div id="progressText" class="tiny"></div></div>' +
    '<div class="row right"><button type="submit" id="uploadSubmit" class="btn primary">' + T('upload.submit') + '</button></div></form>');
  const form = $('#uploadForm');
  form.onsubmit = async ev => {
    ev.preventDefault();
    const file = $('#dsFile', form).files[0]; if (!file) return;
    const btn = $('#uploadSubmit', form), prog = $('#progress', form), fill = $('#progressFill', form), text = $('#progressText', form);
    const onScreen = () => !$('#modal').hidden && $('#modalBody').contains(form);   // closed or replaced: the reader cannot see it
    btn.disabled = true; prog.hidden = false; fill.style.width = '0%'; text.textContent = t('upload.preparing');
    try {
      const created = await api('/api/datasets', { method: 'POST', body: JSON.stringify({ name: $('#dsName', form).value, filename: file.name, size: file.size, content_type: file.type || 'application/zip' }) });
      if (parseRoute(location.hash).page === 'home') showHome();       // the new dataset appears, uploading, even if the dialog is closed
      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open(created.upload.method, created.upload.url);
        for (const [k, v] of Object.entries(created.upload.headers || {})) xhr.setRequestHeader(k, v);
        xhr.withCredentials = created.upload.url.startsWith('/');
        xhr.upload.onprogress = e => { if (e.lengthComputable) { fill.style.width = (100 * e.loaded / e.total).toFixed(1) + '%'; text.textContent = t('upload.progress', { done: fmtBytes(e.loaded), total: fmtBytes(e.total) }); } };
        xhr.onload = () => xhr.status < 300 ? resolve() : reject(new Error(t('upload.failed', { status: xhr.status })));
        xhr.onerror = () => reject(new Error(t('upload.failedNetwork')));
        xhr.send(file);
      });
      text.textContent = t('upload.starting');
      await api('/api/datasets/' + created.id + '/extract', { method: 'POST' });
      if (onScreen()) closeDialog();                                   // still on screen: close it
      const at = parseRoute(location.hash);
      if (at.page === 'home') showHome();                              // the new dataset appears, extracting
      else if (at.page === 'dataset' && at.id === created.id) showDataset(at);   // opened while it uploaded: now it extracts, and polls
    } catch (e) {
      if (onScreen()) { text.textContent = e.message; btn.disabled = false; }
      else if (e.status !== 401) alert(e.message);                     // the form is gone: a note there would never be seen
    }
  };
}

// ---- the sites page
// the add-site dialog. The token is read from the field on submit and goes only to the POST.
// onCreated(site) runs after a successful save; onCancel runs when the reader closes the dialog instead.
function siteDialog(onCreated, onCancel) {
  dialog(t('siteDialog.title'),
    '<p class="muted tiny">' + T('siteDialog.hint') + '</p>' +
    '<form id="siteForm" class="col" autocomplete="off">' +
    '<label class="field"><span>' + T('siteDialog.name') + '</span><input type="text" id="siteName" required placeholder="example"></label>' +
    '<label class="field"><span>' + T('siteDialog.host') + '</span><input type="text" id="siteUrl" required placeholder="example.pamdas.org"></label>' +
    '<label class="field"><span>' + T('siteDialog.token') + '</span><input type="password" id="siteToken" autocomplete="off" required></label>' +
    '<p class="tiny" id="siteError" role="alert"></p>' +
    '<div class="row right"><button type="button" class="ghost" data-close>' + T('shell.close') + '</button><button type="submit" class="primary" id="siteBtn">' + T('siteDialog.submit') + '</button></div></form>');
  const close = $('#modalBody').querySelector('[data-close]'), plain = close.onclick;
  close.onclick = () => { plain(); if (onCancel) onCancel(); };
  $('#siteForm').onsubmit = async ev => {
    ev.preventDefault();
    const btn = $('#siteBtn'), err = $('#siteError'); btn.disabled = true; err.textContent = t('siteDialog.checking');
    try {
      const site = await api('/api/sites', { method: 'POST', body: JSON.stringify({ name: $('#siteName').value, url: $('#siteUrl').value, token: $('#siteToken').value }) });
      closeDialog();
      if (parseRoute(location.hash).page === 'sites') showSites();
      if (onCreated) onCreated(site);
    } catch (e) { if (e.status === 401) return; err.textContent = e.message; btn.disabled = false; }
  };
}

// the edit-site dialog: rename, and replace the token if one is typed. The token is read from the
// field on submit and goes only to the PATCH; an empty field sends none, and the stored one stays.
function siteEditDialog(s) {
  dialog(t('siteEdit.title'), siteEditBody(s));
  $('#siteForm').onsubmit = async ev => {
    ev.preventDefault();
    const btn = $('#siteBtn'), err = $('#siteError'), token = $('#siteToken').value.trim();
    btn.disabled = true; err.textContent = '';
    if (token) err.textContent = t('siteDialog.checking');
    try {
      await api('/api/sites/' + s.id, { method: 'PATCH', body: JSON.stringify(token ? { name: $('#siteName').value, token: token } : { name: $('#siteName').value }) });
      closeDialog();
      if (parseRoute(location.hash).page === 'sites') showSites();
    } catch (e) { if (e.status === 401) return; err.textContent = e.message; btn.disabled = false; }
  };
}

// mirrors findings.ca_identifier: smart-<ca id>, 2-30 chars of [A-Za-z0-9_-]
function defaultEventCategory(caId) {
  const s = ('smart-' + (caId || 'ca')).toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
  return (s.length >= 2 ? s : 'smart-ca').slice(0, 30);
}

// mirrors findings.set_category: smart-<set name>, made safe the same way
function defaultSetCategory(name) { return defaultEventCategory(name.normalize('NFKC').toLowerCase().trim().split(/\s+/).join(' ') || 'set'); }

// keep: the form's values and site choice, when the dialog is reopened after the add-a-site detour
async function loadDialog(d, caId, keep) {
  let sites;
  const from = location.hash;
  try { sites = await api('/api/sites'); } catch (e) { oops(e); return; }
  if (location.hash !== from) return;   // the reader left while the sites loaded: the dialog belongs to the page they left
  if (!sites.length) return siteDialog(() => loadDialog(d, caId));
  const addSite = kept => siteDialog(site => loadDialog(d, kept.ca || caId, { ...kept, site: site.id }), () => loadDialog(d, kept.ca || caId, kept));
  let lastDefault = null, autoDm = false;
  const render = () => {
    const ca = d.export.find(e => e.dir === $('#ldCa').value) || d.export[0];
    // an area with no patrols has only its data model to load; leaving it for one with patrols undoes that choice
    if (!ca.patrols) { $('#ldScope').value = 'datamodel'; autoDm = true; } else if (autoDm) { $('#ldScope').value = 'all'; autoDm = false; }
    setCategory(defaultEventCategory(ca.ca_id));   // what the server defaults to
    $('#ldLang').innerHTML = ca.languages.map(l => '<option' + (l === ca.default_language ? ' selected' : '') + '>' + esc(l) + '</option>').join('');
    $('#ldCm').innerHTML = '<option value="">' + T('loadDialog.none') + '</option>' + ca.configurable_models.map(m => '<option value="' + esc(m.uuid) + '">' + esc(m.label) + '</option>').join('');
    modelChanged();
  };
  // the category field follows the server's default until the reader types their own
  const setCategory = def => {
    if (lastDefault === null || $('#ldCategory').value === lastDefault) $('#ldCategory').value = def;
    lastDefault = def;
  };
  const areaOf = () => d.export.find(e => e.dir === $('#ldCa').value) || d.export[0];
  // a load with a configurable model has a set name: the model's, unless the reader changes it
  const setChanged = () => {
    const name = $('#ldSet').value.trim();
    setCategory($('#ldCm').value && name ? defaultSetCategory(name) : defaultEventCategory(areaOf().ca_id));
  };
  const modelChanged = () => {
    const m = areaOf().configurable_models.find(m => m.uuid === $('#ldCm').value);
    $('#ldSetRow').hidden = !m;
    $('#ldSet').value = m ? String(m.label || '').trim() : '';   // whole, even past the field's limit: a name cut short would be another set
    setChanged();
  };
  dialog(t('loadDialog.title', { name: d.name }),
    '<p class="muted tiny">' + T('loadDialog.intro') + '</p>' +
    '<form id="ldForm" class="col">' +
    '<label>' + T('loadDialog.area') + ' <select id="ldCa">' + d.export.map(e => '<option value="' + esc(e.dir) + '">' + T('loadDialog.areaOption', { name: e.name || e.ca_id }, { patrols: tn('units.patrols', e.patrols || 0) }) + '</option>').join('') + '</select></label>' +
    '<label>' + T('loadDialog.site') + ' <select id="ldSite">' + sites.map(s => '<option value="' + esc(s.id) + '">' + esc(s.name) + ' · ' + esc(s.url) + '</option>').join('') + '<option value="__add__">' + T('loadDialog.addSite') + '</option></select></label>' +
    '<label>' + T('loadDialog.labelLanguage') + ' <select id="ldLang"></select></label>' +
    '<label>' + T('loadDialog.configurableModel') + ' <select id="ldCm"></select></label>' +
    '<p class="muted tiny">' + T('loadDialog.modelHint') + '</p>' +
    '<div id="ldSetRow" class="col" hidden><label>' + T('loadDialog.eventTypeSet') + ' <input type="text" id="ldSet" maxlength="60"></label>' +
    '<p class="muted tiny">' + T('loadDialog.eventTypeSetHint') + '</p></div>' +
    '<label>' + T('loadDialog.roster') + ' <input type="text" id="ldRoster" placeholder="' + T('loadDialog.rosterPlaceholder') + '"></label>' +
    '<label>' + T('loadDialog.category') + ' <input type="text" id="ldCategory" maxlength="30" pattern="[A-Za-z0-9_\\-]{2,30}" required></label>' +
    '<p class="muted tiny">' + T('loadDialog.categoryHint') + '</p>' +
    '<label>' + T('loadDialog.existing') + ' <select id="ldExisting"><option value="keep">' + T('loadDialog.existingKeep') + '</option><option value="update">' + T('loadDialog.existingUpdate') + '</option></select></label>' +
    '<p class="muted tiny">' + T('loadDialog.existingHint') + '</p>' +
    '<label>' + T('loadDialog.what') + ' <select id="ldScope"><option value="all">' + T('loadDialog.modelAndPatrols') + '</option><option value="datamodel">' + T('loadDialog.modelOnly') + '</option></select></label>' +
    '<div class="row" id="ldWindow"><label>' + T('loadDialog.patrolsFrom') + ' <input type="date" id="ldSince"></label><label>' + T('loadDialog.to') + ' <input type="date" id="ldUntil"></label></div>' +
    '<p class="muted tiny" id="ldScopeHint"></p>' +
    '<div class="row right"><button type="button" class="ghost" data-close>' + T('shell.close') + '</button><button type="submit" class="primary">' + T('loadDialog.makePlan') + '</button></div></form>');
  const scopeChanged = () => {
    const dm = $('#ldScope').value === 'datamodel';
    $('#ldWindow').hidden = dm;
    if (dm) $('#ldScopeHint').textContent = t('loadDialog.hintDatamodel');
    else $('#ldScopeHint').textContent = t('loadDialog.hintAll');
  };
  if (caId) $('#ldCa').value = caId;
  const ids = ['ldRoster', 'ldCategory', 'ldExisting', 'ldScope', 'ldSince', 'ldUntil'];
  if (keep && keep.ca) $('#ldCa').value = keep.ca;
  render();
  if (keep) { ids.forEach(i => { $('#' + i).value = keep[i]; }); $('#ldLang').value = keep.ldLang; $('#ldCm').value = keep.ldCm; $('#ldSetRow').hidden = !keep.ldCm; $('#ldSet').value = keep.ldSet || ''; if (keep.site) $('#ldSite').value = keep.site;
    // lastDefault is what the server would default to for the restored form, so a category the reader typed is still theirs
    if (keep.ldCm && $('#ldSet').value.trim()) lastDefault = defaultSetCategory($('#ldSet').value.trim()); }
  scopeChanged(); $('#ldCa').onchange = () => { render(); scopeChanged(); }; $('#ldScope').onchange = scopeChanged;
  $('#ldCm').onchange = modelChanged; $('#ldSet').oninput = setChanged;
  let prevSite = $('#ldSite').value;
  $('#ldSite').onchange = () => {
    if ($('#ldSite').value !== '__add__') { prevSite = $('#ldSite').value; return; }
    const kept = { ca: $('#ldCa').value, site: prevSite, ldLang: $('#ldLang').value, ldCm: $('#ldCm').value, ldSet: $('#ldSet').value };
    ids.forEach(i => { kept[i] = $('#' + i).value; });
    addSite(kept);
  };
  $('#ldForm').onsubmit = async ev => {
    ev.preventDefault();
    const dm = $('#ldScope').value === 'datamodel', since = dm ? '' : $('#ldSince').value, until = dm ? '' : $('#ldUntil').value;
    if (since && until && since > until) return alert(t('loadDialog.windowBackwards'));
    try {
      const l = await api('/api/datasets/' + d.id + '/loads', { method: 'POST', body: JSON.stringify({ ca_id: $('#ldCa').value, site_id: $('#ldSite').value,
        options: { language: $('#ldLang').value, configurable_model: $('#ldCm').value || null, event_type_set: $('#ldCm').value ? $('#ldSet').value.trim() || null : null, roster_group: $('#ldRoster').value,
        event_category: $('#ldCategory').value.trim(), existing_event_types: $('#ldExisting').value, scope: $('#ldScope').value, since: since || null, until: until || null } }) });
      closeDialog(); navigate({ page: 'load', id: d.id, load: l.id });
    } catch (e) { oops(e); }
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

// the load, its dataset for the sidebar, then the page; polls every 4 s while the load is held
async function showLoad(route) {
  clearTimeout(loadTimer); clearTimeout(pollTimer);
  currentLoad = route.load;
  const gen = ++loadGen, mine = routeHash(route);
  const current = () => gen === loadGen && location.hash === mine;
  setRail(route, railDataset && railDataset.id === route.id ? railDataset : null);
  let l;
  try { l = await api('/api/loads/' + route.load); }
  catch (e) {
    if (!current() || e.status === 401) return;   // on 401 the sign-in form is already on the page
    if (e.status === 404) showNotFound('load'); else { setRail(route); mountPage('<p class="empty">' + esc(e.message) + '</p>'); }
    return;
  }
  if (!current()) return;
  if (l.dataset_id !== route.id) { navigate({ page: 'load', id: l.dataset_id, load: l.id }, 'replace'); return; }   // the address names the wrong dataset
  let ds = null;   // without the dataset the sidebar keeps its list form rather than failing the page
  try { ds = await api('/api/datasets/' + l.dataset_id); } catch (e) { if (e.status === 401) return; }
  if (!current()) return;
  const up = { page: 'dataset', id: l.dataset_id, tab: 'loads' };
  setRail(route, ds);
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
    if (x.held || x.dataset_extracting) loadTimer = setTimeout(refresh, 4000);   // an extraction ending re-enables the actions
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
  const key = rangersKey(l);
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
  const run = $('[data-run]', page); if (run) run.onclick = async () => { try { await api('/api/loads/' + l.id + '/run', { method: 'POST' }); refresh(); } catch (e) { oops(e); } };
  const re = $('[data-replan]', page); if (re) re.onclick = async () => { try { await api('/api/loads/' + l.id + '/replan', { method: 'POST' }); refresh(); } catch (e) { oops(e); } };
  const del = $('[data-del]', page); if (del) del.onclick = async () => {
    if (!confirm(t('confirm.deleteLoad'))) return;
    try {
      await api('/api/loads/' + l.id, { method: 'DELETE' });
      // the deleted load's entry becomes its dataset's loads, so Back never lands on it; if the reader has
      // moved on meanwhile, the page they are on is left alone and a list they are on is refreshed
      if (location.hash === routeHash({ page: 'load', id: up.id, load: l.id })) navigate(up, 'replace');
      else { const r = parseRoute(location.hash); if (r.page === 'home') showHome(); else if (r.page === 'dataset') showDataset(r); }
    } catch (e) { oops(e); }
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
  catch (e) { window.prompt(t('findings.copyPrompt'), btn.dataset.copy); return; }
  setTimeout(() => { icon.textContent = 'content_copy'; }, 1500);
}

// ---- help: a drawer of sections, deep-linked by heading id (a finding opens finding-<code>)
let HELP = null, helpLoading = null, helpOpener = null, helpGen = 0;
async function openHelp(anchor) {
  const drawer = $('#help'), body = $('#helpBody');
  // the opener is remembered by its help id: the load page re-renders its buttons on every poll
  const a = document.activeElement;
  helpOpener = a && a.dataset && a.dataset.help ? { help: a.dataset.help } : { node: a };
  if (!HELP) {
    const from = location.hash, gen = helpGen;
    // one fetch, however many clicks arrive while it is pending; a failure alerts once and resolves null for all
    helpLoading = helpLoading || api('/api/help?lang=' + encodeURIComponent(currentLang())).then(r => r.sections, e => { if (gen === helpGen) helpLoading = null; oops(e); return null; });
    const sections = await helpLoading;
    if (!sections || gen !== helpGen || location.hash !== from || !ME) return;   // failed, or the reader left meanwhile
    if (!HELP) {
      HELP = sections;
      body.innerHTML = HELP.map(helpSection).join('');
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
    note.textContent = t('help.noEntry', { id: id.slice(8) });
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
const CSV_COLUMNS = ['name', 'smartEmployeeId', 'smartMemberId', 'active', 'deletedInSmart', 'patrolsThisLoad', 'patrolsAll', 'subjectId', 'email'];   // csv.<column>: the header row, in this order
function bindRangers(host, l) {
  const rows = l.rangers || [];
  host.querySelector('[data-help]').onclick = ev => { ev.preventDefault(); openHelp('rangers-accounts'); };
  host.querySelector('[data-csv]').onclick = ev => { ev.preventDefault(); downloadCsv('rangers-' + l.ca_id + '.csv', CSV_COLUMNS.map(c => t('csv.' + c)),
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
