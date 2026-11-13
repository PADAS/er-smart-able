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


def _build(tmp_path: Path, monkeypatch, cas: list[tuple[str, str, str]], rows: dict | None = None) -> Path:
    """Empty Parquet for every table, conservation_area holding `cas` and `rows`
    ({table: [{column: value}]}) in theirs; run both SQL files."""
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
            for row in (rows or {}).get(table, []):
                con.execute(f'INSERT INTO "t_{table}" ({", ".join(row)}) VALUES ({", ".join("?" for _ in row)})', list(row.values()))
            con.execute(f"COPY \"t_{table}\" TO '{parquet / table}.parquet' (FORMAT PARQUET)")
        monkeypatch.chdir(tmp_path)  # the SQL reads parquet/ and writes site/data/ relative to the work dir
        con.execute("\n".join(p.read_text() for p in SQL))
    return tmp_path / "site" / "data"


def test_empty_profiles_tables_give_empty_lists(tmp_path, monkeypatch):
    data = _build(tmp_path, monkeypatch, [("a" * 32, "ALPHA", "Alpha")])
    profiles = json.loads((data / "profiles.json").read_text())
    assert profiles == [{"profiles": [], "types": [], "entities": [], "records": []}]
    meta = json.loads((data / "meta.json").read_text())[0]
    assert [c["id"] for c in meta["cas"]] == ["ALPHA"]


def test_no_conservation_areas_gives_empty_cas(tmp_path, monkeypatch):
    data = _build(tmp_path, monkeypatch, [])
    assert json.loads((data / "meta.json").read_text())[0]["cas"] == []


def test_employees_and_leg_members_carry_the_employee_uuid(tmp_path, monkeypatch):
    """The Rangers tab matches a leg member to an employee by uuid, not by name."""
    ca, emp, pat, leg = "a" * 32, "e" * 32, "f" * 32, "1" * 32
    data = _build(tmp_path, monkeypatch, [(ca, "ALPHA", "Alpha")], rows={
        "employee": [{"uuid": emp, "ca_uuid": ca, "id": "E1", "givenname": "Ana", "familyname": "Cruz"}],
        "patrol": [{"uuid": pat, "ca_uuid": ca, "id": "P-1", "patrol_type": "GROUND", "start_date": "2026-03-04", "end_date": "2026-03-04"}],
        "patrol_leg": [{"uuid": leg, "patrol_uuid": pat, "id": "1", "start_date": "2026-03-04", "end_date": "2026-03-04"}],
        "patrol_leg_members": [{"patrol_leg_uuid": leg, "employee_uuid": emp, "is_leader": True},
                               {"patrol_leg_uuid": leg, "employee_uuid": "d" * 32, "is_leader": False}],   # record deleted in SMART
    })
    employees = json.loads((data / "employees.json").read_text())
    assert employees == [{"u": emp, "ca": "ALPHA", "n": "Ana Cruz", "id": "E1", "agency": "", "rank": "", "sd": None, "ed": None}]
    assert json.loads((data / "meta.json").read_text())[0]["data_format"] == 2   # additive fields: older data still renders
    patrols = json.loads((data / "patrols.json").read_text())
    assert patrols[0]["legs"][0]["members"] == [{"u": emp, "n": "Ana Cruz", "ldr": True}, {"u": "d" * 32, "n": "", "ldr": False}]
