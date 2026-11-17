// Message functions for the app's languages. Plain browser script: top-level functions are globals,
// and nothing here touches window or document, so tests load it in a bare vm context.
var _messages = {};
var _lang = 'en';

function setMessages(lang, messages) { _messages[lang] = messages || {}; }
function setLang(lang) { _lang = lang; }
function currentLang() { return _lang; }

function _escText(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function _lookup(lang, key) {
  var node = _messages[lang];
  var parts = key.split('.');
  for (var i = 0; i < parts.length; i++) {
    if (node === null || typeof node !== 'object' || !Object.prototype.hasOwnProperty.call(node, parts[i])) return undefined;
    node = node[parts[i]];
  }
  return typeof node === 'string' ? node : undefined;
}

function _find(key) {
  var m = _lookup(_lang, key);
  return m !== undefined ? m : _lookup('en', key);
}

function hasMessage(key) { return _find(key) !== undefined; }

function _val(v) { return v == null ? '' : String(v); }   // a missing value shows nothing, as esc() always did
function _has(o, k) { return o != null && Object.prototype.hasOwnProperty.call(o, k); }

function t(key, values) {
  var m = _find(key);
  if (m === undefined) return key;
  return m.replace(/\{\{(\w+)\}\}/g, function (all, name) { return _has(values, name) ? _val(values[name]) : all; });
}

function T(key, values, html) {
  var m = _find(key);
  if (m === undefined) return _escText(key);
  return _escText(m).replace(/\{\{(\w+)\}\}/g, function (all, name) {
    if (_has(html, name)) return html[name];
    if (_has(values, name)) return _escText(_val(values[name]));
    return all;
  });
}

function fmtNum(n) {
  try { return Number(n).toLocaleString(_lang); } catch (e) { return Number(n).toLocaleString('en'); }
}

function _pluralCategory(n) {
  try { return new Intl.PluralRules(_lang).select(n); } catch (e) { return new Intl.PluralRules('en').select(n); }
}

function tn(key, n, values, html) {
  var k = key + '_' + _pluralCategory(n);
  if (!hasMessage(k)) k = key + '_other';
  var v = Object.assign({}, values, { count: fmtNum(n) });
  return T(k, v, html);
}

function pickLang(stored, browser, supported) {
  if (stored && supported.indexOf(stored) !== -1) return stored;
  var list = browser || [];
  for (var i = 0; i < list.length; i++) {
    var base = String(list[i]).split('-')[0].toLowerCase();
    if (supported.indexOf(base) !== -1) return base;
  }
  return 'en';
}
