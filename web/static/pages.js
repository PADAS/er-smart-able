// Pure page builders: route parsing, HTML builders, status mapping. No DOM access, so Node can
// test it (tests/js). Top-level names are function declarations or var, never const/let, so the
// test shim can reach them. Loads before app.js.
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
