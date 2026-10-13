"""Read access to the Parquet copy of a SMART database (work/parquet/).

Everything is per conservation area. Labels come from i18n_label, keyed by
the labelled row's UUID; `Labels.get` falls back from the requested language
to the CA default and then to any language, so a missing translation never
turns into a crash.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import duckdb


@dataclass(frozen=True)
class CA:
    uuid: str
    id: str
    name: str
    designation: Optional[str]
    description: Optional[str]
    organization: Optional[str]
    country: Optional[str]
    owner: Optional[str]


@dataclass(frozen=True)
class Language:
    uuid: str
    code: str
    default: bool


class Labels:
    def __init__(self, by_element: dict, default_code: str):
        self._by = by_element      # element_uuid -> {code: value}
        self.default_code = default_code

    def all(self, uuid: str) -> dict:
        return dict(self._by.get(uuid, {}))

    def get(self, uuid: str, code: Optional[str] = None) -> Optional[str]:
        m = self._by.get(uuid)
        if not m:
            return None
        for c in (code, self.default_code):
            if c and c in m:
                return m[c]
        return next(iter(m.values()))


def hyphenate(u: str) -> str:
    u = u.replace("-", "").lower()
    return f"{u[0:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:32]}"


def safe_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


class SmartDb:
    def __init__(self, parquet_dir: Path):
        self.dir = Path(parquet_dir)
        self.con = duckdb.connect()
        self._cache: dict = {}   # (what, ca_uuid) -> result; the Parquet never changes under one SmartDb

    def has(self, table: str) -> bool:
        return (self.dir / f"{table}.parquet").exists()

    def t(self, table: str) -> str:
        """SQL literal for a table's Parquet file, for use in FROM clauses."""
        p = self.dir / f"{table}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"no {p}; run ./smart-able extract first")
        return "'" + str(p).replace("'", "''") + "'"

    def rows(self, sql: str, params: Sequence[Any] = ()) -> list:
        cur = self.con.execute(sql, list(params))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def cas(self) -> list:
        rows = self.rows(f"SELECT uuid, id, name, designation, description, organization, country, owner "
                         f"FROM {self.t('conservation_area')} ORDER BY id")
        return [CA(**r) for r in rows]

    def smart_version(self) -> Optional[str]:
        r = self.rows(f"SELECT max(version) AS v FROM {self.t('db_version')} WHERE plugin_id = 'org.wcs.smart'")
        return r[0]["v"] if r else None

    def languages(self, ca_uuid: str) -> list:
        key = ("languages", ca_uuid)
        if key not in self._cache:
            self._cache[key] = self._languages(ca_uuid)
        return self._cache[key]

    def _languages(self, ca_uuid: str) -> list:
        rows = self.rows(f"SELECT uuid, code, isdefault FROM {self.t('language')} WHERE ca_uuid = ? "
                         f"ORDER BY isdefault DESC, code", [ca_uuid])
        return [Language(r["uuid"], r["code"], bool(r["isdefault"])) for r in rows]

    def labels(self, ca_uuid: str) -> Labels:
        key = ("labels", ca_uuid)
        if key not in self._cache:
            self._cache[key] = self._labels(ca_uuid)
        return self._cache[key]

    def _labels(self, ca_uuid: str) -> Labels:
        langs = self.languages(ca_uuid)
        code_by_uuid = {l.uuid: l.code for l in langs}
        default = next((l.code for l in langs if l.default), langs[0].code if langs else "en")
        by: dict = {}
        if langs:
            marks = ", ".join("?" for _ in langs)
            for r in self.rows(f"SELECT element_uuid, language_uuid, value FROM {self.t('i18n_label')} "
                               f"WHERE language_uuid IN ({marks})", [l.uuid for l in langs]):
                by.setdefault(r["element_uuid"], {})[code_by_uuid[r["language_uuid"]]] = r["value"]
        return Labels(by, default)

    def labelled_elements(self, ca_uuid: str) -> set:
        """UUIDs of this CA's rows that carry i18n labels (for coverage counts)."""
        key = ("labelled", ca_uuid)
        if key not in self._cache:
            self._cache[key] = self._labelled_elements(ca_uuid)
        return self._cache[key]

    def _labelled_elements(self, ca_uuid: str) -> set:
        q = [f"SELECT uuid FROM {self.t('dm_category')} WHERE ca_uuid = ?",
             f"SELECT uuid FROM {self.t('dm_attribute')} WHERE ca_uuid = ?",
             f"SELECT l.uuid FROM {self.t('dm_attribute_list')} l JOIN {self.t('dm_attribute')} a ON a.uuid = l.attribute_uuid WHERE a.ca_uuid = ?",
             f"SELECT n.uuid FROM {self.t('dm_attribute_tree')} n JOIN {self.t('dm_attribute')} a ON a.uuid = n.attribute_uuid WHERE a.ca_uuid = ?",
             f"SELECT uuid FROM {self.t('patrol_transport')} WHERE ca_uuid = ?",
             f"SELECT uuid FROM {self.t('patrol_mandate')} WHERE ca_uuid = ?",
             f"SELECT desc_uuid AS uuid FROM {self.t('station')} WHERE ca_uuid = ?",
             f"SELECT r.uuid FROM {self.t('rank')} r JOIN {self.t('agency')} g ON g.uuid = r.agency_uuid WHERE g.ca_uuid = ?"]
        for opt in ("configurable_model", "employee_team"):
            if self.has(opt):
                q.append(f"SELECT uuid FROM {self.t(opt)} WHERE ca_uuid = ?")
        if self.has("cm_node") and self.has("configurable_model"):
            q.append(f"SELECT n.uuid FROM {self.t('cm_node')} n JOIN {self.t('configurable_model')} m ON m.uuid = n.cm_uuid WHERE m.ca_uuid = ?")
            q.append(f"SELECT c.uuid FROM {self.t('cm_attribute_config')} c JOIN {self.t('configurable_model')} m ON m.uuid = c.cm_uuid WHERE m.ca_uuid = ?")
        out: set = set()
        for sql in q:
            out.update(r["uuid"] for r in self.rows(sql, [ca_uuid]) if r["uuid"])
        return out
