const test = require('node:test'); const assert = require('node:assert/strict'); const { load } = require('./shim');
const P = load();
test('sites list rows, owner actions, and the empty state', () => {
  const h = P.renderSites([{ id: 's1', name: 'phinney', url: 'p.pamdas.org', token_hint: 'dbe5', checked_as: 'smart_migration', mine: true, shared_with: [] },
                           { id: 's2', name: 'other', url: 'o.pamdas.org', token_hint: 'aaaa', checked_as: 'x', mine: false, owner_email: 'a@earthranger.com', shared_with: ['me@earthranger.com'] }]);
  assert.match(h, /id="addSiteBtn"/); assert.match(h, /…dbe5 as smart_migration/);
  assert.match(h, /data-act="siteDelete" data-id="s1"/); assert.doesNotMatch(h, /data-act="siteDelete" data-id="s2"/); assert.match(h, /a@earthranger\.com/);
  assert.match(P.renderSites([]), /No sites yet\. Add the EarthRanger site you will load into\./);
});
test('the sites are a page of their own, with their own add button; home lists datasets only', () => {
  const sites = [{ id: 's1', name: 'North <Zone>', url: 'north.pamdas.org', token_hint: 'dbe5', checked_as: 'smart_migration', mine: true, shared_with: [] }];
  const h = P.renderSitesPage(sites);
  assert.match(h, /<section id="sites"[^>]*>.*<h1>EarthRanger sites<\/h1>.*id="addSiteBtn"/s);
  assert.match(h, /North &lt;Zone&gt;/); assert.doesNotMatch(h, /id="uploadBtn"/);
  assert.match(P.renderSitesPage([]), /No sites yet\. Add the EarthRanger site you will load into\./);
  const home = P.renderHome([{ id: 'a1', name: 'R5', status: 'ready', mine: true }]);
  assert.doesNotMatch(home, /id="sites"/); assert.doesNotMatch(home, /id="addSiteBtn"/); assert.match(home, /id="uploadBtn"/);
});
test('support staff get the all-users switch on the sites page too, and no one else does', () => {
  assert.match(P.renderSitesPage([], null, { support: true, all: true }), /id="allUsers" checked>/);
  assert.match(P.renderSitesPage([], null, { support: true, all: false }), /<input type="checkbox" id="allUsers">All users/);
  assert.ok(!P.renderSitesPage([], null, { support: false, all: true }).includes('id="allUsers"'));
  assert.ok(!P.renderSitesPage([]).includes('id="allUsers"'));
});
test('the owner of a site can edit, share and remove it; someone it is shared with cannot', () => {
  const h = P.renderSites([{ id: 's1', name: 'mine', url: 'a.pamdas.org', token_hint: '1111', checked_as: 'u', mine: true, shared_with: [] },
                           { id: 's2', name: 'theirs', url: 'b.pamdas.org', token_hint: '2222', checked_as: 'u', mine: false, owner_email: 'a@earthranger.com', shared_with: [] }]);
  for (const act of ['siteEdit', 'siteShare', 'siteDelete']) {
    assert.match(h, new RegExp('data-act="' + act + '" data-id="s1"')); assert.doesNotMatch(h, new RegExp('data-act="' + act + '" data-id="s2"'));
  }
});
test('when the sites could not be fetched the page says why, with no table and no empty-state line', () => {
  const h = P.renderSitesPage(null, 'Sites are <down>', { support: true, all: false });
  assert.match(h, /<section id="sites"/); assert.match(h, /Sites are &lt;down&gt;/); assert.doesNotMatch(h, /No sites yet/); assert.doesNotMatch(h, /<table/);
  assert.match(h, /id="allUsers"/, 'the switch stays, so support can turn it off again');
});
test('the edit form is filled from the site, shows its address as fixed, and asks for a token only to replace it', () => {
  const h = P.siteEditBody({ id: 's1', name: 'North "Zone"', url: 'north.pamdas.org', token_hint: 'dbe5', checked_as: 'smart_migration' });
  assert.match(h, /<input type="text" id="siteName" required value="North &quot;Zone&quot;">/);
  assert.match(h, /north\.pamdas\.org/); assert.doesNotMatch(h, /id="siteUrl"/, 'the address is not a field');
  assert.match(h, /<input type="password" id="siteToken" autocomplete="off" placeholder="leave empty to keep the current token">/);
  assert.doesNotMatch(h, /id="siteToken"[^>]*required/); assert.doesNotMatch(h, /dbe5"|value="[^"]*dbe5/, 'no token text is put into a field');
  assert.match(h, /…dbe5 as smart_migration/); assert.match(h, /id="siteBtn">Save<\/button>/);
});
test('#/sites is an address of its own', () => {
  assert.equal(P.parseRoute('#/sites').page, 'sites');
});
test('a site seen through support view shows whose token it is, not its hint, and no actions', () => {
  const h = P.renderSites([{ id: 's9', name: 'theirs', url: 'example.pamdas.org', token_hint: null, checked_as: 'migration', mine: false, access: 'support', owner_email: 'owner@example.org', shared_with: [] }]);
  assert.match(h, /checked as migration/); assert.match(h, /owner@example\.org/);
  assert.doesNotMatch(h, /undefined|null|…/); assert.doesNotMatch(h, /data-act=/);
  assert.doesNotMatch(P.renderSites([{ id: 's9', name: 'n', url: 'u', mine: false, access: 'support', shared_with: [] }]), /undefined|null/);
});
