const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
const d = { id: 'a1', name: 'R5 <Lawin>', source_name: 'r5.zip', source_size: 2900000000, created_at: '2026-10-07T00:00:00+00:00', status: 'ready',
            cas: [{ id: '050500', n: 'Albay' }, { id: '050504', n: 'Guinobatan' }], db_version: '7.5.6', counts: { patrols: 2570, waypoints: 30791 }, mine: true, shared_with: ['x@earthranger.com'] };
test('a dataset card links to its page and shows status, areas, counts, owner', () => {
  const h = P.renderDatasetCard(d);
  assert.match(h, /href="#\/datasets\/a1"/); assert.match(h, /R5 &lt;Lawin&gt;/); assert.match(h, /2\.9 GB/);
  assert.match(h, /st-success/); assert.match(h, /Albay/); assert.match(h, /050504/); assert.match(h, /2,570 patrols/); assert.match(h, /you/); assert.match(h, /shared/);
});
test('a failed extraction shows its error on the card', () => {
  assert.match(P.renderDatasetCard({ ...d, status: 'failed', error: 'zip is not a SMART backup' }), /st-error[\s\S]*zip is not a SMART backup/);
});
test('home orders newest first and has an empty state', () => {
  const h = P.renderHome([{ ...d, id: 'old', created_at: '2026-01-01T00:00:00+00:00' }, { ...d, id: 'new', created_at: '2026-11-01T00:00:00+00:00' }]);
  assert.ok(h.indexOf('#/datasets/new') < h.indexOf('#/datasets/old'));
  assert.match(P.renderHome([]), /No datasets yet\. Upload a backup or export to begin\./);
  assert.match(h, /id="uploadBtn"/);
});
test('the home page follows the language', () => {
  const P = load({ lang: 'xx', messages: { home: { title: 'TITRE', upload: 'ENVOYER' }, status: { ready: 'PRÊT' } } });
  const h = P.renderHome([{ id: 'a1', name: 'R5', status: 'ready', mine: true }]);
  assert.match(h, /<h1>TITRE<\/h1>/); assert.match(h, />ENVOYER<\/button>/); assert.match(h, /<span class="pill st-success">PRÊT<\/span>/);
});
test('the sign-in sentence is the language\'s own, with the domain as data', () => {
  const P = load({ lang: 'xx', messages: { signin: { yourDomainAccount: 'COMPTE {{domain}}' } } });
  assert.match(P.renderSignIn({ allowed: ['@a<b>.org'] }), /COMPTE @a&lt;b&gt;\.org/);
});
test('only support staff are shown the all-users switch', () => {
  assert.ok(!P.renderHome([d]).includes('id="allUsers"'));
  assert.ok(!P.renderHome([d], { support: false, all: true }).includes('id="allUsers"'));
  assert.match(P.renderHome([d], { support: true, all: false }), /<input type="checkbox" id="allUsers">All users/);
  assert.match(P.renderHome([d], { support: true, all: true }), /id="allUsers" checked>/);
});

// ---- the upload form: one upload at a time
test('Upload is on only with a file chosen and no upload on its way', () => {
  assert.equal(P.canUpload(null, false), false);
  assert.equal(P.canUpload({ name: 'a.zip' }, false), true);
  assert.equal(P.canUpload({ name: 'b.zip' }, true), false, 'choosing another file mid-upload does not turn Upload back on');
  assert.equal(P.canUpload(null, true), false);
  const src = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', '..', 'web', 'static', 'app.js'), 'utf8');
  // one form's wiring for both uploads: a new dataset's, and a backup uploaded again for a dataset
  const form = src.slice(src.indexOf('function wireUpload'), src.indexOf('// mirrors findings.ca_identifier'));
  assert.match(form, /\$\('#uploadSubmit', form\)\.disabled = !canUpload\(\$\('#dsFile', form\)\.files\[0\], uploading\);/, 'the button asks that question');
  assert.equal((form.match(/#uploadSubmit'[^;\n]*\.disabled = /g) || []).length, 1, 'and nothing else in the form sets it');
  assert.match(form, /\$\('#dsPick', form\)\.disabled = uploading;/, 'the file cannot be changed meanwhile');
  assert.match(form, /if \(!canUpload\(file, uploading\)\) return;/, 'and a submit that arrives anyway is dropped');
  assert.equal((form.match(/wireUpload\(form, async/g) || []).length, 2, 'both upload dialogs are wired by it');
});
