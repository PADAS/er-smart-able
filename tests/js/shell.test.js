// tests/js/shell.test.js
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
test('every status maps to a token class', () => {
  const m = { running: 'running', continuing: 'running', queued: 'pending', planning: 'pending', uploading: 'pending', planned: 'ready',
              needs_attention: 'warning', stopped: 'warning', done: 'success', ready: 'success', failed: 'error', interrupted: 'interrupted', whatever: 'pending' };
  for (const [s, c] of Object.entries(m)) assert.equal(P.statusClass(s), c, s);
  assert.equal(P.pill('needs_attention'), '<span class="pill st-warning">needs attention</span>');
  assert.equal(P.pill('done', 'Done'), '<span class="pill st-success">Done</span>');
});
test('the sidebar marks where the reader is, for every route', () => {
  const me = { email: 'ana@example.org' }, ds = { id: 'a1', name: 'R5 <Lawin>', status: 'ready', export: [{ dir: 'x' }] };
  const at = (route, dataset) => P.railState(route, me, { dataset: dataset, lang: 'en', languages: [], theme: 'dark', version: '1.2.3' });
  assert.equal(at({ page: 'home' }).current, 'home'); assert.equal(at({ page: 'sites' }).current, 'sites');
  assert.equal(at({ page: 'dataset', id: 'a1', tab: 'overview' }, ds).current, 'overview');
  for (const tab of ['loads', 'rangers', 'backup']) assert.equal(at({ page: 'dataset', id: 'a1', tab: tab }, ds).current, 'migration:' + tab);
  assert.equal(at({ page: 'load', id: 'a1', load: 'b2' }, ds).current, 'migration:loads');
  const s = at({ page: 'dataset', id: 'a1', tab: 'overview' }, ds);
  assert.deepEqual(JSON.parse(JSON.stringify(s.dataset)), { id: 'a1', name: 'R5 <Lawin>', ready: true, loadTabs: true });   // the name whole: the stylesheet cuts it
  assert.equal(s.doc, 'app'); assert.equal(s.signedIn, true); assert.equal(s.email, 'ana@example.org'); assert.equal(s.theme, 'dark'); assert.equal(s.version, '1.2.3');
});
test('a dataset still extracting is not ready, and one not fetched yet shows the list form', () => {
  const st = (dataset) => P.railState({ page: 'dataset', id: 'a1', tab: 'overview' }, { email: 'a@example.org' }, { dataset: dataset, lang: 'en', languages: [], theme: 'system', version: '' });
  const s = st({ id: 'a1', name: 'A', status: 'running', export: [] });
  assert.equal(s.dataset.ready, false); assert.equal(s.dataset.loadTabs, false);
  assert.equal(st(null).dataset, null); assert.equal(st(null).current, null);
});
test('signed out, the sidebar state says so and names no one', () => {
  const s = P.railState(null, null, { lang: 'fr', languages: [], theme: 'system', version: '1.2.3' });
  assert.equal(s.signedIn, false); assert.equal(s.dataset, null); assert.equal(s.current, null); assert.equal(s.email, '');
});
test('sign-in names the product and the allowed domain', () => {
  const h = P.renderSignIn({ allowed: ['@earthranger.com'] });
  assert.match(h, /SMART migration/); assert.match(h, /your @earthranger\.com Google account/); assert.match(h, /id="signInBtn"/); assert.match(h, /er-lockup-h\.svg/);
});
test('the allowed phrase reads naturally for one, several or no entries', () => {
  assert.equal(P.allowedPhrase(['@earthranger.com']), 'your @earthranger.com Google account');
  assert.equal(P.allowedPhrase(['@earthranger.com', '@partner.org', 'ana@example.org']), 'a Google account at @earthranger.com, @partner.org or ana@example.org');
  assert.equal(P.allowedPhrase([]), 'your Google account');
  assert.equal(P.allowedPhrase('@earthranger.com'), 'your @earthranger.com Google account');   // the string form older servers send
  assert.match(P.renderSignIn({ allowed: ['@a.org', '@b.org'] }), /Sign in with a Google account at @a\.org or @b\.org\./);
});
test('a status with no message is still shown in words', () => {
  assert.equal(load().pill('some_new_state'), '<span class="pill st-pending">some new state</span>');
});

test('a help section in another language than the reader\'s says it is only in English', () => {
  const fr = load({ lang: 'fr', messages: { help: { englishOnly: 'ANGLAIS SEULEMENT' } } });
  const q = fr.helpSection({ id: 'quirks', title: 'SMART data <quirks>', lang: 'en', html: '<p>body</p>' });
  assert.match(q, /^<section id="help-quirks" lang="en"><h2>SMART data &lt;quirks&gt;<\/h2><p class="tiny muted" lang="fr">ANGLAIS SEULEMENT<\/p><p>body<\/p><\/section>$/);
  const own = fr.helpSection({ id: 'sites', title: 'Sites', lang: 'fr', html: '<p>corps</p>' });
  assert.equal(own, '<section id="help-sites"><h2>Sites</h2><p>corps</p></section>');
  assert.doesNotMatch(load().helpSection({ id: 'quirks', title: 'Q', lang: 'en', html: '' }), /only|lang=/, 'an English reader sees no note');
});
