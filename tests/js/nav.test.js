// tests/js/nav.test.js: the sidebar both documents draw (web/static/nav.js)
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
const L = k => P.T(k);
const DS = { id: 'a1', name: 'Area', ready: true, loadTabs: true };
function rail(over) {
  return P.renderRail(Object.assign({ doc: 'app', hosted: true, signedIn: true, dataset: DS, current: 'overview', lang: 'en',
    languages: [{ code: 'en', name: 'English' }, { code: 'fr', name: 'Français' }], theme: 'system', email: 'ana@example.org', version: '0.0.0' }, over), L);
}

test('outside a dataset the rail lists datasets and sites', () => {
  const h = rail({ current: 'home', dataset: null });
  assert.match(h, /<a[^>]*href="#\/"[^>]*class="on"[^>]*aria-current="page"/); assert.match(h, /href="#\/sites"/);
  assert.doesNotMatch(h, /rail-dataset/);
});
test('inside a dataset it shows that dataset in two groups, and no sites', () => {
  const h = rail({ current: 'migration:loads' });
  const order = ['Datasets', 'Overview', 'Data', 'Summary', 'Patrols', 'Rangers', 'Map', 'Observations', 'Data model', 'Profiles', 'Schema', 'Migration', 'Loads', 'Match rangers', 'Backup'];
  let at = -1; for (const w of order) { const i = h.indexOf('>' + w, at + 1); assert.ok(i > at, w); at = i; }
  assert.match(h, /href="\/d\/a1\/#patrols"/); assert.match(h, /href="#\/datasets\/a1\/loads"[^>]*class="on"/);
  assert.doesNotMatch(h, /#\/sites/);
});
test('a dataset that is not ready has its data entries off, not linked', () => {
  const h = rail({ dataset: { id: 'a1', name: 'Area', ready: false, loadTabs: false } });
  assert.doesNotMatch(h, /href="\/d\/a1\//); assert.equal((h.match(/class="off" aria-disabled="true"/g) || []).length, 8 + 2);   // eight views, Loads and Match rangers
  assert.match(h, /href="#\/datasets\/a1\/backup"/);
});
test('the name is escaped', () => { assert.match(rail({ dataset: { id: 'a1', name: 'R5 <b>', ready: true, loadTabs: true } }), /R5 &lt;b&gt;/); });
test('the browser links back to the app, and its views are its own', () => {
  const h = rail({ doc: 'browser', current: 'data:map' });
  assert.match(h, /href="\/#\/"/); assert.match(h, /href="\/#\/datasets\/a1\/loads"/); assert.match(h, /href="#map"[^>]*class="on"/);
});
test('from a folder there is only the data group and the fold control', () => {
  const h = rail({ doc: 'browser', hosted: false, signedIn: false, dataset: null, current: 'data:overview' });
  assert.match(h, /id="railToggle"/); assert.match(h, /href="#patrols"/);
  for (const no of ['/#/', 'id="lang"', 'id="helpBtn"', 'id="signOut"', 'name="theme"', 'Migration']) assert.ok(!h.includes(no), no);
});
test('signed out, only theme and language', () => {
  const h = rail({ signedIn: false, dataset: null, current: null });
  assert.match(h, /name="theme"/); assert.match(h, /id="lang"/); assert.doesNotMatch(h, /href="#\/"|id="signOut"|id="helpBtn"/);
});
test('another language says the data pages are in English', () => {
  assert.match(rail({ lang: 'fr' }), /in English/);
  assert.doesNotMatch(rail({ lang: 'en' }), /in English/);
});
test('the browser view ids are the browser\'s', () => { assert.deepEqual(Array.from(P.NAV_DATA, e => e[0]), ['overview', 'patrols', 'rangers', 'map', 'observations', 'datamodel', 'profiles', 'schema']); });
test('the chosen theme and language are marked, and the account is named', () => {
  const h = rail({ theme: 'dark', lang: 'fr' });
  assert.match(h, /value="dark"[^>]* checked>/); assert.match(h, /<option value="fr"[^>]*selected/); assert.match(h, /ana@example\.org/); assert.match(h, /0\.0\.0/);
});

// ---- from the whole-branch review
const fs = require('node:fs'); const path = require('node:path');
const APP = fs.readFileSync(path.join(__dirname, '..', '..', 'web', 'static', 'app.js'), 'utf8');
const BROWSER = fs.readFileSync(path.join(__dirname, '..', '..', 'browse', 'index.html'), 'utf8');
const fn = (src, head) => { const i = src.indexOf(head); assert.ok(i >= 0, head); return src.slice(i, src.indexOf('\n}\n', i)); };
test('the fold control says whether the sidebar is open', () => {
  assert.match(rail({ open: true }), /id="railToggle"[^>]*aria-expanded="true"/);
  assert.match(rail({ open: false }), /id="railToggle"[^>]*aria-expanded="false"/);
  assert.match(rail({}), /id="railToggle"[^>]*aria-expanded="true"/, 'open unless told otherwise');
  assert.match(fn(APP, 'function drawRail() {'), /open: document\.documentElement\.dataset\.nav !== 'closed'/);
  assert.match(fn(APP, 'function setNav(state, remember) {'), /setAttribute\('aria-expanded'/);
  assert.match(fn(BROWSER, 'function drawRail() {'), /open: document\.documentElement\.getAttribute\('data-nav'\) !== 'closed'/);
});
test('the sidebar the app draws has its Help button bound, every time it is drawn', () => {
  assert.match(fn(APP, 'function drawRail() {'), /\$\('#helpBtn'\)\.onclick = \(\) => openHelp\(\);/);
  assert.doesNotMatch(fn(APP, 'async function boot() {'), /#helpBtn|#signOut|#account|#lang'\)\.onchange/, 'boot binds nothing the sidebar re-creates');
});
test('choosing a language keeps the keyboard on the language menu', () => {
  assert.match(fn(APP, 'function drawRail() {'), /await useLang\(\$\('#lang'\)\.value, true\);[\s\S]*\$\('#lang'\)\.focus\(\);/);
  assert.match(fn(BROWSER, 'async function hostedRail(lang, refocus) {'), /drawRail\(\);\s*if \(refocus\) \$\('#lang'\)\.focus\(\);/);
});
test('the theme is three radios in one control, each named, the chosen one checked', () => {
  const h = rail({ theme: 'dark' });
  const group = h.slice(h.indexOf('<div class="rail-theme"'), h.indexOf('<label class="rail-lang"'));
  assert.match(group, /role="radiogroup" aria-label="Theme"/);
  assert.deepEqual([...group.matchAll(/value="(\w+)" aria-label="(\w+)"( checked)?/g)].map(m => m.slice(1, 4)), [['system', 'System', undefined], ['light', 'Light', undefined], ['dark', 'Dark', ' checked']]);
  assert.doesNotMatch(h, /themeMenu|menu-theme/);
});
test('the fold control\'s line is named, and the version closes the foot outside the account menu', () => {
  const h = rail({});
  assert.match(h, /<span class="rail-heading">Resources<\/span><button id="railToggle"/);
  assert.match(h, /<\/details><p class="tiny menu-version">0\.0\.0<\/p><\/div>$/);
  assert.match(rail({ signedIn: false, dataset: null, current: null }), /<p class="tiny menu-version">0\.0\.0<\/p><\/div>$/, 'signed out too');
});
