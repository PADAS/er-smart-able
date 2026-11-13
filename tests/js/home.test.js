const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
const d = { id: 'a1', name: 'R5 <Lawin>', source_name: 'r5.zip', source_size: 2900000000, created_at: '2026-10-07T00:00:00+00:00', status: 'ready',
            cas: [{ id: '050500', n: 'Albay' }, { id: '050504', n: 'Guinobatan' }], db_version: '7.5.6', counts: { patrols: 2570, waypoints: 30791 }, mine: true, shared_with: ['x@earthranger.com'] };
test('a dataset card links to its page and shows status, areas, counts, owner', () => {
  const h = P.renderDatasetCard(d);
  assert.match(h, /href="#\/datasets\/a1"/); assert.match(h, /R5 &lt;Lawin&gt;/); assert.match(h, /2\.9 GB/);
  assert.match(h, /st-success/); assert.match(h, /Albay/); assert.match(h, /050504/); assert.match(h, /2,570 patrols/); assert.match(h, /you/); assert.match(h, /shared/);
});
test('a failed extraction shows its error on the card', () => {
  assert.match(P.renderDatasetCard({ ...d, status: 'failed', error: 'zip is not a SMART backup' }), /st-error[\s\S]*zip is not a SMART backup/);
});
test('home orders newest first and has an empty state', () => {
  const h = P.renderHome([{ ...d, id: 'old', created_at: '2026-01-01T00:00:00+00:00' }, { ...d, id: 'new', created_at: '2026-11-01T00:00:00+00:00' }]);
  assert.ok(h.indexOf('#/datasets/new') < h.indexOf('#/datasets/old'));
  assert.match(P.renderHome([]), /No datasets yet\. Upload a backup or export to begin\./);
  assert.match(h, /id="uploadBtn"/);
});
