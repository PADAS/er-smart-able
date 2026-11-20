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

// Help on the data browser's sidebar opens the app at #/help: the dataset list with the help drawer open
test('#/help is the list with the help open, and its entry becomes the list\'s address', () => {
  const r = P.parseRoute('#/help');
  assert.equal(r.page, 'home'); assert.equal(r.help, true);
  assert.equal(P.routeHash(r), '#/', 'reloading or going Back does not open the help again');
  assert.equal(P.parseRoute('#/').help, undefined);
  const fs = require('node:fs'), path = require('node:path');
  const app = fs.readFileSync(path.join(__dirname, '..', '..', 'web', 'static', 'app.js'), 'utf8');
  const render = app.slice(app.indexOf('function renderRoute(route) {'), app.indexOf('\n}\n', app.indexOf('function renderRoute(route) {')));
  assert.match(render, /if \(route\.help\) openHelp\(\);/);
  assert.ok(render.indexOf('if (route.help) openHelp();') > render.indexOf('closeLayers();'), 'opened after the page\'s layers are closed');
  const browser = fs.readFileSync(path.join(__dirname, '..', '..', 'browse', 'index.html'), 'utf8');
  assert.match(browser, /window\.open\('\/#\/help', '_blank', 'noopener'\)/);
});
