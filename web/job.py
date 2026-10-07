"""The extraction job: fetch a dataset's uploaded backup, run ./smart-able all
on it, publish the resulting site, and record the outcome on the dataset.

Runs as a Cloud Run Job (DATASET_ID in the environment) or, with
BACKEND=local, as a subprocess started by the service. Everything it needs
is the smart-able checkout it sits in: Java, DuckDB, OpenSSL, unzip and uv
must be on PATH (see web/Dockerfile.job).

Usage: job.py [dataset_id]
"""
import os
import shutil
import subprocess
import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import ROOT, get_store, now  # noqa: E402


def main(dataset_id: str) -> int:
    store = get_store()
    doc = store.get(dataset_id)
    if not doc:
        print(f"no dataset {dataset_id}", file=sys.stderr)
        return 2
    store.update(dataset_id, status="running", error=None, started_at=now())
    work = Path(os.environ.get("JOB_WORK_DIR") or tempfile.mkdtemp(prefix="smart-able-"))
    log_lines = []
    try:
        src = store.fetch_upload(dataset_id, doc["source_name"], work / "in")
        env = {**os.environ, "SMART_ABLE_WORK": str(work / "out")}
        print(f"extracting {src} -> {work / 'out'}", flush=True)
        proc = subprocess.Popen([str(ROOT / "smart-able"), "all", str(src)], cwd=str(ROOT), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            print(line, end="", flush=True)
            log_lines.append(line.rstrip("\n"))
            if len(log_lines) > 400:
                del log_lines[:-400]
        rc = proc.wait()
        tail = "\n".join(l for l in log_lines[-60:] if not l.strip().endswith(" rows"))
        if rc != 0:
            store.update(dataset_id, status="failed", error=f"smart-able exited with {rc}", log_tail=tail)
            return rc
        site = work / "out" / "site"
        meta = json.loads((site / "data" / "meta.json").read_text())
        meta = meta[0] if isinstance(meta, list) and meta else meta  # the SQL writes a one-element array
        if not isinstance(meta, dict):
            raise RuntimeError("site/data/meta.json has an unexpected shape")
        print("publishing site", flush=True)
        store.put_site(dataset_id, site)
        store.update(dataset_id, status="ready", log_tail=tail,
                     cas=[{"id": c.get("id"), "n": c.get("n")} for c in meta.get("cas", [])],
                     db_version=meta.get("db_version"),
                     counts={k: meta.get(k) for k in ("patrols", "waypoints", "observations", "employees")})
        print("done", flush=True)
        return 0
    except Exception as e:  # noqa: BLE001
        store.update(dataset_id, status="failed", error=f"{type(e).__name__}: {e}", log_tail="\n".join(log_lines[-60:]))
        raise
    finally:
        if not os.environ.get("JOB_KEEP_WORK"):
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.environ["DATASET_ID"]))
