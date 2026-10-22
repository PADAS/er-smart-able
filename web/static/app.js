// smart-able web: sign in, list datasets, upload + extract, share, open.
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtBytes = n => n >= 1e9 ? (n / 1e9).toFixed(1) + ' GB' : n >= 1e6 ? (n / 1e6).toFixed(0) + ' MB' : n >= 1e3 ? (n / 1e3).toFixed(0) + ' kB' : n + ' B';
let CONFIG = null, ME = null, pollTimer = null;

async function api(path, opts = {}) {
  const r = await fetch(path, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) }, ...opts });
  if (r.status === 401) { showSignIn(); throw new Error('Sign in required'); }
  if (!r.ok) { let d = ''; try { d = (await r.json()).detail; } catch (e) {} throw new Error(d || r.statusText); }
  return r.status === 204 ? null : r.json();
}

function showSignIn(err) {
  $('#signIn').hidden = false; $('#appUI').hidden = true; $('#who').hidden = true;
  $('#signInError').textContent = err || '';
}
function showApp() {
  $('#signIn').hidden = true; $('#appUI').hidden = false; $('#who').hidden = false;
  $('#whoEmail').textContent = ME.email;
  loadList();
  loadSites();
}

async function boot() {
  CONFIG = await (await fetch('/api/config')).json();
  $('#allowedHint').textContent = CONFIG.allowed;
  if (!CONFIG.authDisabled) {
    firebase.initializeApp({ apiKey: CONFIG.apiKey, authDomain: CONFIG.authDomain, projectId: CONFIG.projectId });
    if (CONFIG.authEmulatorUrl) firebase.auth().useEmulator(CONFIG.authEmulatorUrl);
  }
  $('#signInBtn').onclick = signIn;
  $('#helpBtn').onclick = () => openHelp();
  $('#helpClose').onclick = closeHelp;
  $('#helpBody').onscroll = helpScrolled;
  $('#help').onkeydown = helpKeydown;
  $('#helpBackdrop').onclick = closeHelp;
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('#help').hidden) closeHelp(); });
  $('#signOut').onclick = async () => { await api('/api/signout', { method: 'POST' }); if (!CONFIG.authDisabled) await firebase.auth().signOut(); showSignIn(); };
  $('#modalClose').onclick = () => { $('#modal').hidden = true; };
  $('#uploadForm').onsubmit = upload;
  $('#siteForm').onsubmit = addSite;
  $('#loadBack').onclick = showDatasets;
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
async function loadList() {
  const list = await api('/api/datasets');
  const host = $('#list');
  if (!list.length) { host.innerHTML = '<p class="muted">No datasets yet. Upload one above.</p>'; return; }
  host.innerHTML = '<table><thead><tr><th>Dataset</th><th>Conservation area(s)</th><th>Status</th><th>Owner</th><th>Shared with</th><th></th></tr></thead><tbody>' +
    list.map(d => '<tr data-id="' + d.id + '">' +
      '<td><b>' + esc(d.name) + '</b><div class="tiny">' + esc(d.source_name) + (d.source_size ? ' · ' + fmtBytes(d.source_size) : '') + ' · ' + esc((d.created_at || '').slice(0, 10)) + '</div></td>' +
      '<td>' + ((d.cas || []).map(c => esc(c.n || c.id)).join('<br>') || '<span class="tiny">—</span>') + (d.db_version ? '<div class="tiny">SMART ' + esc(d.db_version) + '</div>' : '') + '</td>' +
      '<td><span class="pill ' + esc(d.status) + '">' + esc(d.status) + '</span>' + (d.error ? '<div class="tiny">' + esc(d.error) + '</div>' : '') +
        (d.counts && d.counts.patrols != null ? '<div class="tiny">' + d.counts.patrols + ' patrols · ' + d.counts.waypoints + ' waypoints</div>' : '') + '</td>' +
      '<td>' + (d.mine ? 'you' : esc(d.owner_email)) + '</td>' +
      '<td>' + ((d.shared_with || []).map(esc).join('<br>') || '<span class="tiny">—</span>') + '</td>' +
      '<td class="actions">' +
        (d.status === 'ready' ? '<a href="/d/' + d.id + '/"><button><span class="mi" aria-hidden="true">arrow_forward</span>Open</button></a> ' : '') +
        (d.mine ? '<button data-act="share"><span class="mi" aria-hidden="true">share</span>Share</button> ' : '') +
        (d.status === 'ready' && (d.export || []).length ? '<button data-act="load"><span class="mi" aria-hidden="true">cloud_upload</span>Load into EarthRanger</button> ' : '') +
        (d.status === 'ready' && !(d.export || []).length ? '<span class="tiny" title="Run the extraction again to build the migration bundle">re-extract to enable loading</span> ' : '') +
        (d.mine && !d.extract_held && ['failed', 'uploaded', 'ready', 'uploading', 'queued', 'running'].includes(d.status) ? '<button data-act="extract" title="' + (d.status === 'uploading' ? 'Start the extraction (if the upload completed)' : 'Run the extraction again') + '"><span class="mi" aria-hidden="true">refresh</span></button> ' : '') +
        (d.mine && (d.status === 'failed' || d.status === 'running') ? '<button data-act="log" title="Extraction log"><span class="mi" aria-hidden="true">receipt_long</span></button> ' : '') +
        (d.mine ? '<button data-act="delete" class="danger" title="Delete this dataset and its files"><span class="mi" aria-hidden="true">delete</span></button>' : '') +
      '</td></tr>').join('') + '</tbody></table>';
  host.querySelectorAll('button[data-act]').forEach(b => b.onclick = () => action(b.dataset.act, b.closest('tr').dataset.id, list.find(d => d.id === b.closest('tr').dataset.id)));
  clearTimeout(pollTimer);
  // 'uploading' is not polled: the tab doing the upload shows its own progress, and an abandoned one never changes
  if (list.some(d => ['queued', 'running'].includes(d.status))) pollTimer = setTimeout(loadList, 5000);
  list.filter(d => d.status === 'ready').forEach(d => renderLoads(d.id, d.export || []).catch(() => {}));
}

async function renderLoads(id, exp) {
  const loads = await api('/api/datasets/' + id + '/loads');
  const td = $('tr[data-id="' + id + '"] td:nth-child(3)');
  if (!td || !loads.length) return;
  td.insertAdjacentHTML('beforeend', '<div class="loads">' + loads.map(l =>
    '<div><a data-load="' + esc(l.id) + '">' + esc(l.site ? l.site.url : 'removed site') + ' · ' + esc(((exp || []).find(e => e.dir === l.ca_id) || {}).name || l.ca_id) + '</a> <span class="pill ' + esc(l.status) + '">' + esc(l.status) + '</span>' +
    (l.progress && ['running', 'continuing', 'needs_attention', 'done'].includes(l.status) ? ' <span class="tiny">' + esc(l.progress.done) + ' of ' + esc(l.progress.patrols_total) + ' patrols</span>' : '') + '</div>').join('') + '</div>');
  td.querySelectorAll('a[data-load]').forEach(a => a.onclick = () => showLoad(a.dataset.load));
  if (loads.some(l => l.held)) { clearTimeout(pollTimer); pollTimer = setTimeout(loadList, 5000); }
}

async function action(act, id, d) {
  try {
    if (act === 'share') return shareDialog(d);
    if (act === 'load') return loadDialog(d);
    if (act === 'extract') { await api('/api/datasets/' + id + '/extract', { method: 'POST' }); return loadList(); }
    if (act === 'log') { const full = await api('/api/datasets/' + id); return dialog('Extraction log: ' + d.name, '<pre class="log">' + esc(full.log_tail || full.error || '(no output yet)') + '</pre>'); }
    if (act === 'delete') { if (!confirm('Delete "' + d.name + '" and all its extracted data? This cannot be undone.')) return; await api('/api/datasets/' + id, { method: 'DELETE' }); return loadList(); }
  } catch (e) { alert(e.message); }
}

function dialog(title, bodyHtml) { $('#modalTitle').textContent = title; $('#modalBody').innerHTML = bodyHtml; $('#modal').hidden = false; }

function shareDialog(d, base = '/api/datasets/', note) {
  const refresh = () => base === '/api/sites/' ? loadSites() : loadList();
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

// ---- upload: create the dataset, PUT the file where the server says (a signed
// GCS URL in production, the service itself locally), then start extraction
async function upload(ev) {
  ev.preventDefault();
  const file = $('#dsFile').files[0]; if (!file) return;
  const btn = $('#uploadBtn'); btn.disabled = true;
  const prog = $('#progress'), fill = $('#progressFill'), text = $('#progressText');
  prog.hidden = false; fill.style.width = '0%'; text.textContent = 'Preparing…';
  try {
    const created = await api('/api/datasets', { method: 'POST', body: JSON.stringify({ name: $('#dsName').value, filename: file.name, size: file.size, content_type: file.type || 'application/zip' }) });
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
    text.textContent = 'Extraction started; the list below updates as it runs.';
    $('#uploadForm').reset();
    loadList();
  } catch (e) { text.textContent = e.message; }
  finally { btn.disabled = false; setTimeout(() => { prog.hidden = true; }, 6000); }
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

async function loadDialog(d) {
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
    '<label>Roster group <input type="text" id="ldRoster" placeholder="optional; default: the patrol configuration\'s first member group"></label>' +
    '<label>Event category <input type="text" id="ldCategory" maxlength="30" pattern="[A-Za-z0-9_\\-]{2,30}" required></label>' +
    '<p class="muted tiny">Use the identifier an earlier CLI push used, if any (phinney: lawin050500).</p>' +
    '<div class="row right"><button type="submit" class="primary">Make the plan</button></div></form>');
  render(); $('#ldCa').onchange = render;
  $('#ldForm').onsubmit = async ev => {
    ev.preventDefault();
    try {
      const l = await api('/api/datasets/' + d.id + '/loads', { method: 'POST', body: JSON.stringify({ ca_id: $('#ldCa').value, site_id: $('#ldSite').value,
        options: { language: $('#ldLang').value, configurable_model: $('#ldCm').value || null, roster_group: $('#ldRoster').value,
        event_category: $('#ldCategory').value.trim() } }) });
      $('#modal').hidden = true; showLoad(l.id);
    } catch (e) { alert(e.message); }
  };
}

// ---- the load page
let loadTimer = null, currentLoad = null;
function showDatasets() { clearTimeout(loadTimer); currentLoad = null; document.querySelectorAll('#appUI > .panel:not(#loadPage)').forEach(p => p.hidden = false); $('#loadPage').hidden = true; loadList(); loadSites(); }

async function showLoad(id) {
  clearTimeout(pollTimer);
  currentLoad = id;
  ['#loadTitle', '#loadStages', '#loadActions', '#loadFindings', '#loadPlan', '#loadProgress'].forEach(s => { $(s).innerHTML = ''; });
  document.querySelectorAll('#appUI > .panel:not(#loadPage)').forEach(p => p.hidden = true);
  $('#loadPage').hidden = false;
  try { await renderLoad(); } catch (e) { alert(e.message); showDatasets(); }
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
    ' <span class="pill ' + esc(l.status) + '">' + esc(l.status.replace('_', ' ')) + '</span>' +
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
  const del = $('#loadActions [data-del]'); if (del) del.onclick = async () => { if (!confirm('Delete this load\'s records? Nothing in EarthRanger is removed.')) return; try { await api('/api/loads/' + l.id, { method: 'DELETE' }); showDatasets(); } catch (e) { alert(e.message); } };
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
  const p = l.progress;
  const prevLog = $('#loadProgress details'), prevPre = prevLog && prevLog.querySelector('pre');
  const logOpen = prevLog ? prevLog.open : active;
  const atBottom = !prevPre || prevPre.scrollHeight - prevPre.scrollTop - prevPre.clientHeight < 12, scrollTop = prevPre ? prevPre.scrollTop : 0;
  $('#loadProgress').innerHTML = (p && p.patrols_total && l.mode !== 'plan' ? '<h3>Progress</h3><div class="bar"><div style="width:' + (100 * p.done / p.patrols_total).toFixed(1) + '%"></div></div><p class="tiny">' + esc(importSummary(l, active)) + '</p>' : '') +
    (l.continuations ? '<p class="tiny">Continued ' + esc(l.continuations) + ' time(s) past the job limit.</p>' : '') +
    (l.log_tail ? '<details' + (logOpen ? ' open' : '') + '><summary class="tiny">Log' + (active ? ' (live)' : ' tail') + '</summary><pre class="log">' + esc(l.log_tail) + '</pre></details>' : '') +
    '<p class="tiny">Files: ' + ['plan.json', 'findings.json', 'checklist.json', 'checklist.md', 'import-ledger.json', 'log.txt'].map(n => '<a href="/api/loads/' + esc(l.id) + '/files/' + n + '" download>' + n + '</a>').join(' · ') + '</p>';
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
  let s = p.done.toLocaleString() + ' of ' + p.patrols_total.toLocaleString() + ' patrols' + (p.failed ? ', ' + p.failed + ' failed' : '') + (p.skipped ? ', ' + p.skipped + ' already there' : '');
  const row = (l.stages || {}).import || {};
  const end = live ? Date.now() : row.finished_at ? Date.parse(row.finished_at) : null;   // a finished import's rate does not decay
  const mins = row.started_at && end ? (end - Date.parse(row.started_at)) / 60000 : null, written = p.done - (p.skipped || 0);   // skips take no time
  if (mins && mins > 0.5 && written > 0) {
    const rate = written / mins;
    s += ' · ' + rate.toFixed(1) + ' per minute';
    if (live && p.done < p.patrols_total) s += ' · about ' + fmtDur((p.patrols_total - p.done) / rate * 60) + ' left';
  }
  return s;
}

function renderStages(l, active) {
  const rows = stageRows(l);
  let html = '<table class="stagetable"><thead><tr><th>Stage</th><th>Status</th><th>Took</th><th>What happened</th></tr></thead><tbody>';
  for (const s of STAGES) {
    const r = rows[s], status = r ? r.status : 'pending';
    const running = status === 'running' && active;
    const took = r && r.started_at && r.finished_at ? fmtDur((Date.parse(r.finished_at) - Date.parse(r.started_at)) / 1000) : running && r.started_at ? fmtDur(secondsSince(r.started_at)) + '…' : '';
    html += '<tr class="' + esc(status) + '"><td>' + esc(STAGE_LABEL[s]) + '</td><td><span class="pill ' + esc(running ? 'running' : status === 'running' ? 'stale' : status) + '">' +
      esc(running ? 'running' : status === 'running' ? 'interrupted' : status === 'pending' && !active ? 'not reached' : status) + '</span></td><td class="tiny">' + esc(took) + '</td><td class="tiny">' + esc(r ? stageSummary(s, r, l, active) : '') + '</td></tr>';
  }
  html += '</tbody></table>';
  if (active) html += notStarted(l) ? '<p class="tiny heartbeat">Waiting for the job to start · ' + esc(fmtDur(secondsSince(l.claimed_at))) + ' since it was queued</p>'
    : '<p class="tiny heartbeat">' + (l.continuations ? 'Continuation ' + esc(l.continuations) + ' running for ' : 'Running for ') + esc(fmtDur(secondsSince(l.started_at || l.claimed_at))) + ' · the job last reported ' + esc(fmtDur(secondsSince(l.updated_at))) + ' ago</p>';
  return html;
}

function renderPlan(plan) {
  const group = (title, g) => {
    if (!g) return '';
    const parts = [];
    for (const k of ['create', 'update', 'deactivate']) if (Array.isArray(g[k]) && g[k].length)
      parts.push('<details><summary>' + k + ' ' + g[k].length + (g.more ? '+' : '') + '</summary><ul>' + g[k].map(e => '<li>' + esc(e.label) + (e.value && e.value !== e.label ? ' <span class="tiny">' + esc(e.value) + '</span>' : '') + '</li>').join('') + (g.more ? '<li class="tiny">and ' + esc(g.more) + ' more</li>' : '') + '</ul></details>');
    if (g.unchanged) parts.push('<span class="tiny">' + esc(g.unchanged) + ' unchanged</span>');
    return '<div><b>' + title + '</b> ' + (parts.join(' ') || '<span class="tiny">nothing to do</span>') + '</div>';
  };
  const p = plan.patrols || {};
  return group('Event categories', plan.event_categories) + group('Event types', plan.event_types) + group('Patrol types', plan.patrol_types) +
    '<div><b>Universal patrol fields</b> ' + esc(plan.universal_patrol_fields) + '</div>' + group('Choices', plan.choices) + group('Subjects', plan.subjects) +
    '<div><b>Roster</b> ' + (plan.roster && plan.roster.group ? esc(plan.roster.group) + ': ' : '') + esc((plan.roster || {}).add || 0) + ' to add</div>' +
    '<div><b>Patrols</b> ' + esc(p.total) + (p.first ? ' from ' + esc(p.first) + ' to ' + esc(p.last) : '') + (p.already_done ? ', ' + esc(p.already_done) + ' already imported' : '') + ' · ' + esc(p.events) + ' observations · ' + esc(p.track_points) + ' track points</div>';
}

boot();
