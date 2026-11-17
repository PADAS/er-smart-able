const test = require('node:test');
const assert = require('node:assert/strict');
const { pick } = require('../../web/site/lang.js');
const S = ['en', 'fr', 'es', 'pt', 'sw'];

test('a remembered language wins over the browser', () => {
  assert.equal(pick('fr', ['es-ES'], S), 'fr');
  assert.equal(pick('en', ['fr-FR'], S), null);            // choosing English sticks
});
test('with nothing remembered, the first browser language the site has', () => {
  assert.equal(pick(null, ['pt-BR', 'en'], S), 'pt');
  assert.equal(pick(null, ['fr-CA'], S), 'fr');
  assert.equal(pick(null, ['SW-ke'], S), 'sw');
  assert.equal(pick(null, ['de-DE', 'es'], S), 'es');
  assert.equal(pick(null, ['en-GB', 'fr'], S), null);      // English comes first: stay
  assert.equal(pick(null, ['de', 'ja'], S), null);
  assert.equal(pick(null, undefined, S), null);
  assert.equal(pick(null, [], S), null);
});
test('a remembered language the site no longer has is ignored', () => {
  assert.equal(pick('ne', ['en-US'], S), null);
  assert.equal(pick('ne', ['es'], S), 'es');
});
