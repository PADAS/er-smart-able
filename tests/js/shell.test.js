// tests/js/shell.test.js
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
test('every status maps to a token class', () => {
  const m = { running: 'running', continuing: 'running', queued: 'pending', planning: 'pending', uploading: 'pending', planned: 'ready',
              needs_attention: 'warning', done: 'success', ready: 'success', failed: 'error', interrupted: 'interrupted', whatever: 'pending' };
  for (const [s, c] of Object.entries(m)) assert.equal(P.statusClass(s), c, s);
  assert.equal(P.pill('needs_attention'), '<span class="pill st-warning">needs attention</span>');
  assert.equal(P.pill('done', 'Done'), '<span class="pill st-success">Done</span>');
});
test('breadcrumb links all but the last part and escapes', () => {
  const h = P.renderBreadcrumb([{ label: 'Datasets', hash: '#/' }, { label: 'R5 <Lawin>', hash: '#/datasets/a1' }, { label: 'Load' }]);
  assert.match(h, /<a href="#\/">Datasets<\/a>/); assert.match(h, /R5 &lt;Lawin&gt;/); assert.doesNotMatch(h, /<a[^>]*>Load</);
});
test('sign-in names the product and the allowed domain', () => {
  const h = P.renderSignIn({ allowed: '@earthranger.com' });
  assert.match(h, /SMART migration/); assert.match(h, /@earthranger\.com/); assert.match(h, /id="signInBtn"/); assert.match(h, /er-lockup-h\.svg/);
});
