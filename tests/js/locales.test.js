const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..', '..', 'web');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');
const flat = (o, p = '') => Object.entries(o).flatMap(([k, v]) => typeof v === 'object' ? flat(v, p + k + '.') : [[p + k, v]]);
const { load } = require('./shim');
const EN = Object.fromEntries(flat(JSON.parse(read('static/locales/en.json'))));

test('every key the code and the template ask for is in the English file', () => {
  const src = read('static/pages.js') + read('static/app.js');
  const asked = new Set([...src.matchAll(/\b(?:T|t|hasMessage)\(\s*'([\w.]+)'/g)].map(m => m[1]));
  for (const m of src.matchAll(/\btn\(\s*'([\w.]+)'/g)) asked.add(m[1] + '_other');
  for (const m of read('templates/index.html').matchAll(/data-i18n(?:-title|-aria)?="([\w.]+)"/g)) asked.add(m[1]);
  // a key ending in '.' is a prefix a later lookup completes from the data, such as T('status.' + status)
  const missing = [...asked].filter(k => !k.endsWith('.')).filter(k => !(k in EN));
  assert.deepEqual(missing, []);
});
test('no message holds markup', () => {
  for (const [k, v] of Object.entries(EN)) assert.doesNotMatch(v, /<[a-z/]/i, k);
});
test('changing language forgets the loaded help and drops a pending fetch', () => {
  const src = read('static/app.js');
  const body = src.slice(src.indexOf('async function useLang'), src.indexOf('async function boot'));
  assert.match(body, /HELP = null;\s*helpLoading = null;\s*helpGen\+\+/);
  const open = src.slice(src.indexOf('async function openHelp'));
  assert.match(open, /gen = helpGen/);
  assert.match(open, /gen !== helpGen/);
});
// Functions in pages.js that build plain text for a caller that escapes it (or passes it to t() or textContent):
// fmtBytes and fmtDur are wrapped in esc() or handed to a message as a value; loadScope and loadName are wrapped in
// esc() (or passed as a breadcrumb label, which renderBreadcrumb escapes); loadFacts returns the facts under a
// load's title, which the title block escapes with facts.map(esc); stageLabel returns the words handed to pill(),
// which escapes its label; errorMessage returns the words for alert() or textContent.
const PLAIN_TEXT_FUNCTIONS = ['fmtBytes', 'fmtDur', 'loadScope', 'loadName', 'loadFacts', 'stageLabel', 'errorMessage'];
test('t() is used only where plain text is wanted; markup is built with T()', () => {
  const src = read('static/app.js') + read('static/pages.js');
  // dialog( and prompt( write or show their first argument as text; renderBreadcrumb escapes each label
  const ok = /(?:esc\(|alert\(|confirm\(|prompt\(|dialog\(|\.textContent = |\.title = |\.placeholder = |new Error\(|label: |setAttribute\([^,]+, )\s*$/;
  const bad = [...src.matchAll(/\bt\(\s*'[\w.]+'/g)]
    .filter(m => !m[0].endsWith(".'"))   // a key ending in '.' is a prefix completed from the data
    .filter(m => !ok.test(src.slice(Math.max(0, m.index - 40), m.index)))
    .filter(m => !PLAIN_TEXT_FUNCTIONS.includes(([...src.slice(0, m.index).matchAll(/\bfunction (\w+)\(/g)].pop() || [])[1]))
    .map(m => src.slice(Math.max(0, m.index - 40), m.index + m[0].length));
  assert.deepEqual(bad, []);
});
test('the wiring script holds no confirm or alert with words of its own', () => {
  const src = read('static/app.js');
  assert.deepEqual([...src.matchAll(/\b(?:alert|confirm)\(\s*'[^']*[A-Za-z]{3,} [a-z]/g)].map(m => m[0]), []);
});
test('every English message is used by the code or the template', () => {
  const src = read('static/pages.js') + read('static/app.js') + read('templates/index.html');
  const dynamic = [/^status\./, /^stages\./, /^findings\.severity\./, /^errors\./, /^findingText\./, /^findings\.valueLabel\./, /^csv\./, /^plan\.(?:create|update|deactivate)$/];   // looked up by a value from the data
  const unused = Object.keys(EN).filter(k => !dynamic.some(d => d.test(k)) && !src.includes("'" + k.replace(/_(one|other)$/, '') + "'") && !src.includes('"' + k + '"'));
  assert.deepEqual(unused, []);
});
test('every csv column the rangers download names has a header message', () => {
  const src = read('static/app.js');
  const cols = [...src.match(/const CSV_COLUMNS = \[([^\]]*)\]/)[1].matchAll(/'(\w+)'/g)].map(m => m[1]);
  assert.ok(cols.length > 0);
  assert.deepEqual(cols.filter(c => !('csv.' + c in EN)), []);
  assert.deepEqual(Object.keys(EN).filter(k => k.startsWith('csv.') && !cols.includes(k.slice(4))), []);
});
test('an error is shown in the language when its code is known, and as the server worded it when not', () => {
  const P = load({ lang: 'xx', messages: { errors: { dataset_not_found: 'INTROUVABLE', language_not_in_bundle: 'LANGUE {{language}}' } } });
  assert.equal(P.errorMessage(404, 'Not Found', { detail: 'Dataset not found', code: 'dataset_not_found', values: {} }), 'INTROUVABLE');
  assert.equal(P.errorMessage(400, 'Bad Request', { detail: 'x', code: 'language_not_in_bundle', values: { language: 'zz' } }), 'LANGUE zz');
  assert.equal(P.errorMessage(409, 'Conflict', { detail: 'Something new', code: 'brand_new_code' }), 'Something new');
  assert.equal(P.errorMessage(409, 'Conflict', { detail: 'Old server, no code' }), 'Old server, no code');
  assert.equal(P.errorMessage(422, 'Unprocessable', { detail: [{ loc: ['body', 'name'], msg: 'field required' }], code: 'invalid_request' }), 'The request was not valid.');
  assert.equal(P.errorMessage(500, 'Internal Server Error', null), 'Internal Server Error');
});
test('an error with odd values does not throw, and values are plain text', () => {
  const P = load({ lang: 'xx', messages: { errors: { dataset_status: 'STATUT {{status}}' } } });
  for (const values of [undefined, null, 'x', 5, []]) {
    assert.doesNotThrow(() => P.errorMessage(409, 'Conflict', { detail: 'd', code: 'dataset_status', values }));
  }
  assert.equal(P.errorMessage(409, 'Conflict', { detail: 'd', code: 'dataset_status', values: { status: '<b>x</b>' } }), 'STATUT <b>x</b>');
  assert.equal(P.errorMessage(401, '', undefined), '401');
});
const LANGS = JSON.parse(read('static/locales/languages.json')).map(l => l.code).filter(c => c !== 'en');
for (const code of LANGS) {
  test(code + ' has every English message, with the same placeholders', () => {
    const L = Object.fromEntries(flat(JSON.parse(read('static/locales/' + code + '.json'))));
    const ph = s => (s.match(/\{\{\w+\}\}/g) || []).sort().join(' ');
    for (const [k, v] of Object.entries(EN)) {
      assert.ok(k in L && L[k].trim(), code + ' lacks ' + k);
      assert.equal(ph(L[k]), ph(v), code + ' ' + k);
      assert.doesNotMatch(L[k], /<[a-z/]/i, code + ' ' + k);
    }
    for (const k of Object.keys(L)) assert.ok(k in EN || /_(zero|one|two|few|many|other)$/.test(k) && k.replace(/_\w+$/, '_other') in EN, code + ' has an unknown key ' + k);
  });
  test(code + ' names no host but the example and holds no token', () => {
    const s = read('static/locales/' + code + '.json');
    assert.deepEqual([...new Set(s.match(/[a-z0-9-]+\.pamdas\.org/g) || [])].filter(h => !['example.pamdas.org', 'site.pamdas.org'].includes(h)), []);
    assert.doesNotMatch(s, /\b[0-9a-f]{32,}\b/);
  });
}
