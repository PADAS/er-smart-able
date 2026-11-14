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
    assert "localStorage.getItem('theme')" in html and "Back to dataset" in html
    assert "<svg class=\"acorn\"" not in html
