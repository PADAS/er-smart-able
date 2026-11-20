// The sidebar both documents draw: the app (web/templates/index.html) loads this file, and the data
// browser (browse/index.html) carries a copy between markers, written by scripts/sync_nav.py and
// checked by tests/test_viewer_page.py. Nothing here touches the document, storage or the messages:
// the caller passes the state and a label(key, english) function that returns escaped text.

// the browser's views: id (its hash and TABS), English name, icon
var NAV_DATA = [['overview', 'Summary', 'dashboard'], ['patrols', 'Patrols', 'hiking'], ['rangers', 'Rangers', 'groups'],
  ['map', 'Map', 'map'], ['observations', 'Observations', 'visibility'], ['datamodel', 'Data model', 'account_tree'],
  ['profiles', 'Profiles', 'badge'], ['schema', 'Schema', 'schema']];
// the dataset page's parts that migrate it: the app's tab name, English name, icon, message key
var NAV_MIGRATION = [['loads', 'Loads', 'upload', 'nav.loads'], ['rangers', 'Match rangers', 'how_to_reg', 'nav.matchRangers'],
  ['backup', 'Backup', 'inventory_2', 'nav.backup']];

function _navEsc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function _navIcon(name) { return '<span class="mi" aria-hidden="true">' + name + '</span>'; }
// one entry: a link, the current one marked, or a span when it cannot be opened. text is escaped already.
function _navEntry(current, nav, href, icon, text, off) {
  var inner = _navIcon(icon) + '<span class="label">' + text + '</span>';
  if (off) return '<span class="off" aria-disabled="true" title="' + text + '">' + inner + '</span>';
  return '<a href="' + _navEsc(href) + '" data-nav="' + nav + '"' + (current === nav ? ' class="on" aria-current="page"' : '') + ' title="' + text + '">' + inner + '</a>';
}

// state: { doc: 'app'|'browser', hosted, signedIn, dataset: null|{id, name, ready, loadTabs}, current,
//          lang, languages: [{code, name}], theme: 'system'|'light'|'dark', email, version }
function renderRail(state, label) {
  var s = state || {}, d = s.dataset, browser = s.doc === 'browser', hosted = s.hosted !== false;
  var app = browser ? '/' : '';   // the app's addresses, as seen from each document
  var h = '<div class="rail-top">' +
    (hosted ? '<span class="rail-brand"><img class="logo-light" src="/static/img/er-lockup-h.svg" alt="EarthRanger"><img class="logo-dark" src="/static/img/er-lockup-white-h.svg" alt="EarthRanger"></span>' : '') +
    '<span class="rail-app">' + label('shell.appName', 'SMART migration') + '</span>' +
    '<button id="railToggle" type="button" aria-controls="rail" title="' + label('nav.fold', 'Open or collapse the list') + '" aria-label="' + label('nav.fold', 'Open or collapse the list') + '">' + _navIcon('left_panel_close') + '</button></div>';

  h += '<div class="rail-main">';
  if (hosted && s.signedIn) {
    if (d) h += _navEntry(null, 'home', app + '#/', 'arrow_back', label('nav.datasets', 'Datasets'));
    else {
      h += _navEntry(s.current, 'home', app + '#/', 'folder', label('nav.datasets', 'Datasets'));
      if (!browser) h += _navEntry(s.current, 'sites', '#/sites', 'public', label('nav.sites', 'Sites'));
    }
  }
  if (d) {
    h += '<div class="rail-dataset" title="' + _navEsc(d.name) + '">' + _navEsc(d.name) + '</div>' +
      _navEntry(s.current, 'overview', app + '#/datasets/' + d.id, 'info', label('nav.overview', 'Overview'));
  }
  if (d || browser) {
    h += '<div class="rail-group"><span>' + label('nav.data', 'Data') + '</span>' +
      (hosted && s.lang && s.lang !== 'en' ? ' <span class="rail-note">' + label('dataset.browseInEnglish', 'in English') + '</span>' : '') + '</div>' +
      '<div id="railFilter"></div>';
    for (var i = 0; i < NAV_DATA.length; i++) {
      var v = NAV_DATA[i];
      h += _navEntry(s.current, 'data:' + v[0], browser ? '#' + v[0] : '/d/' + d.id + '/#' + v[0], v[2], label('nav.view.' + v[0], v[1]), !browser && !d.ready);
    }
  }
  if (d && hosted) {
    h += '<div class="rail-group"><span>' + label('nav.migration', 'Migration') + '</span></div>';
    for (var j = 0; j < NAV_MIGRATION.length; j++) {
      var m = NAV_MIGRATION[j];
      h += _navEntry(s.current, 'migration:' + m[0], app + '#/datasets/' + d.id + '/' + m[0], m[2], label(m[3], m[1]), m[0] !== 'backup' && !d.loadTabs);
    }
  }
  h += '</div>';
  if (!hosted) return h;

  var themes = [['system', 'shell.themeSystem', 'System'], ['light', 'shell.themeLight', 'Light'], ['dark', 'shell.themeDark', 'Dark']];
  h += '<div class="rail-foot">' +
    '<details class="rail-menu" id="themeMenu"><summary title="' + label('shell.theme', 'Theme') + '">' + _navIcon('dark_mode') + '<span class="label">' + label('shell.theme', 'Theme') + '</span></summary><fieldset class="menu-theme">' +
    themes.map(function (t) { return '<label><input type="radio" name="theme" value="' + t[0] + '"' + (s.theme === t[0] ? ' checked' : '') + '><span>' + label(t[1], t[2]) + '</span></label>'; }).join('') +
    '</fieldset></details>' +
    '<label class="rail-lang" title="' + label('shell.language', 'Language') + '">' + _navIcon('translate') + '<select id="lang" class="lang-select" aria-label="' + label('shell.language', 'Language') + '">' +
    (s.languages || []).map(function (l) { return '<option value="' + _navEsc(l.code) + '" lang="' + _navEsc(l.code) + '"' + (l.code === s.lang ? ' selected' : '') + '>' + _navEsc(l.name) + '</option>'; }).join('') +
    '</select></label>';
  if (s.signedIn) {
    h += '<button id="helpBtn" type="button" title="' + label('shell.help', 'Help') + '">' + _navIcon('help') + '<span class="label">' + label('shell.help', 'Help') + '</span></button>' +
      '<details class="rail-menu" id="account"><summary id="whoEmail" title="' + _navEsc(s.email) + '">' + _navIcon('account_circle') + '<span class="label">' + _navEsc(s.email) + '</span></summary>' +
      '<button id="signOut" type="button" class="menu-item">' + _navIcon('logout') + '<span>' + label('shell.signOut', 'Sign out') + '</span></button>' +
      (s.version ? '<p class="tiny menu-version">' + _navEsc(s.version) + '</p>' : '') + '</details>';
  }
  return h + '</div>';
}
