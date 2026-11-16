// tests/js/router.test.js
const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
// objects built inside the VM context have its own Object.prototype, which deepStrictEqual rejects; copy them out
const parse = h => JSON.parse(JSON.stringify(P.parseRoute(h)));
test('parseRoute maps every route and tolerates junk', () => {
  assert.deepEqual(parse(''), { page: 'home' });
  assert.deepEqual(parse('#/'), { page: 'home' });
  assert.deepEqual(parse('#/datasets/abc123'), { page: 'dataset', id: 'abc123', tab: 'overview' });
  assert.deepEqual(parse('#/datasets/abc123/loads'), { page: 'dataset', id: 'abc123', tab: 'loads' });
  assert.deepEqual(parse('#/datasets/abc123/rangers'), { page: 'dataset', id: 'abc123', tab: 'rangers' });
  assert.deepEqual(parse('#/datasets/abc123/loads/ld9'), { page: 'load', id: 'abc123', load: 'ld9' });
  assert.deepEqual(parse('#/sites'), { page: 'sites' });
  assert.deepEqual(parse('#load/ld9'), { page: 'legacy-load', load: 'ld9' });
  assert.deepEqual(parse('#/nonsense/x'), { page: 'home' });
  assert.deepEqual(parse('#/datasets/<script>'), { page: 'home' });   // ids are [A-Za-z0-9]+
});
test('routeHash inverts parseRoute', () => {
  for (const h of ['#/', '#/datasets/abc123', '#/datasets/abc123/loads', '#/datasets/abc123/rangers', '#/datasets/abc123/loads/ld9', '#/sites'])
    assert.equal(P.routeHash(P.parseRoute(h)), h);
});
