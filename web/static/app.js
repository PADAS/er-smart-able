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
        (d.status === 'ready' ? '<a href="/d/' + d.id + '/" target="_blank" rel="noopener"><button><span class="mi" aria-hidden="true">open_in_new</span>Open</button></a> ' : '') +
        (d.mine ? '<button data-act="share"><span class="mi" aria-hidden="true">share</span>Share</button> ' : '') +
        (d.mine && ['failed', 'uploaded', 'ready', 'uploading'].includes(d.status) ? '<button data-act="extract" title="' + (d.status === 'uploading' ? 'Start the extraction (if the upload completed)' : 'Run the extraction again') + '"><span class="mi" aria-hidden="true">refresh</span></button> ' : '') +
        (d.mine && (d.status === 'failed' || d.status === 'running') ? '<button data-act="log" title="Extraction log"><span class="mi" aria-hidden="true">receipt_long</span></button> ' : '') +
        (d.mine ? '<button data-act="delete" class="danger" title="Delete this dataset and its files"><span class="mi" aria-hidden="true">delete</span></button>' : '') +
      '</td></tr>').join('') + '</tbody></table>';
  host.querySelectorAll('button[data-act]').forEach(b => b.onclick = () => action(b.dataset.act, b.closest('tr').dataset.id, list.find(d => d.id === b.closest('tr').dataset.id)));
  clearTimeout(pollTimer);
  // 'uploading' is not polled: the tab doing the upload shows its own progress, and an abandoned one never changes
  if (list.some(d => ['queued', 'running'].includes(d.status))) pollTimer = setTimeout(loadList, 5000);
}

async function action(act, id, d) {
  try {
    if (act === 'share') return shareDialog(d);
    if (act === 'extract') { await api('/api/datasets/' + id + '/extract', { method: 'POST' }); return loadList(); }
    if (act === 'log') { const full = await api('/api/datasets/' + id); return dialog('Extraction log: ' + d.name, '<pre class="log">' + esc(full.log_tail || full.error || '(no output yet)') + '</pre>'); }
    if (act === 'delete') { if (!confirm('Delete "' + d.name + '" and all its extracted data? This cannot be undone.')) return; await api('/api/datasets/' + id, { method: 'DELETE' }); return loadList(); }
  } catch (e) { alert(e.message); }
}

function dialog(title, bodyHtml) { $('#modalTitle').textContent = title; $('#modalBody').innerHTML = bodyHtml; $('#modal').hidden = false; }

function shareDialog(d) {
  const render = shared => {
    dialog('Share "' + d.name + '"',
      '<p class="muted tiny">People you share with can open the dataset. Only you can share, re-extract, or delete it. Addresses must be ' + esc(CONFIG.allowed) + '.</p>' +
      '<form id="shareForm" class="row"><input type="email" id="shareEmail" placeholder="colleague' + esc(CONFIG.allowed.startsWith('@') ? CONFIG.allowed : '@example.org') + '" required><button type="submit" class="primary">Share</button></form>' +
      '<div class="shared"><ul>' + (shared.length ? shared.map(e => '<li><span class="mi" aria-hidden="true">person</span>' + esc(e) + ' <button class="ghost" data-unshare="' + esc(e) + '" title="Remove"><span class="mi" aria-hidden="true">close</span></button></li>').join('') : '<li class="tiny">Not shared with anyone yet.</li>') + '</ul></div>');
    $('#shareForm').onsubmit = async ev => { ev.preventDefault(); try { const r = await api('/api/datasets/' + d.id + '/share', { method: 'POST', body: JSON.stringify({ email: $('#shareEmail').value }) }); render(r.shared_with); loadList(); } catch (e) { alert(e.message); } };
    $('#modalBody').querySelectorAll('[data-unshare]').forEach(b => b.onclick = async () => { const r = await api('/api/datasets/' + d.id + '/share/' + encodeURIComponent(b.dataset.unshare), { method: 'DELETE' }); render(r.shared_with); loadList(); });
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

boot();
