const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
test('sites list rows, owner actions, and the empty state', () => {
  const h = P.renderSites([{ id: 's1', name: 'phinney', url: 'p.pamdas.org', token_hint: 'dbe5', checked_as: 'smart_migration', mine: true, shared_with: [] },
                           { id: 's2', name: 'other', url: 'o.pamdas.org', token_hint: 'aaaa', checked_as: 'x', mine: false, owner_email: 'a@earthranger.com', shared_with: ['me@earthranger.com'] }]);
  assert.match(h, /id="addSiteBtn"/); assert.match(h, /…dbe5 as smart_migration/);
  assert.match(h, /data-act="siteDelete" data-id="s1"/); assert.doesNotMatch(h, /data-act="siteDelete" data-id="s2"/); assert.match(h, /a@earthranger\.com/);
  assert.match(P.renderSites([]), /No sites yet\. Add the EarthRanger site you will load into\./);
});
