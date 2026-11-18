const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./shim');

const EN = { greet: 'Hello {{name}}', only: { en: 'English only' }, patrol_one: '{{count}} patrol', patrol_other: '{{count}} patrols',
             link: 'Read {{more}} first', plain: 'A <b>bold</b> claim' };
const FR = { greet: 'Bonjour {{name}}', patrol_one: '{{count}} patrouille', patrol_other: '{{count}} patrouilles' };
function ctx(lang) { const P = load(); P.setMessages('en', EN); P.setMessages('fr', FR); P.setLang(lang); return P; }

test('t gives plain text in the language, English when the language lacks the key, the key when neither has it', () => {
  const P = ctx('fr');
  assert.equal(P.t('greet', { name: 'Awa' }), 'Bonjour Awa');
  assert.equal(P.t('only.en'), 'English only');
  assert.equal(P.t('no.such.key'), 'no.such.key');
  assert.equal(P.hasMessage('only.en'), true); assert.equal(P.hasMessage('no.such.key'), false);
});
test('T escapes the message and every value, and inserts only the markup the caller built', () => {
  const P = ctx('en');
  assert.equal(P.T('greet', { name: '<img src=x onerror=alert(1)>' }), 'Hello &lt;img src=x onerror=alert(1)&gt;');
  assert.equal(P.T('plain'), 'A &lt;b&gt;bold&lt;/b&gt; claim');
  assert.equal(P.T('link', {}, { more: '<a href="#x">this</a>' }), 'Read <a href="#x">this</a> first');
  assert.equal(P.t('greet', { name: '<b>' }), 'Hello <b>', 't is plain text: the caller escapes it or gives it to textContent');
});
test('tn follows the language: French takes the singular for 0 and 1, and groups digits its own way', () => {
  const en = ctx('en'), fr = ctx('fr');
  assert.equal(en.tn('patrol', 0), '0 patrols'); assert.equal(en.tn('patrol', 1), '1 patrol'); assert.equal(en.tn('patrol', 1234), '1,234 patrols');
  assert.equal(fr.tn('patrol', 0), '0 patrouille'); assert.equal(fr.tn('patrol', 1), '1 patrouille');
  assert.match(fr.tn('patrol', 1234), /^1[   ]234 patrouilles$/);
});
test('tn falls back to _other when the language has no form for the category', () => {
  const P = load(); P.setMessages('en', { x_other: '{{count}} things' }); P.setLang('en');
  assert.equal(P.tn('x', 1), '1 things');
});
test('pickLang: a remembered choice, then the browser, then English', () => {
  const P = load(), S = ['en', 'fr', 'es', 'pt', 'sw'];
  assert.equal(P.pickLang('sw', ['fr-FR'], S), 'sw');
  assert.equal(P.pickLang(null, ['pt-BR', 'en'], S), 'pt');
  assert.equal(P.pickLang('de', ['es-MX'], S), 'es');
  assert.equal(P.pickLang(null, ['de'], S), 'en');
  assert.equal(P.pickLang(null, undefined, S), 'en');
});
test('the shim gives every other test English', () => {
  assert.equal(load().currentLang(), 'en');
});
test('a made-up language code does not throw and uses English rules', () => {
  const P = load(); P.setMessages('en', EN); P.setLang('xx');
  assert.equal(P.tn('patrol', 1), '1 patrol'); assert.equal(P.fmtNum(1234), '1,234');
});
test('a null or undefined value shows nothing, in t, T and tn', () => {
  const P = ctx('en');
  assert.equal(P.t('greet', { name: null }), 'Hello ');
  assert.equal(P.t('greet', { name: undefined }), 'Hello ');
  assert.equal(P.T('greet', { name: null }), 'Hello ');
  assert.equal(P.T('greet', { name: undefined }), 'Hello ');
  assert.equal(P.T('greet', { name: 0 }), 'Hello 0');
  assert.equal(P.tn('patrol', 2, { name: null }), '2 patrols');
});
