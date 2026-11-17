// The reader's language on the getting-started site. A choice made in the header is remembered in
// this browser; before any choice, the browser's own language decides. Only an English page sends
// the reader on (to the same page in their language), so nothing can loop. The switcher is plain
// links and works without this script.
//
// A link that chooses English ends in ?lang=en. That is how the choice holds when nothing can be
// remembered (storage blocked) and for a link that is followed before any click is stored: the
// English page sees it and stays. With nothing remembered it also passes the mark on to the links
// of the page, so the reader stays in English as they move through it.
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
  // The language a link asked for: the value of lang in '?lang=en', if the site has it.
  function asked(search, supported) {
    var m = /[?&]lang=([a-z]{2,3})(?:&|$)/.exec(search || '');
    return m && supported.indexOf(m[1]) !== -1 ? m[1] : null;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { pick: pick, asked: asked };
  if (typeof document === 'undefined') return;

  var html = document.documentElement;
  var supported = (html.getAttribute('data-langs') || '').split(' ');
  var wanted = asked(location.search, supported);
  var stored = null, remembers = true;
  try {
    if (wanted) window.localStorage.setItem('lang', wanted);
    stored = window.localStorage.getItem('lang');
  } catch (e) { stored = null; remembers = false; }   // storage can be blocked: nothing remembered
  if (html.lang === 'en') {
    var to = pick(wanted || stored, navigator.languages || [navigator.language], supported);
    if (to) {
      var page = location.pathname.split('/').pop() || 'index.html';
      location.replace(to + '/' + page + location.hash);
      return;
    }
  }
  var carry = html.lang === 'en' && wanted === 'en' && !remembers;   // English was asked for and cannot be remembered
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    var lang = a.getAttribute('data-lang'), href = a.getAttribute('href');
    if (lang) {
      try { window.localStorage.setItem('lang', lang); } catch (err) { /* not remembered; the link still works */ }
    } else if (carry && /^[\w-]+\.html(#.*)?$/.test(href)) {   // another page of the English site
      a.setAttribute('href', href.replace(/(#.*)?$/, '?lang=en$1'));
    }
  });
})();
