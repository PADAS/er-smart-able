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
  $('#loadTitle').textContent = l.ca_id + ' → ' + (l.site ? l.site.name + ' (' + l.site.url + ')' : 'removed site') + ' · ' + l.status;
  const idx = STAGES.indexOf(l.stage);
  const active = !!l.held;
  const stale = !active && ACTIVE.includes(l.status);
  $('#loadStages').innerHTML = STAGES.map((s, i) => '<span class="stage ' +
    (i < idx || (i === idx && ['done', 'planned'].includes(l.status)) ? 'done' : i === idx && active ? 'current' : i === idx && ['needs_attention', 'failed'].includes(l.status) ? 'stopped' : '') +
    '">' + esc(STAGE_LABEL[s]) + '</span>').join('');
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
  $('#loadFindings').innerHTML = fs.length ? '<h3>Findings</h3>' + fs.map(f => '<div class="finding ' + esc(f.severity) + '"><b>' + esc(f.title) + '</b> <span class="tiny">' + esc(f.severity) + ' · ' + esc(STAGE_LABEL[f.stage] || f.stage) + (f.affected && f.affected.count ? ' · ' + esc(f.affected.count) + ' patrols' : '') + '</span>' +
    (f.detail ? '<pre>' + esc(f.detail) + '</pre>' : '') + (f.fix ? '<div class="tiny"><b>Fix:</b> ' + esc(f.fix) + '</div>' : '') + '</div>').join('') :
    (['planned', 'done'].includes(l.status) ? '<p class="muted tiny">No findings.</p>' : '');
  $('#loadPlan').innerHTML = l.plan ? '<h3>Plan</h3><div class="plan">' + renderPlan(l.plan) + '</div>' : '';
  const p = l.progress;
  $('#loadProgress').innerHTML = (p ? '<h3>Progress</h3><p>' + esc(p.done) + ' of ' + esc(p.patrols_total) + ' patrols' + (p.failed ? ', ' + esc(p.failed) + ' failed' : '') + (p.skipped ? ', ' + esc(p.skipped) + ' already there' : '') + '</p>' : '') +
    (l.continuations ? '<p class="tiny">Continued ' + esc(l.continuations) + ' time(s) past the job limit.</p>' : '') +
    (l.log_tail ? '<details><summary class="tiny">Log tail</summary><pre class="log">' + esc(l.log_tail) + '</pre></details>' : '') +
    '<p class="tiny">Files: ' + ['plan.json', 'findings.json', 'checklist.json', 'checklist.md', 'import-ledger.json', 'log.txt'].map(n => '<a href="/api/loads/' + esc(l.id) + '/files/' + n + '" download>' + n + '</a>').join(' · ') + '</p>';
  if (active) loadTimer = setTimeout(() => renderLoad().catch(() => {}), 4000);
}

function renderPlan(plan) {
  const group = (title, g) => {
    if (!g) return '';
    const parts = [];
    for (const k of ['create', 'update', 'deactivate']) if (Array.isArray(g[k]) && g[k].length)
      parts.push('<details><summary>' + k + ' ' + g[k].length + (g.more ? '+' : '') + '</summary><ul>' + g[k].map(e => '<li>' + esc(e.label) + ' <span class="tiny">' + esc(e.value) + '</span></li>').join('') + (g.more ? '<li class="tiny">and ' + esc(g.more) + ' more</li>' : '') + '</ul></details>');
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
