"""The load job: run er-smart-sync's SMART patrol migration for one load,
in plan mode (dry run, writes the plan) or run mode (writes to EarthRanger,
stops where the site needs a human, continues itself past the job's soft
deadline).

Runs as Cloud Run Job smart-able-load (LOAD_ID and MODE in the environment)
or, with BACKEND=local, as a subprocess started by the service. Lives in
the job image's load venv (/opt/load), which has er-smart-sync and the
Google client libraries; it imports only store.py, findings.py and er_site.py
from this checkout.

Usage: load_job.py [load_id] [plan|run]
"""
import json
import logging
import os
import re
import shutil
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import findings as F  # noqa: E402
from er_site import TokenRejected, check_token as default_check_token  # noqa: E402
from store import get_store, now  # noqa: E402

STAGES = ("datamodel", "patrol_datamodel", "preflight", "import")
LOG_TAIL = 60
TAIL_LINE = 500   # characters per tail line: the tail lives on the load doc (Firestore: 1 MiB a document)
FILE_BASED_CA_UUID = "smart-ca-import"
QUIET_LOGGERS = ("httpx", "httpcore", "urllib3")


ca_identifier = F.ca_identifier   # the default event category of a load; findings.py holds it for the service too


class _RunLogHandler(logging.Handler):
    """Sends library log records (er-smart-sync's logging calls) to the run's
    log: log.txt and the tail on the load doc."""

    def __init__(self, runner):
        super().__init__(level=logging.INFO)
        self.runner = runner
        self.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    def emit(self, record):
        try:
            self.runner._log(self.format(record))
        except Exception:  # noqa: BLE001
            self.handleError(record)


def bound_http_timeouts(seconds: float) -> None:
    """Bound every HTTP request this process makes without a timeout of its own.

    erclient sends with requests and no timeout. requests turns that into an
    explicit unlimited timeout, which overrides socket.setdefaulttimeout, so a
    site that accepts a request and never answers would stall the job until
    its hold lapses. Wrapping HTTPAdapter.send covers erclient's session and
    its module-level requests.post for files; callers that pass their own
    timeout (the Google clients) keep it. The socket default stays as a floor
    for anything that bypasses requests."""
    import requests.adapters

    socket.setdefaulttimeout(seconds)
    adapter = requests.adapters.HTTPAdapter
    send = getattr(adapter.send, "_unbounded", adapter.send)   # a second call replaces the wrapper, never stacks one

    def bounded(self, request, *args, timeout=None, **kwargs):
        return send(self, request, *args, timeout=seconds if timeout is None else timeout, **kwargs)

    bounded._unbounded = send
    adapter.send = bounded


class Runner:
    def __init__(self, store, load_id, mode, *, work: Path, migration_factory=None, check_token=None,
                 clock=time.monotonic, env=None):
        self.store, self.load_id, self.mode = store, load_id, mode
        self.work = Path(work)
        self.migration_factory = migration_factory or make_migration
        self.check_token = check_token or default_check_token
        self.clock = clock
        self.env = os.environ if env is None else env
        self.soft_deadline = int(self.env.get("LOAD_SOFT_DEADLINE_SECONDS", 79200))
        self.max_continuations = int(self.env.get("LOAD_MAX_CONTINUATIONS", 10))
        # erclient sets no timeout of its own: without this a hung request stalls the job until its hold lapses
        self.network_timeout = float(self.env.get("LOAD_NETWORK_TIMEOUT_SECONDS", 600))
        self.workers = int(self.env.get("LOAD_WORKERS", 1))   # for experiments: more is slower on today's EarthRanger
        self.log_lines: list = []
        self.load_dir: Path | None = None
        self.dataset_id = None
        self.findings: list = []  # the latest findings, for whichever exit records them
        self.stages: dict = {}    # this execution's rows: status, started_at, finished_at, metrics
        self._log_lock = threading.Lock()
        self.started = self.clock()

    # ---- bookkeeping
    def _update(self, **fields):
        self.store.update_load(self.load_id, **fields)

    def _log(self, line: str):
        with self._log_lock:
            print(line, flush=True)
            self.log_lines.append(line)
            if self.load_dir:
                with open(self.load_dir / "log.txt", "a", encoding="utf-8") as f:
                    f.write(line + "\n")

    def _begin(self, stage: str, **fields):
        """A stage starts: its row, the current stage and the tail so far."""
        self.stages[stage] = {"status": "running", "started_at": now(), "finished_at": None, "metrics": {}}
        self._update(stage=stage, stages=self.stages, log_tail=self._tail(), **fields)

    def _end(self, stage: str, metrics: dict | None = None):
        self.stages[stage].update(status="done", finished_at=now(), metrics=metrics or {})
        self._update(stages=self.stages, log_tail=self._tail())

    def _close_stages(self, status: str):
        """The outcome closes a row still running: stopped, failed, or done."""
        for row in self.stages.values():
            if row["status"] == "running":
                row.update(status={"needs_attention": "stopped", "failed": "failed", "continuing": "running"}.get(status, "done"),
                           finished_at=None if status == "continuing" else now())

    def _tail(self) -> str:
        return "\n".join(F.clip(line, TAIL_LINE) for line in self.log_lines[-LOG_TAIL:])

    def _push_files(self):
        """Everything in the load's folder goes back to the store: ledger,
        checklist, run records, plan, findings, log."""
        if not self.load_dir or not self.load_dir.is_dir():
            return
        for p in sorted(self.load_dir.iterdir()):
            if p.is_file():
                self.store.put_load_file(self.dataset_id, self.load_id, p.name, p)

    def _finish(self, status: str, **fields):
        """Record an outcome. The outcome line is logged first, so it reaches
        log.txt and the tail; the files go before the status, so a status that
        ends the execution never points at files the store does not have yet;
        a failure to push them is logged and does not stop the status."""
        self._log(f"load {self.load_id}: {status}")
        self._close_stages(status)
        fields["stages"] = self.stages
        try:
            self._push_files()
        except Exception as e:  # noqa: BLE001
            self._log(f"pushing the load's files failed: {type(e).__name__}: {e}")
        try:
            self._update(status=status, log_tail=self._tail(), **fields)
        except Exception as e:  # noqa: BLE001  e.g. a document over Firestore's limit: the status must still land
            self._log(f"recording the outcome failed: {type(e).__name__}: {e}; retrying without the tail, plan and progress")
            small = {k: v for k, v in fields.items() if k in ("stage", "continuations", "claimed_at", "stages", "findings")}
            self._update(status=status, error=(fields.get("error") or "The full outcome could not be recorded; see log.txt")[:2000],
                         log_tail=None, plan=None, progress=None, **small)   # the findings are what the operator acts on
            self._log(f"load {self.load_id}: {status} recorded without the tail, plan and progress")
            try:   # so log.txt has both attempts
                self._push_files()
            except Exception as e2:  # noqa: BLE001
                self._log(f"pushing the load's files failed: {type(e2).__name__}: {e2}")

    # ---- the run
    def run(self) -> int:
        load = self.store.get_load(self.load_id)
        if not load:
            print(f"no load {self.load_id}", file=sys.stderr)
            return 2
        self.dataset_id = load["dataset_id"]
        self.stages = {}
        self._update(status="running", error=None, started_at=now(), stages=self.stages, mode=self.mode,
                     stage=None, progress=None)   # nothing of the previous execution shows as this one's
        self.work.mkdir(parents=True, exist_ok=True)
        findings = self.findings
        stage = None
        root = logging.getLogger()
        handler, old_level = None, root.level
        try:
            site = self.store.get_site(load["site_id"])
            dataset = self.store.get(load["dataset_id"])
            if not site or not dataset:
                raise RuntimeError("the site or the dataset of this load no longer exists")
            entry = next((e for e in dataset.get("export") or [] if e.get("dir") == load["ca_id"]), None)
            if not entry:
                raise RuntimeError("the dataset has no migration bundle for this conservation area; re-extract it")
            token = self.store.read_site_token(site["id"])
            self.load_dir = self.store.fetch_load_dir(self.dataset_id, self.load_id, self.work / "load")
            self.load_dir.mkdir(parents=True, exist_ok=True)
            handler = _RunLogHandler(self)
            root.addHandler(handler)
            root.setLevel(logging.INFO)
            for name in QUIET_LOGGERS:  # one INFO line per HTTP request would bury the log
                logging.getLogger(name).setLevel(logging.WARNING)
            self._log(f"{self.mode}: {entry.get('name')} ({entry.get('ca_id')}) -> {site['url']} "
                      f"(continuation {load.get('continuations', 0)})")
            stage = "datamodel"
            self._begin(stage)
            try:
                who = self.check_token(site["url"], token)
            except TokenRejected as e:
                self._finish("needs_attention", stage=stage, findings=[F.token_rejected(str(e))])
                return 0
            self._log(f"token works as {who}")
            export_dir = self.store.fetch_export(self.dataset_id, load["ca_id"], self.work / "export")
            dry = self.mode == "plan"
            bound_http_timeouts(self.network_timeout)
            m = self.migration_factory(workers=self.workers, bundle_dir=Path(export_dir) / "bundle", load_dir=self.load_dir, host=site["url"],
                                       token=token, options=load["options"], dry_run=dry,
                                       ca_identifier=load["options"].get("event_category") or ca_identifier(entry.get("ca_id")))
            del token

            self._log(f"setup took {self.clock() - self.started:.0f} s")
            self.stages[stage]["started_at"] = now()   # the row times the push, not the export download
            self._update(stages=self.stages)
            dm_stats = m.push_datamodel()
            self._log(f"datamodel: {dm_stats}")
            self._end(stage, dm_stats)

            stage = "patrol_datamodel"
            self._begin(stage)
            checklist, pd_stats, pd_changes = m.patrol_datamodel(self.load_dir)
            (self.load_dir / "checklist.json").write_text(json.dumps(checklist, indent=1))
            findings += F.from_checklist(checklist)
            self._log(f"patrol-datamodel: {len(checklist)} checklist item(s)")
            if not dry and F.has_blocking(findings):
                self._finish("needs_attention", stage=stage, findings=findings)
                return 0
            self._end(stage, pd_stats)

            stage = "preflight"
            self._begin(stage, findings=findings)
            report = m.preflight()
            pre = F.from_preflight(report)
            # a plan wrote nothing, so what stages 1-2 create is reported missing; the run preflights again
            findings += F.plan_mode_adjust(pre) if dry else pre
            self._log(f"preflight: {len(report.get('blocking') or [])} blocking, {len(report.get('warnings') or [])} warning(s)")
            if not dry and F.has_blocking(findings):
                self._finish("needs_attention", stage=stage, findings=findings)
                return 0
            patrols = m.patrols()
            self._end(stage, {"blocking": len(report.get("blocking") or []), "warnings": len(report.get("warnings") or []),
                              "patrols": len(patrols)})

            stage = "import"
            self._begin(stage, findings=findings)
            if dry:
                plan = F.build_plan(datamodel_stats=dm_stats, dry_calls=m.dry_calls, pd_changes=pd_changes, pd_stats=pd_stats,
                                    roster_group=load["options"].get("roster_group"), patrols=patrols,
                                    ledger_done=m.ledger_done(), counts=m.counts())
                (self.load_dir / "plan.json").write_text(json.dumps(plan, indent=1))
                (self.load_dir / "findings.json").write_text(json.dumps(findings, indent=1))
                self.stages[stage]["metrics"] = {"planned": len(patrols), "already_done": plan["patrols"]["already_done"]}
                self._finish("planned", stage=stage, findings=findings, plan=plan)
                return 0
            return self._import(m, load, findings, patrols)
        except Exception as e:  # noqa: BLE001
            logging.exception("load %s failed", self.load_id)
            self._log(f"error: {type(e).__name__}: {e}")
            self._finish("failed", stage=stage, error=f"{type(e).__name__}: {e}", findings=self.findings)
            return 0
        finally:
            if handler is not None:
                root.removeHandler(handler)
                root.setLevel(old_level)
            if not self.env.get("JOB_KEEP_WORK"):
                shutil.rmtree(self.work, ignore_errors=True)

    def _import(self, m, load, findings, patrols) -> int:
        counts = m.counts()
        total = len(patrols)
        stop, deleted = threading.Event(), threading.Event()
        last_push = {"t": self.clock(), "n": 0}
        last: dict = {}
        current = {"phase": None, "started_at": None}
        last_live: dict = {}

        def progress(p: dict):
            """Called by er-smart-sync after each patrol. It must never raise:
            an exception here would abort the whole import."""
            try:
                if self.clock() - self.started >= self.soft_deadline:
                    stop.set()
            except Exception as e:  # noqa: BLE001
                self._log(f"progress update failed: {type(e).__name__}: {e}")
            if deleted.is_set():
                return
            try:
                last.update(p)
                phase = p.get("phase")
                if phase != current["phase"]:   # done restarts at 0 with each phase
                    current.update(phase=phase, started_at=now())
                    last_push["n"] = 0
                periodic = p["done"] - last_push["n"] >= 10 or self.clock() - last_push["t"] >= 30
                if periodic and self.store.get_load(self.load_id) is None:
                    # the load (or its dataset) was deleted: stop writing to the site; there is nothing to record to
                    deleted.set()
                    stop.set()
                    self._log("load deleted; stopping")
                    return
                live = {"patrols_total": total, "done": p["done"], "failed": p["failed"],
                        "skipped": p.get("already_imported", 0), "events": counts.get("observations", 0),
                        "track_points": counts.get("track_points", 0)}
                if phase:
                    live.update(phase=phase, phase_started_at=current["started_at"],
                                phase_skipped=p.get("phase_skipped", 0))
                last_live.clear(); last_live.update(live)
                self._update(progress=live,
                             **({"log_tail": self._tail()} if periodic else {}))
                if periodic:
                    self._push_files()  # the ledger above all: what a continuation resumes from
                    last_push.update(t=self.clock(), n=p["done"])
            except Exception as e:  # noqa: BLE001
                self._log(f"progress update failed: {type(e).__name__}: {e}")

        watcher = threading.Thread(target=self._watch_deadline, args=(stop,), daemon=True)
        watcher.start()
        try:
            result = m.import_patrols(progress, stop)
        finally:
            stop.set()
        if deleted.is_set():
            self._log(f"import: {len(result.get('imported') or [])} imported before the load was deleted")
            return 0
        ids = {p["uuid"]: p.get("id") or p["uuid"] for p in patrols}
        failed = result.get("failed") or {}
        for u, err in failed.items():
            self._log(f"failed {ids.get(u, u)}: {err}")
        findings = self.findings = findings + F.from_failed_patrols(failed, ids)
        imported = len(result.get("imported") or [])
        # one write records the outcome, the final counts and the import row (closed by the outcome:
        # done or needs_attention end it, failed patrols are findings, a continuation keeps it running)
        progress = {"patrols_total": total, "done": imported + len(failed), "failed": len(failed),
                    "skipped": last.get("already_imported", 0), "events": counts.get("observations", 0),
                    "track_points": counts.get("track_points", 0)}
        self.stages["import"]["metrics"] = {"imported": imported, "failed": len(failed), "skipped": progress["skipped"]}
        if not result.get("stopped_early"):
            self.stages["import"].update(status="done", finished_at=now())   # it ran to its end; failed patrols are findings
        self._log(f"import: {imported} imported, {len(failed)} failed"
                  + (", stopped at the soft deadline" if result.get("stopped_early") else ""))
        if result.get("stopped_early"):
            n = load.get("continuations", 0) + 1
            if n > self.max_continuations:
                self._finish("failed", stage="import", findings=findings, progress=progress,
                             error=f"the import is not finishing after {self.max_continuations} continuations")
                return 0
            if last_live.get("phase"):
                # still live: keep the phase it stopped in, so the bar does not drop to the whole run's count
                progress = dict(last_live)
            self._finish("continuing", stage="import", findings=findings, progress=progress, continuations=n, claimed_at=now())
            execution = self.store.start_load(self.load_id, "run")
            try:
                self._update(execution=execution)
            except Exception as e:  # noqa: BLE001  the continuation may already be running
                self._log(f"recording the continuation's execution failed: {type(e).__name__}: {e}")
            return 0
        self._finish("needs_attention" if F.has_blocking(findings) else "done", stage="import", findings=findings, progress=progress)
        return 0

    def _watch_deadline(self, stop: threading.Event):
        """Set the stop event at the soft deadline even while a patrol is in
        flight, so a slow one cannot push the run past the hard cap."""
        while not stop.is_set():
            if self.clock() - self.started >= self.soft_deadline:
                stop.set()
                return
            stop.wait(5)


class ErSmartSyncMigration:
    """er-smart-sync, called as a library, for one bundle against one site."""

    def __init__(self, *, bundle_dir, load_dir, host, token, options, dry_run, ca_identifier, er_client=None, workers=1):
        from er_smart_sync.bundle import load_bundle
        from er_smart_sync.defaults import DryRunERClient
        from er_smart_sync.er_patrol_api import ERPatrolAPI
        from er_smart_sync.import_ledger import ImportLedger
        from er_smart_sync.patrol_ids import namespace
        from erclient import ERClient

        self.bundle_dir, self.load_dir, self.options = Path(bundle_dir), Path(load_dir), options
        self.endpoint = f"https://{host}/api/v1.0"
        self.ca_identifier = ca_identifier
        self.language = options.get("language")
        self.cm_uuid = options.get("configurable_model")
        self.bundle = load_bundle(self.bundle_dir, language=self.language)
        client = er_client or ERClient(service_root=self.endpoint, username="", password="", token=token,
                                       client_id="das_web_client")
        self.workers = max(1, int(workers))
        # one client per worker thread; the client already holds the token, so this keeps no more of it
        self.api_factory = (lambda: ERPatrolAPI(ERClient(service_root=self.endpoint, username="", password="", token=token,
                                                         client_id="das_web_client"))) if self.workers > 1 else None
        self.dry = dry_run
        self.client = DryRunERClient(client) if dry_run else client
        self.dry_calls = self.client.calls if dry_run else []
        self.api = ERPatrolAPI(self.client)
        self.ledger = ImportLedger(self.load_dir / "import-ledger.json",
                                   f"{host}|{self.bundle.ca_uuid}", read_only=dry_run)
        self.ns = namespace(self.endpoint, self.bundle.ca_uuid, None)
        self.event_type_prefix = f"{FILE_BASED_CA_UUID}_{self.cm_uuid}" if self.cm_uuid else FILE_BASED_CA_UUID

    def _cm_file(self):
        """The configurable model's XML beside the bundle (named as smart-able's
        export writes it). A configured model without its file is an error:
        push_datamodel_files needs both."""
        if not self.cm_uuid:
            return None
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", self.cm_uuid)
        f = self.bundle_dir.parent / f"configurable_model_{safe}.xml"
        if not f.is_file():
            raise RuntimeError(f"the export has no {f.name} for the chosen configurable model; re-extract the dataset")
        return str(f)

    def push_datamodel(self) -> dict:
        from er_smart_sync.datamodel_push import push_datamodel_files
        return push_datamodel_files(self.client, endpoint=self.endpoint, datamodel_file=str(self.bundle_dir.parent / "datamodel.xml"),
                                    ca_identifier=self.ca_identifier, cm_file=self._cm_file(), cm_uuid=self.cm_uuid,
                                    language=self.language or "en", bundle_dir=str(self.bundle_dir))

    def patrol_datamodel(self, out_dir):
        from er_smart_sync.patrol_datamodel import render_checklist, run_patrol_datamodel, write_run_record
        result = run_patrol_datamodel(self.api, self.client, self.bundle, roster_group=self.options.get("roster_group"),
                                      schema_backup_dir=Path(out_dir))
        (Path(out_dir) / "checklist.md").write_text(render_checklist(result, self.bundle), encoding="utf-8")
        if not self.dry:
            write_run_record(result, self.bundle, self.endpoint, Path(out_dir))
        if result.stats.errors:
            raise RuntimeError("patrol-datamodel: " + "; ".join(str(e) for e in result.stats.errors))
        stats = {k: getattr(result.stats, k) for k in (
            "schema_written", "schema_skipped", "types_created", "types_updated", "types_unchanged",
            "subjects_created", "subjects_updated", "subjects_unchanged", "subjects_deactivated", "subjects_grouped")}
        return result.checklist_dicts(), stats, list(result.stats.changes)

    def preflight(self) -> dict:
        from er_smart_sync.preflight import render_json, run_preflight
        report = run_preflight(self.api, self.bundle, timezone=self.bundle.manifest.timezone.get("name"),
                               event_type_prefix=self.event_type_prefix, event_type_version="v2")
        self._report = report
        return json.loads(render_json(report))

    def patrols(self) -> list:
        return [{"uuid": p["uuid"], "id": p.get("id"), "start_date": p.get("start_date")} for p in self.bundle.patrols]

    def counts(self) -> dict:
        return dict(self.bundle.manifest.counts)

    def ledger_done(self) -> set:
        return {p["uuid"] for p in self.bundle.patrols if {"patrol", "events", "tracks"} <= self.ledger.stages(p["uuid"])}

    def import_patrols(self, progress, stop) -> dict:
        from importlib.metadata import version as pkg_version
        from er_smart_sync import patrol_import
        workers = 1 if self.dry else self.workers   # a plan's writes read in order
        opts = patrol_import.ImportOptions(event_type_prefix=self.event_type_prefix, event_type_version="v2",
                                           timezone=self.bundle.manifest.timezone.get("name"), workers=workers)
        extra = {"api_factory": self.api_factory} if workers > 1 else {}
        result = patrol_import.run_import(self.api, self.bundle, endpoint=self.endpoint, ledger=self.ledger, opts=opts,
                                          ns=self.ns, importer_version=pkg_version("er-smart-sync"),
                                          report=getattr(self, "_report", None), progress=progress, stop=stop, **extra)
        return {"imported": list(result.imported), "failed": dict(result.failed), "stopped_early": result.stopped_early}


def make_migration(**kw):
    return ErSmartSyncMigration(**kw)


def main(load_id: str, mode: str) -> int:
    # Runner.run sends INFO and above to the run's log (stdout, log.txt, the
    # tail); a basicConfig stream handler here would print every line twice.
    work = Path(os.environ.get("JOB_WORK_DIR") or tempfile.mkdtemp(prefix="smart-able-load-"))
    return Runner(get_store(), load_id, mode, work=work / load_id).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.environ["LOAD_ID"],
                  sys.argv[2] if len(sys.argv) > 2 else os.environ.get("MODE", "run")))
