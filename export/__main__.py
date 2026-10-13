"""smart-able export: write each CA's data model XML, Data Model tab JSON
and migration bundle under <work>/export/<ca_id>/.

    uv run python -m export --work work [--site-data work/site/data] [ca_id ...]
    uv run python -m export --work work --site-data work/site/data --merge-only   # just rebuild site/data/datamodel.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfoNotFoundError

from .bundle import validate_bundle_dir, write_bundle
from .datamodel_json import build_datamodel_json
from .datamodel_xml import build_configurable_model_xml, build_datamodel_xml, list_configurable_models
from .smartdb import CA, SmartDb, safe_id
from .timezone import resolve_timezone

SKIP_CA_UUID = "0" * 32   # "Cross Conservation Area Analysis" placeholder row

# warning prefix -> section of docs/smart-data-quirks.md (served as quirks.html)
QUIRK = {"timezone": "timezones", "no timezone": "timezones", "track": "tracks", "attachment": "attachments",
         "icon": "data-model-export", "useEarthRanger": "configurable-models", "extraData": "configurable-models",
         "waypoint": "waypoints-and-legs", "SMART version": "backups-versus-exports"}
QUIRK_CONTAINS = {"leg days have no times": "patrol-times", "placeholder for an unset date": "patrol-times",
                  "no label in the default language": "labels-and-languages"}


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
    print(f"warning: {msg}" + (f"  (see quirks.html#{anchor})" if anchor and "quirks.html#" not in msg else ""), file=sys.stderr)


def merge_site_datamodel(work: Path, site_data: Path) -> List[str]:
    """site/data/datamodel.json = every work/export/<ca>/datamodel.json on disk, by CA id."""
    merged = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((work / "export").glob("*/datamodel.json"))]
    merged.sort(key=lambda d: d.get("ca_id", ""))
    site_data.mkdir(parents=True, exist_ok=True)
    (site_data / "datamodel.json").write_text(json.dumps(merged, ensure_ascii=False) + "\n", encoding="utf-8")
    return [d.get("ca_id", "") for d in merged]


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="smart-able export", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--work", required=True, type=Path, help="work directory holding parquet/ (and site/)")
    p.add_argument("--site-data", type=Path, help="site/data directory to receive datamodel.json (and ../export/ copies of the XML)")
    p.add_argument("--attachments", type=Path, help="decrypted filestore root (default: <work>/site/attachments)")
    p.add_argument("--source-kind", choices=["backup", "export"], help="what the Parquet came from, for the manifest")
    p.add_argument("--source-file", help="name of the zip or folder the Parquet came from, for the manifest")
    p.add_argument("--merge-only", action="store_true", help="only rebuild <site-data>/datamodel.json from the exports on disk")
    p.add_argument("ca_ids", nargs="*", help="conservation_area.id values to export (default: all)")
    a = p.parse_args(argv)

    if a.merge_only:
        if not a.site_data:
            print("error: --merge-only needs --site-data", file=sys.stderr)
            return 1
        merge_site_datamodel(a.work, a.site_data)
        return 0
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
    failed = 0
    for ca in cas:
        try:
            export_ca(db, ca, a, attachments)
        except Exception as e:  # one CA's problem must not take the others (or the browser) down
            failed += 1
            print(f"error: {ca.id}: {type(e).__name__}: {e}", file=sys.stderr)
    if a.site_data:
        merge_site_datamodel(a.work, a.site_data)   # every CA on disk, not just the ones exported this run
    return 1 if failed else 0


def export_ca(db: SmartDb, ca: CA, a, attachments: Path) -> None:
    """Build the CA's outputs in a temporary directory and swap them in only
    when everything succeeded, so a failure leaves the previous export intact."""
    final = a.work / "export" / safe_id(ca.id)
    out = final.with_name(final.name + ".tmp")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    try:
        summary, warnings = _build_ca(db, ca, a, attachments, out)
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise
    shutil.rmtree(final, ignore_errors=True)   # no stale XML or attachments from an earlier backup
    out.rename(final)
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
        shutil.rmtree(site_export, ignore_errors=True)
        site_export.mkdir(parents=True, exist_ok=True)
        for f in final.glob("*.xml"):
            shutil.copyfile(f, site_export / f.name)


def _build_ca(db: SmartDb, ca: CA, a, attachments: Path, out: Path):
    xml, warnings = build_datamodel_xml(db, ca.uuid)
    (out / "datamodel.xml").write_text(xml, encoding="utf-8")
    for m in list_configurable_models(db, ca.uuid):
        cm_xml, w = build_configurable_model_xml(db, m["uuid"])
        (out / f"configurable_model_{safe_id(m['uuid'])}.xml").write_text(cm_xml, encoding="utf-8")
        warnings += w
    dmj = build_datamodel_json(db, ca)
    (out / "datamodel.json").write_text(json.dumps(dmj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    default = next((l for l in dmj["languages"] if l["default"]), None)
    if default and default["missing"]:
        warnings.append(f"{default['missing']} element(s) have no label in the default language ({default['code']}); another language's label is used")
    n_patrols = db.rows(f"SELECT count(*) AS n FROM {db.t('patrol')} WHERE ca_uuid = ?", [ca.uuid])[0]["n"]
    summary = (f"  {ca.id}: data model ({len(dmj['categories'])} root categories, {len(dmj['attributes'])} attributes, "
               f"{len(dmj['configurable_models'])} configurable models)")
    if not n_patrols:
        return summary + "; no patrols, no bundle", warnings
    try:
        zone, source = resolve_timezone(db, ca, a.site_data)
    except ZoneInfoNotFoundError as e:
        raise RuntimeError(f"unknown timezone {os.environ.get('SMART_ABLE_TIMEZONE')!r} in SMART_ABLE_TIMEZONE ({e})") from None
    except (OSError, ValueError) as e:   # e.g. a corrupt site/data/timezones.json
        raise RuntimeError(f"could not resolve the timezone ({type(e).__name__}: {e}); check {a.site_data}/timezones.json or set SMART_ABLE_TIMEZONE") from None
    manifest = write_bundle(db, ca, out / "bundle", zone, source, attachments if attachments.exists() else None,
                            {"kind": a.source_kind, "file": a.source_file})
    warnings += manifest["warnings"]
    c, tc = manifest["counts"], manifest["time_coverage"]
    summary += (f"; bundle ({c['patrols']} patrols, {c['waypoints']} waypoints, {c['tracks']} tracks, timezone {zone}; "
                f"leg-day times from track {tc['track']}, start/end {tc['leg_day_times']}, waypoints {tc['waypoints']}, date only {tc['date_only']})")
    for e in validate_bundle_dir(out / "bundle"):
        warnings.append(f"bundle schema: {e}")
    return summary, warnings


if __name__ == "__main__":
    sys.exit(main())
