# tests/test_viewer_page.py
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def test_the_viewer_shares_the_apps_tokens_header_and_theme_key():
    html = (ROOT / "browse" / "index.html").read_text()
    tokens = (ROOT / "web" / "static" / "er-tokens.css").read_text()
    for name in ("--er-ui-text-primary-text", "--er-ui-cta-primary", "--er-ui-background-secondary-background", "--er-ui-status-running"):
        light = re.search(name + r": (#[0-9a-f]{6});", tokens).group(1)
        assert f"{name}: {light};" in html, name
    assert "keep the two in step" in html
    assert "SMART migration" in html and "fonts.googleapis.com/css2?family=Roboto" not in html
    assert "localStorage.getItem('theme')" in html
    assert "<svg class=\"acorn\"" not in html


def test_the_viewer_carries_the_apps_sidebar_verbatim():
    html = (ROOT / "browse" / "index.html").read_text()
    for name in ("nav.js", "nav.css"):
        src = (ROOT / "web" / "static" / name).read_text()
        body = html.split(f"/* {name}:begin */", 1)[1].split(f"/* {name}:end */", 1)[0]
        assert body.strip() == src.strip(), f"{name}: run scripts/sync_nav.py"


def test_the_sync_script_agrees():
    import subprocess, sys
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_nav.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_viewer_has_the_apps_band_and_no_list_of_its_own():
    html = (ROOT / "browse" / "index.html").read_text()
    assert 'id="sidenav"' not in html and "Back to dataset" not in html and 'id="navToggle"' not in html
    # the band names the app and its version and holds nothing to do; the lockup is the page's own drawing, for a folder
    assert '<header id="band"><a id="home"></a><span id="appName">SMART migration</span><span id="version"></span></header>' in html
    assert "$('#lockupMark').content.cloneNode(true)" in html and "if (HOSTED) { home.setAttribute('href', '/#/');" in html
    assert "--band-h: 48px" in html and "#rail .rail-brand, #rail .rail-app { display: none; }" in html
    assert '<nav id="rail"' in html and "renderRail(" in html
    assert "localStorage.getItem('sidenav')" in html, "the fold state is the app's, applied before first paint"
    assert "doc: 'browser'" in html and "'data:' + TAB" in html
    assert 'id="caSel"' in html and "railFilter" in html, "the conservation area filter sits in the sidebar's slot"


def test_from_a_folder_the_viewer_asks_no_server():
    html = (ROOT / "browse" / "index.html").read_text()
    # everything asked of the app is asked in one function, which leaves at once when the page is not under /d/{id}/
    start = html.index("async function hostedRail(lang, refocus) {")
    body = html[start:html.index("\n}\n", start)]
    assert body.split("\n")[1].strip() == "if (!HOSTED) return;"
    outside = html.split("/* nav.js:end */", 1)[1].replace(body, "")
    assert not re.search(r"\b(?:fetch|ask)\(\s*['\"`]/", outside), "a request to the app outside hostedRail"
    # the one caller outside it (sign out) goes through fetchApp, which refuses until hostedRail has run
    assert "let fetchApp = () => Promise.reject(new Error('no server'));" in outside
    assert re.findall(r"fetchApp\(\s*'(/[^']*)'", outside) == ["/api/signout"]
    assert "hosted: !!HOSTED" in html and "const HOSTED = location.pathname.match(/^\\/d\\/([A-Za-z0-9]+)\\//);" in html


def test_the_first_view_is_named_summary_and_keeps_its_address():
    html = (ROOT / "browse" / "index.html").read_text()
    assert "const TABS = ['overview'," in html
    assert "SMART database" in html and "$('#dbver').textContent" not in html
