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
    assert "not validated" not in out.out   # jsonschema is a runtime dependency
    assert "1 element(s) have no label in the default language (en)" in out.err


def test_subset_export_keeps_other_cas_in_site_json_and_clears_stale_files(smart_parquet, tmp_path):
    work = smart_parquet.parent
    site = work / "site" / "data"
    site.mkdir(parents=True)
    assert main(["--work", str(work), "--site-data", str(site)]) == 0
    stale = work / "export" / "ALPHA" / "configurable_model_deadbeef.xml"
    stale.write_text("<old/>")
    stale_site = work / "site" / "export" / "ALPHA" / "configurable_model_deadbeef.xml"
    stale_site.write_text("<old/>")
    assert main(["--work", str(work), "--site-data", str(site), "ALPHA"]) == 0
    assert not stale.exists() and not stale_site.exists()
    merged = json.loads((site / "datamodel.json").read_text())
    assert [d["ca_id"] for d in merged] == ["ALPHA", "BETA"]   # BETA kept from disk


def test_bad_timezone_is_a_clean_error_not_a_traceback(smart_parquet, monkeypatch, capsys):
    monkeypatch.setenv("SMART_ABLE_TIMEZONE", "Mars/Olympus")
    rc = main(["--work", str(smart_parquet.parent), "ALPHA"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Mars/Olympus" in err and "Traceback" not in err


def test_unsafe_configurable_model_uuid_is_sanitised(smart_parquet, tmp_path):
    import duckdb
    p = smart_parquet / "configurable_model.parquet"
    con = duckdb.connect()
    con.execute(f"CREATE TABLE x AS SELECT * FROM '{p}'")
    con.execute("UPDATE x SET uuid = '../evil'")
    con.execute(f"COPY x TO '{p}' (FORMAT PARQUET)")
    con.close()
    work = smart_parquet.parent
    assert main(["--work", str(work), "ALPHA"]) == 0
    assert (work / "export" / "ALPHA" / "configurable_model_.._evil.xml").exists()
    assert not (work / "evil.xml").exists() and not (work / "export" / "evil.xml").exists()


def test_cli_selects_ca_and_rejects_unknown(smart_parquet, tmp_path, capsys):
    work = smart_parquet.parent
    assert main(["--work", str(work), "BETA"]) == 0
    assert not (work / "export" / "ALPHA").exists()
    assert main(["--work", str(work), "NOPE"]) == 1
    assert "NOPE" in capsys.readouterr().err
