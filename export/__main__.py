"""smart-able export: write each CA's data model XML, Data Model tab JSON
and migration bundle under <work>/export/<ca_id>/.

    uv run python -m export --work work [--site-data work/site/data] [ca_id ...]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from .bundle import write_bundle
from .datamodel_json import build_datamodel_json
from .datamodel_xml import build_configurable_model_xml, build_datamodel_xml, list_configurable_models
from .smartdb import SmartDb, safe_id
from .timezone import resolve_timezone

SKIP_CA_UUID = "0" * 32   # "Cross Conservation Area Analysis" placeholder row

# warning prefix -> section of docs/smart-data-quirks.md (served as quirks.html)
QUIRK = {"timezone": "timezones", "no timezone": "timezones", "track": "tracks", "attachment": "attachments",
         "icon": "data-model-export", "useEarthRanger": "configurable-models", "extraData": "configurable-models",
         "waypoint": "waypoints-and-legs", "SMART version": "backups-versus-exports"}
QUIRK_CONTAINS = {"leg days have no times": "patrol-times"}


def quirk_anchor(msg: str) -> Optional[str]:
    text = msg.split(": ", 1)[-1] if ": " in msg else msg
    for k, a in QUIRK.items():
        if text.startswith(k):
            return a
    for k, a in QUIRK_CONTAINS.items():
        if k in text:
            return a
    return None


def warn(msg: str) -> None:
    anchor = quirk_anchor(msg)
    print(f"warning: {msg}" + (f"  (see quirks.html#{anchor})" if anchor else ""), file=sys.stderr)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="smart-able export", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--work", required=True, type=Path, help="work directory holding parquet/ (and site/)")
    p.add_argument("--site-data", type=Path, help="site/data directory to receive datamodel.json (and ../export/ copies of the XML)")
    p.add_argument("--attachments", type=Path, help="decrypted filestore root (default: <work>/site/attachments)")
    p.add_argument("--source-kind", choices=["backup", "export"], help="what the Parquet came from, for the manifest")
    p.add_argument("--source-file", help="name of the zip or folder the Parquet came from, for the manifest")
    p.add_argument("ca_ids", nargs="*", help="conservation_area.id values to export (default: all)")
    a = p.parse_args(argv)

    parquet = a.work / "parquet"
    if not (parquet / "conservation_area.parquet").exists():
        print(f"error: no {parquet}; run ./smart-able extract first", file=sys.stderr)
        return 1
    db = SmartDb(parquet)
    cas = [c for c in db.cas() if c.uuid != SKIP_CA_UUID]
    if a.ca_ids:
        by_id = {c.id: c for c in cas}
        missing = [i for i in a.ca_ids if i not in by_id]
        if missing:
            print(f"error: unknown conservation area id(s): {', '.join(missing)}; have: {', '.join(sorted(by_id))}", file=sys.stderr)
            return 1
        cas = [by_id[i] for i in a.ca_ids]
    attachments = a.attachments or (a.work / "site" / "attachments")
    merged = []
    for ca in cas:
        out = a.work / "export" / safe_id(ca.id)
        out.mkdir(parents=True, exist_ok=True)
        xml, warnings = build_datamodel_xml(db, ca.uuid)
        (out / "datamodel.xml").write_text(xml, encoding="utf-8")
        for m in list_configurable_models(db, ca.uuid):
            cm_xml, w = build_configurable_model_xml(db, m["uuid"])
            (out / f"configurable_model_{m['uuid']}.xml").write_text(cm_xml, encoding="utf-8")
            warnings += w
        dmj = build_datamodel_json(db, ca)
        (out / "datamodel.json").write_text(json.dumps(dmj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        merged.append(dmj)
        n_patrols = db.rows(f"SELECT count(*) AS n FROM {db.t('patrol')} WHERE ca_uuid = ?", [ca.uuid])[0]["n"]
        summary = (f"  {ca.id}: data model ({len(dmj['categories'])} root categories, {len(dmj['attributes'])} attributes, "
                   f"{len(dmj['configurable_models'])} configurable models)")
        if n_patrols:
            zone, source = resolve_timezone(db, ca, a.site_data)
            manifest = write_bundle(db, ca, out / "bundle", zone, source,
                                    attachments if attachments.exists() else None,
                                    {"kind": a.source_kind, "file": a.source_file})
            warnings += manifest["warnings"]
            c = manifest["counts"]
            tc = manifest["time_coverage"]
            summary += (f"; bundle ({c['patrols']} patrols, {c['waypoints']} waypoints, {c['tracks']} tracks, timezone {zone}; "
                        f"leg-day times from track {tc['track']}, start/end {tc['leg_day_times']}, waypoints {tc['waypoints']}, date only {tc['date_only']})")
            try:
                from .bundle import validate_bundle_dir
                errs = validate_bundle_dir(out / "bundle")
            except ImportError:
                errs = []
                print("  (jsonschema not installed; bundle not validated)")
            for e in errs:
                warn(f"{ca.id}: bundle schema: {e}")
        else:
            summary += "; no patrols, no bundle"
        print(summary)
        shown = 0
        unique = list(dict.fromkeys(warnings))
        n_att = sum(1 for w in unique if w.startswith("attachment "))
        for w in unique:
            if w.startswith("attachment "):
                shown += 1
                if shown == 4 and n_att > 4:
                    warn(f"{ca.id}: ... and {n_att - 3} more attachments are not in the extracted filestore (all listed in bundle/manifest.json)")
                if shown >= 4:
                    continue
            warn(f"{ca.id}: {w}")
        if a.site_data:
            site_export = a.site_data.parent / "export" / safe_id(ca.id)
            site_export.mkdir(parents=True, exist_ok=True)
            for f in out.glob("*.xml"):
                shutil.copyfile(f, site_export / f.name)
    if a.site_data:
        a.site_data.mkdir(parents=True, exist_ok=True)
        (a.site_data / "datamodel.json").write_text(json.dumps(merged, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
