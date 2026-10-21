"""browse/*.sql on a database with empty tables: every top-level list is [], not null.

DuckDB's list() over no rows is NULL, and the page maps over these lists as it
loads, so a null one stops it with "Could not load data". The tables are built
empty from extract/smart_schema.tsv, the way a SMART 7.5.4 database has them.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
SQL = [ROOT / "browse" / "build_browser_data.sql", ROOT / "browse" / "build_profiles.sql"]


def _schema() -> dict[str, list[tuple[str, str]]]:
    """{table: [(column, DuckDB type)]} for the 7.5.4 columns (no version in the fourth field)."""
    tables: dict[str, list[tuple[str, str]]] = {}
    for line in (ROOT / "extract" / "smart_schema.tsv").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) > 3 and f[3]:
            continue
        tables.setdefault(f[0], []).append((f[1], f[2]))
    return tables


def _build(tmp_path: Path, monkeypatch, cas: list[tuple[str, str, str]]) -> Path:
    """Empty Parquet for every table, conservation_area holding `cas`; run both SQL files."""
    parquet = tmp_path / "parquet"
    parquet.mkdir()
    (tmp_path / "site" / "data").mkdir(parents=True)
    with duckdb.connect() as con:
        try:
            con.execute("INSTALL spatial; LOAD spatial;")
        except duckdb.Error as e:  # offline with no cached extension
            pytest.skip(f"DuckDB spatial extension unavailable: {e}")
        for table, cols in _schema().items():
            columns = ", ".join(f'"{c}" {t}' for c, t in cols)
            con.execute(f'CREATE TABLE "t_{table}" ({columns})')
            if table == "conservation_area":
                for u, i, n in cas:
                    con.execute('INSERT INTO "t_conservation_area" (uuid, id, name) VALUES (?, ?, ?)', [u, i, n])
            con.execute(f"COPY \"t_{table}\" TO '{parquet / table}.parquet' (FORMAT PARQUET)")
        monkeypatch.chdir(tmp_path)  # the SQL reads parquet/ and writes site/data/ relative to the work dir
        con.execute("\n".join(p.read_text() for p in SQL))
    return tmp_path / "site" / "data"


def test_empty_profiles_tables_give_empty_lists(tmp_path, monkeypatch):
    data = _build(tmp_path, monkeypatch, [("a" * 32, "ALPHA", "Alpha")])
    profiles = json.loads((data / "profiles.json").read_text())
    assert len(profiles) == 1 and profiles[0]  # one row, with every top-level list in it
    assert {k: v for k, v in profiles[0].items() if v != []} == {}
    meta = json.loads((data / "meta.json").read_text())[0]
    assert [c["id"] for c in meta["cas"]] == ["ALPHA"]


def test_no_conservation_areas_gives_empty_cas(tmp_path, monkeypatch):
    data = _build(tmp_path, monkeypatch, [])
    assert json.loads((data / "meta.json").read_text())[0]["cas"] == []
