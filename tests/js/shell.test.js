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
test('breadcrumb links all but the last part and escapes', () => {
  const h = P.renderBreadcrumb([{ label: 'Datasets', hash: '#/' }, { label: 'R5 <Lawin>', hash: '#/datasets/a1' }, { label: 'Load' }]);
  assert.match(h, /<a href="#\/">Datasets<\/a>/); assert.match(h, /R5 &lt;Lawin&gt;/); assert.doesNotMatch(h, /<a[^>]*>Load</);
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
