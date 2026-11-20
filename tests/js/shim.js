// Loads web/static/i18n.js, then English from locales/en.json, then web/static/nav.js and pages.js into one fresh
// VM context with no DOM (no document, no window), so a stray DOM reference in a page builder throws
// ReferenceError. Returns the context: every top-level function and var in those scripts is a property
// of it. load({ lang, messages }) also sets another language and makes it current.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const STATIC = path.join(__dirname, '..', '..', 'web', 'static');

function load(opts) {
  const ctx = { console };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(STATIC, 'i18n.js'), 'utf8'), ctx, { filename: 'i18n.js' });
  ctx.setMessages('en', JSON.parse(fs.readFileSync(path.join(STATIC, 'locales', 'en.json'), 'utf8')));
  if (opts && opts.lang) { ctx.setMessages(opts.lang, opts.messages || {}); ctx.setLang(opts.lang); }
  vm.runInContext(fs.readFileSync(path.join(STATIC, 'nav.js'), 'utf8'), ctx, { filename: 'nav.js' });
  vm.runInContext(fs.readFileSync(path.join(STATIC, 'pages.js'), 'utf8'), ctx, { filename: 'pages.js' });
  return ctx;
}

module.exports = { load };
