const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./shim');

test('pages.js loads with no DOM and exposes its functions', () => {
  const P = load();
  assert.equal(typeof P.esc, 'function');
  assert.equal(P.esc('<a & "b">'), '&lt;a &amp; &quot;b&quot;&gt;');
});
