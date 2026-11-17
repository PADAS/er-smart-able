// The part of web/site/lang.js that runs in a page: what it does to location and storage, with a
// stand-in document. pick() and asked() are covered in sitelang.test.js.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', '..', 'web', 'site', 'lang.js'), 'utf8');

function run({ pageLang, search = '', pathname = '/er-smart-able/loading.html', hash = '', stored = null, storage = true, browser = ['fr-FR'] }) {
  const state = { replaced: null, store: stored === null ? {} : { lang: stored }, click: null };
  const localStorage = storage
    ? { getItem: k => (k in state.store ? state.store[k] : null), setItem: (k, v) => { state.store[k] = v; } }
    : { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  const ctx = {
    document: {
      documentElement: { lang: pageLang, getAttribute: () => 'en fr es pt sw' },
      addEventListener: (name, fn) => { state.click = fn; },
    },
    window: { localStorage },
    navigator: { languages: browser },
    location: { search, pathname, hash, replace: to => { state.replaced = to; } },
  };
  vm.runInNewContext(SRC, ctx, { filename: 'lang.js' });
  return state;
}
function link(attrs) {
  const a = { attrs: { ...attrs }, getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }, setAttribute(k, v) { this.attrs[k] = v; } };
  return { target: { closest: () => a }, a };
}

test('an English page sends a reader with French remembered to the French page, keeping the place', () => {
  const s = run({ pageLang: 'en', stored: 'fr', hash: '#rangers-accounts' });
  assert.equal(s.replaced, 'fr/loading.html#rangers-accounts');
});
test('the site root is index.html', () => {
  assert.equal(run({ pageLang: 'en', pathname: '/er-smart-able/' }).replaced, 'fr/index.html');
});
test('a link that chose English is obeyed and remembered, whatever was remembered before', () => {
  const s = run({ pageLang: 'en', search: '?lang=en', stored: 'fr' });
  assert.equal(s.replaced, null);
  assert.equal(s.store.lang, 'en');
});
test('a link that chose English is obeyed when nothing can be remembered', () => {
  assert.equal(run({ pageLang: 'en', search: '?lang=en', storage: false }).replaced, null);
});
test('with storage blocked and no choice, the browser language still decides and nothing throws', () => {
  assert.equal(run({ pageLang: 'en', storage: false }).replaced, 'fr/loading.html');
});
test('a page in another language never sends the reader anywhere', () => {
  for (const stored of [null, 'en', 'es']) assert.equal(run({ pageLang: 'fr', stored }).replaced, null);
});
test('choosing a language in the header remembers it', () => {
  const s = run({ pageLang: 'fr', stored: 'fr' });
  s.click(link({ href: '../loading.html?lang=en', 'data-lang': 'en' }));
  assert.equal(s.store.lang, 'en');
});
test('English asked for and not rememberable is carried to the next page of the site, and only there', () => {
  const s = run({ pageLang: 'en', search: '?lang=en', storage: false });
  const inSite = link({ href: 'statuses.html#a-load' }); s.click(inSite);
  assert.equal(inSite.a.attrs.href, 'statuses.html?lang=en#a-load');
  const outside = link({ href: 'https://github.com/PADAS/er-smart-able' }); s.click(outside);
  assert.equal(outside.a.attrs.href, 'https://github.com/PADAS/er-smart-able');
  const remembered = run({ pageLang: 'en', search: '?lang=en' });
  const plain = link({ href: 'statuses.html' }); remembered.click(plain);
  assert.equal(plain.a.attrs.href, 'statuses.html', 'when the choice is remembered the links are left alone');
});
