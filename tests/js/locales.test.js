const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..', '..', 'web');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');
const flat = (o, p = '') => Object.entries(o).flatMap(([k, v]) => typeof v === 'object' ? flat(v, p + k + '.') : [[p + k, v]]);
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
