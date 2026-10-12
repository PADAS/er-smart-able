from __future__ import annotations

import json

from export.__main__ import main
from tests.conftest import CM


def test_cli_writes_everything(smart_parquet, tmp_path, capsys):
    work = smart_parquet.parent
    site = work / "site" / "data"
    site.mkdir(parents=True)
    (site / "timezones.json").write_text(json.dumps({"default": "Asia/Manila", "byCa": {"ALPHA": "Asia/Manila"}}))
    rc = main(["--work", str(work), "--site-data", str(site), "--source-kind", "backup", "--source-file", "x.zip"])
    assert rc == 0
    a = work / "export" / "ALPHA"
    assert (a / "datamodel.xml").exists() and (a / f"configurable_model_{CM}.xml").exists() and (a / "datamodel.json").exists()
    assert (a / "bundle" / "manifest.json").exists()
    m = json.loads((a / "bundle" / "manifest.json").read_text())
    assert m["timezone"] == {"name": "Asia/Manila", "source": "inferred"} and m["source"]["file"] == "x.zip"
    b = work / "export" / "BETA"
    assert (b / "datamodel.xml").exists() and not (b / "bundle").exists()   # no patrols, no bundle
    merged = json.loads((site / "datamodel.json").read_text())
    assert [d["ca_id"] for d in merged] == ["ALPHA", "BETA"]
    assert (work / "site" / "export" / "ALPHA" / "datamodel.xml").exists()
    out = capsys.readouterr()
    assert "ALPHA" in out.out and "2 patrols" in out.out
    assert "warning:" in out.err   # the missing attachment
    assert "quirks.html#attachments" in out.err


def test_cli_selects_ca_and_rejects_unknown(smart_parquet, tmp_path, capsys):
    work = smart_parquet.parent
    assert main(["--work", str(work), "BETA"]) == 0
    assert not (work / "export" / "ALPHA").exists()
    assert main(["--work", str(work), "NOPE"]) == 1
    assert "NOPE" in capsys.readouterr().err
