// The reader's language on the getting-started site. A choice made in the header is remembered in
// this browser; before any choice, the browser's own language decides. Only an English page sends
// the reader on (to the same page in their language), so nothing can loop. The switcher is plain
// links and works without this script.
(function () {
  // The language to go to from an English page, or null to stay.
  //   stored: the remembered code, or null; browser: navigator.languages; supported: the site's codes
  function pick(stored, browser, supported) {
    if (stored && supported.indexOf(stored) !== -1) return stored === 'en' ? null : stored;
    var list = browser || [];
    for (var i = 0; i < list.length; i++) {
      var code = String(list[i] || '').split('-')[0].toLowerCase();
      if (supported.indexOf(code) !== -1) return code === 'en' ? null : code;   // the first the site has, English included
    }
    return null;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { pick: pick };
  if (typeof document === 'undefined') return;

  var html = document.documentElement;
  var supported = (html.getAttribute('data-langs') || '').split(' ');
  var stored = null;
  try { stored = window.localStorage.getItem('lang'); } catch (e) { stored = null; }   // storage can be blocked: nothing remembered
  if (html.lang === 'en') {
    var to = pick(stored, navigator.languages || [navigator.language], supported);
    if (to) {
      var page = location.pathname.split('/').pop() || 'index.html';
      location.replace(to + '/' + page + location.search + location.hash);
      return;
    }
  }
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('[data-lang]') : null;
    if (!a) return;
    try { window.localStorage.setItem('lang', a.getAttribute('data-lang')); } catch (err) { /* not remembered; the link still works */ }
  });
})();
