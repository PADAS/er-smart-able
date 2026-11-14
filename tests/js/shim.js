// Loads web/static/pages.js into a fresh VM context with no DOM (no document, no window), so a
// stray DOM reference in a page builder throws ReferenceError. Returns the context: every
// top-level function and var in pages.js is a property of it.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load() {
  const src = fs.readFileSync(path.join(__dirname, '..', '..', 'web', 'static', 'pages.js'), 'utf8');
  const ctx = { console };
  vm.runInNewContext(src, ctx, { filename: 'pages.js' });
  return ctx;
}

module.exports = { load };
