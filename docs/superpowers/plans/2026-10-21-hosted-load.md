# Hosted Load Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an allowed user of the hosted smart-able app register an EarthRanger site and run the SMART patrol migration of a ready dataset into it, with a plan to confirm first, findings that stop and report where the site needs a human, progress, and automatic continuation past the Cloud Run task limit.

**Architecture:** A second Cloud Run Job (`smart-able-load`) built from the extraction image plus its own virtualenv holding er-smart-sync, driven by `web/load_job.py`, which calls er-smart-sync as a library. The extraction job starts publishing the migration bundle. Two new Firestore collections, `sites` (token in Secret Manager) and `loads`, mirrored by the local backend. New API routes and a load page in the existing single-page app.

**Tech Stack:** Python 3.12, FastAPI, Firestore, GCS, Secret Manager, Cloud Run Jobs, er-smart-sync (pydantic 1.x, in its own venv), vanilla JS, pytest, OpenTofu.

**Spec:** `docs/superpowers/specs/2026-10-21-hosted-load-design.md`

## Global Constraints

- Two repositories: Part A changes `~/padas/earthranger-smart-utils` (er-smart-sync, pydantic 1.x, `uv run pytest`); Part B changes this repo (`/Users/chrisdo/padas/er-smart-able`, pydantic 2, `uv run pytest`). Commit in whichever repo the task names.
- er-smart-sync and the web service never share a virtualenv. `web/load_job.py` imports only `store.py` and er-smart-sync.
- The site token is never written to Firestore, to a log line, to `log_tail`, or to any file under `web-data/` other than `web-data/secrets/`.
- Status vocabulary for a load, exactly: `planning`, `planned`, `queued`, `running`, `continuing`, `needs_attention`, `done`, `failed`. Stage vocabulary: `datamodel`, `patrol_datamodel`, `preflight`, `import`.
- A finding is `{stage, code, severity, title, detail, fix, affected: {count, patrols}}`, severity in `blocking`, `warning`, `info`; `affected.patrols` holds at most 50 uuids.
- Defaults: `LOAD_SOFT_DEADLINE_SECONDS=79200`, `LOAD_STALE_AFTER_SECONDS=90000`, `LOAD_MAX_CONTINUATIONS=10`, `LOAD_JOB=smart-able-load`. Plan lists are capped at 200 entries with a `more` count.
- Secret names are `smart-able-site-<site id>`. Site `url` is stored as a bare host.
- Follow the file style of `web/app.py` and `web/store.py`: module docstrings that list routes, one-line comments explaining why, no type-only refactors.

## Review Focus

1. A site URL pasted with a scheme, path or trailing slash (`https://phinney.staging.pamdas.org/api/v1.0/`) must normalize to the bare host, and two registrations of the same host by one user must be allowed (different tokens). Test in Task B3.
2. Creating a load for a conservation area whose bundle has zero patrols, or whose `ca_id` is not in `export`, must be refused with 400 before any execution starts. Test in Task B5.
3. The load job must never leave a load in `running` when it exits by exception from the plan builder or the token fetch: every exit path writes `failed` or `needs_attention`. Test in Task B7.
4. A `needs_attention` load whose site was deleted: `run` and `replan` return 409 and the load doc is unchanged. Test in Task B5.
5. Deleting a dataset with an active load: the load's folder and doc go with it and no orphan execution can claim it later (the job finds no doc and exits 2). Test in Task B4 and B7.

---

# Part A: er-smart-sync additions

Repository: `~/padas/earthranger-smart-utils`. Run tests with `uv run pytest`. These land as one release (`v0.9.0`) that Part B pins.

### Task A1: Checklist items as data

**Files:**
- Modify: `src/er_smart_sync/patrol_datamodel.py:72-78` (ChecklistItem)
- Test: `tests/test_patrol_datamodel.py`

**Interfaces:**
- Produces: `ChecklistItem.to_dict() -> dict` with keys `code`, `title`, `steps` (list of str); `PatrolDatamodelResult.checklist_dicts() -> list[dict]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_patrol_datamodel.py`:

```python
def test_checklist_items_render_as_dicts():
    from er_smart_sync.patrol_datamodel import ChecklistItem, PatrolDatamodelResult, PatrolDatamodelStats

    item = ChecklistItem("team", "Create the patrol team Alpha", ["Django admin > Teams.", "Re-run."])
    assert item.to_dict() == {"code": "team", "title": "Create the patrol team Alpha",
                              "steps": ["Django admin > Teams.", "Re-run."]}
    result = PatrolDatamodelResult(stats=PatrolDatamodelStats(), checklist=[item], subject_ids={})
    assert result.checklist_dicts() == [item.to_dict()]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_patrol_datamodel.py::test_checklist_items_render_as_dicts -v`
Expected: FAIL with `AttributeError: 'ChecklistItem' object has no attribute 'to_dict'`

- [ ] **Step 3: Implement**

In `src/er_smart_sync/patrol_datamodel.py` replace the two dataclasses:

```python
@dataclass
class ChecklistItem:
    code: str
    title: str
    steps: list

    def to_dict(self) -> dict:
        return {"code": self.code, "title": self.title, "steps": list(self.steps)}


@dataclass
class PatrolDatamodelResult:
    stats: PatrolDatamodelStats
    checklist: list
    subject_ids: dict

    def checklist_dicts(self) -> list:
        """The checklist as data, for callers that render it themselves."""
        return [c.to_dict() for c in self.checklist]
```

- [ ] **Step 4: Run the test file**

Run: `uv run pytest tests/test_patrol_datamodel.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/er_smart_sync/patrol_datamodel.py tests/test_patrol_datamodel.py
git commit -m "patrol-datamodel: expose the checklist as dicts"
```

### Task A2: Progress callback and stop event on run_import

**Files:**
- Modify: `src/er_smart_sync/patrol_import.py:367-476` (run_import) and `cli.py:1099-1205` (unchanged behaviour, no edit needed)
- Test: `tests/test_patrol_import.py`

**Interfaces:**
- Produces: `run_import(..., progress: Callable[[dict], None] | None = None, stop: threading.Event | None = None)`. `progress` is called after every patrol with `{"total": int, "done": int, "failed": int, "already_imported": int}` where `total` is the number of selected patrols and `done` counts patrols finished this run (imported or already imported). When `stop.is_set()` before a patrol starts, that patrol and the rest are not started; `ImportResult.stopped_early: bool` is True and they are absent from `imported`, `failed` and `skipped`.

- [ ] **Step 1: Write the failing tests**

Look at the top of `tests/test_patrol_import.py` for the existing fixtures that build a bundle and a fake API (`FakeAPI` or similar) and a `_run` helper; reuse them. Append:

```python
def test_progress_is_reported_per_patrol(bundle_and_api):
    bundle, api = bundle_and_api
    seen = []
    result = _run(api, bundle, progress=seen.append)
    assert len(seen) == len(result.imported) + len(result.failed)
    assert seen[-1]["done"] == len(seen) and seen[-1]["total"] == len(seen)
    assert set(seen[-1]) == {"total", "done", "failed", "already_imported"}


def test_a_set_stop_event_starts_no_more_patrols(bundle_and_api):
    import threading

    bundle, api = bundle_and_api
    stop = threading.Event()

    def after_first(p):
        stop.set()

    result = _run(api, bundle, progress=after_first, stop=stop)
    assert result.stopped_early is True
    assert len(result.imported) + len(result.failed) == 1
```

If the file has no `bundle_and_api` fixture and `_run` helper, write them above the tests using the same construction the file's first test uses for `run_import` (api, bundle, `endpoint="https://x.pamdas.org"`, a fresh `ImportLedger(tmp_path / "l.json", "x")`, `ImportOptions()`, `ns=namespace(...)`, `importer_version="test"`), passing `**kwargs` through to `run_import`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_patrol_import.py -k "progress or stop_event" -v`
Expected: FAIL with `TypeError: run_import() got an unexpected keyword argument 'progress'`

- [ ] **Step 3: Implement**

In `patrol_import.py`:

```python
@dataclass
class ImportResult:
    imported: list = field(default_factory=list)
    skipped: dict = field(default_factory=dict)
    failed: dict = field(default_factory=dict)
    report: PreflightReport | None = None
    stopped: bool = False
    stopped_early: bool = False  # a stop event ended the run before every patrol was tried
    counts: Counter = field(default_factory=Counter)
```

Change the signature and the loop:

```python
def run_import(
    api,
    bundle: Bundle,
    *,
    endpoint: str,
    ledger: ImportLedger,
    opts: ImportOptions,
    ns,
    importer_version: str,
    report: PreflightReport | None = None,
    api_factory: Callable[[], Any] | None = None,
    progress: Callable[[dict], None] | None = None,
    stop: threading.Event | None = None,
) -> ImportResult:
```

Inside, after `selected` is built, keep a tally and report it from `record`:

```python
    tally = {"total": len(selected), "done": 0, "failed": 0, "already_imported": 0}

    def record(outcome):
        uuid, counts, error = outcome
        result.counts.update(counts)
        if error:
            result.failed[uuid] = error
            tally["failed"] += 1
        else:
            result.imported.append(uuid)
        tally["done"] += 1
        tally["already_imported"] += counts.get("already_imported", 0)
        if progress:
            progress(dict(tally))
```

In the single-worker branch:

```python
        if workers == 1 or api_factory is None:
            for p in selected:
                if stop is not None and stop.is_set():
                    result.stopped_early = True
                    break
                record(_import_one(api, bundle, p, **per_patrol))
```

In the pool branch, check the event inside `worker` before `_import_one` and return a sentinel the loop ignores:

```python
            def worker(p):
                if stop is not None and stop.is_set():
                    return None
                ...
            for outcome in pool.map(worker, selected):
                if outcome is None:
                    result.stopped_early = True
                    continue
                record(outcome)
```

- [ ] **Step 4: Run the test file**

Run: `uv run pytest tests/test_patrol_import.py -v`
Expected: all PASS

- [ ] **Step 5: Document and commit**

Add to `docs/cli-reference/import-patrols.md` under "Identity and re-runs" one sentence: "Library callers can pass `progress=` (called per patrol with running totals) and `stop=` (a `threading.Event`; once set, no further patrol starts and `ImportResult.stopped_early` is true)." Add a changelog line under the unreleased heading of `docs/changelog.md`.

```bash
git add src/er_smart_sync/patrol_import.py tests/test_patrol_import.py docs/cli-reference/import-patrols.md docs/changelog.md
git commit -m "import-patrols: progress callback and stop event for library callers"
```

### Task A3: The from-file datamodel push as a function

**Files:**
- Create: `src/er_smart_sync/datamodel_push.py`
- Modify: `src/er_smart_sync/cli.py:458-549` (the `if datamodel_file:` branch calls the new function)
- Test: `tests/test_datamodel_push.py`

**Interfaces:**
- Produces:

```python
def push_datamodel_files(
    er_client,                      # an ERClient, or DryRunERClient(ERClient)
    *,
    endpoint: str,
    datamodel_file: str,
    ca_identifier: str,
    cm_file: str | None = None,
    cm_uuid: str | None = None,
    include_base_datamodel: bool = False,
    language: str = "en",
    bundle_dir: str | None = None,
    event_type_version: str = "v2",
    mode: str = "both",
) -> dict:   # the synchronizer's datamodel_stats
```

It builds a `SyncConfig` with an empty `SmartConnectConfig` (endpoint, login, password all `""`, `use_language_code=language`) and an `EarthRangerConfig(id="library", endpoint=endpoint, token="unused", event_type_version=...)`, constructs `ERSmartSynchronizer(config=config)`, replaces `sync.er_client` with the given client, sets `sync.sync_mode`, `sync.observed_categories` from the bundle when given, loads the XML exactly as `cli.datamodel` does, and makes the same one or two `push_smart_ca_datamodel_to_earthranger` calls. It raises `ValueError` for the same invalid combinations the CLI rejects with `UsageError`.

- [ ] **Step 1: Write the failing test**

`tests/test_datamodel_push.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from er_smart_sync.defaults import DryRunERClient

FIXTURE = Path(__file__).parent / "fixtures" / "smart_demo_bundle"


class _Reads:
    """The reads the synchronizer makes before deciding what to write."""

    def get_event_categories(self, *a, **k):
        return []

    def get_event_types(self, *a, **k):
        return []

    def get_event_schema(self, *a, **k):
        return {}

    def get_objects_multithreaded(self, *a, **k):
        return []

    def __getattr__(self, name):
        if name.startswith("get_"):
            return lambda *a, **k: []
        raise AttributeError(name)


def test_push_from_file_makes_the_same_writes_as_the_cli(tmp_path):
    from er_smart_sync.datamodel_push import push_datamodel_files

    xml = next(FIXTURE.parent.glob("**/datamodel.xml"), None)
    if xml is None:
        pytest.skip("no datamodel.xml fixture")
    client = DryRunERClient(_Reads())
    stats = push_datamodel_files(client, endpoint="https://x.pamdas.org", datamodel_file=str(xml),
                                 ca_identifier="smart-test")
    names = {name for name, _, _ in client.calls}
    assert "post_event_category" in names and "post_event_type" in names
    assert stats["event_types_created"] == sum(1 for n, _, _ in client.calls if n == "post_event_type")


def test_cm_without_datamodel_is_refused():
    from er_smart_sync.datamodel_push import push_datamodel_files

    with pytest.raises(ValueError):
        push_datamodel_files(DryRunERClient(_Reads()), endpoint="https://x.pamdas.org",
                             datamodel_file="dm.xml", ca_identifier="x", cm_uuid="not-a-uuid", cm_file=None)
```

Check `tests/fixtures/` for an existing `datamodel.xml` used by `test_smart_to_er_v2.py` or `test_cli.py` and point `xml` at it directly instead of the glob.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_datamodel_push.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'er_smart_sync.datamodel_push'`

- [ ] **Step 3: Implement**

`src/er_smart_sync/datamodel_push.py`:

```python
"""Push a SMART data model (and a configurable model) from XML files into
EarthRanger, as `er-smart-sync datamodel --from-file` does, for callers that
are not the CLI."""

from __future__ import annotations

import uuid as _uuid

from .bundle import BundleError, load_bundle
from .config import EarthRangerConfig, SmartConnectConfig, SyncConfig
from .synchronizer import ERSmartSynchronizer

FILE_BASED_CA_UUID = "smart-ca-import"
DEFAULT_FILE_CM_UUID = "00000000-0000-0000-0000-000000000000"


def push_datamodel_files(er_client, *, endpoint, datamodel_file, ca_identifier, cm_file=None, cm_uuid=None,
                         include_base_datamodel=False, language="en", bundle_dir=None, event_type_version="v2",
                         mode="both") -> dict:
    if cm_uuid and not cm_file:
        raise ValueError("cm_uuid needs cm_file")
    if include_base_datamodel and not cm_file:
        raise ValueError("include_base_datamodel needs cm_file")
    if cm_file:
        try:
            _uuid.UUID(cm_uuid or DEFAULT_FILE_CM_UUID)
        except ValueError:
            raise ValueError(f"cm_uuid {cm_uuid!r} is not a UUID") from None
    observed: set = set()
    if bundle_dir:
        if event_type_version != "v2":
            raise ValueError("bundle_dir needs v2 event types")
        try:
            observed = load_bundle(bundle_dir).observed_category_hkeys()
        except BundleError as e:
            raise ValueError(f"bundle: {e}") from None

    from smartconnect import ConfigurableDataModel, SmartClient

    sclient = SmartClient(api="https://tempuri.org/", username="", password="", use_language_code=language)
    dm = sclient.load_datamodel(filename=datamodel_file)
    cm = None
    if cm_file:
        cm = ConfigurableDataModel(use_language_code=language, cm_uuid=cm_uuid or DEFAULT_FILE_CM_UUID)
        with open(cm_file) as f:
            cm.load(f.read())

    config = SyncConfig(
        smart=SmartConnectConfig(endpoint="", login="", password="", use_language_code=language),
        earthranger=EarthRangerConfig(id="library", endpoint=endpoint, token="unused",
                                      event_type_version=event_type_version),
    )
    sync = ERSmartSynchronizer(config=config)
    sync.er_client = er_client
    sync.sync_mode = mode
    sync.observed_categories = observed
    if cm and include_base_datamodel:
        sync.push_smart_ca_datamodel_to_earthranger(dm=dm, smart_ca_uuid=FILE_BASED_CA_UUID,
                                                    ca_identifier=ca_identifier, cm=None)
    sync.push_smart_ca_datamodel_to_earthranger(dm=dm, smart_ca_uuid=FILE_BASED_CA_UUID,
                                                ca_identifier=ca_identifier, cm=cm)
    return dict(sync.datamodel_stats)
```

Check `ERSmartSynchronizer.__init__` (synchronizer.py around line 200) for what it builds from `config` on construction (an ERClient from the token, a publisher). If constructing with `token="unused"` makes a network call, pass a constructor keyword that skips it, or construct the client lazily; the existing `_make_synchronizer` in `cli.py` shows the pattern (it replaces `sync.er_client` after construction, so construction must already be network-free).

Then in `cli.py`'s `datamodel` command, replace the body of `if datamodel_file:` (from `from smartconnect import ...` through the second `push_smart_ca_datamodel_to_earthranger` call) with:

```python
        sync = _make_synchronizer(config, ctx=ctx)
        from .datamodel_push import push_datamodel_files

        try:
            sync.datamodel_stats = push_datamodel_files(
                sync.er_client, endpoint=config.earthranger.endpoint, datamodel_file=datamodel_file,
                ca_identifier=ca_identifier, cm_file=cm_file, cm_uuid=cm_uuid,
                include_base_datamodel=include_base_datamodel, language=config.smart.use_language_code,
                bundle_dir=bundle_dir, event_type_version=config.earthranger.event_type_version, mode=mode,
            )
        except ValueError as e:
            raise click.UsageError(str(e)) from None
```

and delete the now-duplicated validation of `cm_uuid`, `include_base_datamodel` and `bundle_dir` above it, keeping the `--cm-from-file requires --from-file` and `--ca-identifier is required` checks (those are CLI-only).

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q`
Expected: all PASS, including `tests/test_cli.py`'s datamodel from-file tests.

- [ ] **Step 5: Commit**

```bash
git add src/er_smart_sync/datamodel_push.py src/er_smart_sync/cli.py tests/test_datamodel_push.py
git commit -m "datamodel: from-file push callable as a function"
```

### Task A4: Release

**Files:**
- Modify: `docs/changelog.md`

- [ ] **Step 1: Changelog**

Under a new `## 0.9.0` heading list: checklist as dicts, `progress`/`stop` on `run_import`, `datamodel_push.push_datamodel_files`.

- [ ] **Step 2: Run the suite, tag, push**

```bash
uv run pytest -q
git add docs/changelog.md && git commit -m "Release 0.9.0"
git tag -a v0.9.0 -m "0.9.0: library hooks for hosted loads"
git push origin main v0.9.0
```

Confirm the package is installable by tag: `uv pip install --dry-run "er-smart-sync @ git+https://github.com/PADAS/earthranger-smart-utils@v0.9.0"`. Part B pins this reference.

---

# Part B: smart-able

Repository: `/Users/chrisdo/padas/er-smart-able`. Run tests with `uv run pytest`. Work on a branch `feat/hosted-load`.

## File structure

| File | Responsibility |
| --- | --- |
| `web/store.py` | existing; gains sites, loads, secrets, load claims, `export/` and `loads/` storage, `start_load` on both backends |
| `web/findings.py` | new, pure: finding dicts from checklist items, preflight findings, failed patrols, token rejection; the plan dict from dry-run calls and stats |
| `web/load_job.py` | new: the job entrypoint, stages, stop rule, continuation |
| `web/er_site.py` | new: URL normalization and the token check against an ER site (service side, uses `httpx`) |
| `web/app.py` | existing; gains the sites and loads routes |
| `web/job.py` | existing; publishes `export/` and writes `export` on the dataset |
| `web/static/app.js`, `web/templates/index.html`, `web/static/app.css` | sites panel, load form, loads on cards, load page |
| `web/Dockerfile.job`, `.github/workflows/deploy.yml`, `web/infra/main.tf`, `web/DEPLOY.md` | the load job, Secret Manager |
| `tests/test_web_sites.py`, `tests/test_web_loads.py`, `tests/test_findings.py`, `tests/test_load_job.py`, `tests/test_web_extract.py` | tests |

### Task B1: The extraction job publishes the bundle and describes it

**Files:**
- Modify: `web/store.py` (LocalStore and GcpStore: `put_export`, `fetch_export`, `delete_storage` already covers it by prefix)
- Modify: `web/job.py:44-55`
- Test: `tests/test_web_extract.py`

**Interfaces:**
- Produces: `store.put_export(id, export_dir: Path)` copies `work/export/` (every `<ca>/` with its bundle, XML and `datamodel.json`, not `.export-staging`) to `datasets/<id>/export/`, replacing what was there. `store.fetch_export(id, ca_dir: str, dest: Path) -> Path` fetches one conservation area's folder and returns the local path of it. `store.export_exists(id, ca_dir) -> bool`. The dataset doc gains `export: list[dict]` built by `describe_export(export_dir) -> list` in `job.py`, one entry per `<ca>/bundle/manifest.json`: `{"ca_id", "dir", "name", "languages": [codes], "default_language", "configurable_models": [{"uuid", "label"}], "patrols", "timezone"}`. `dir` is the folder name (`ca_dir_name` in `export/__main__.py`), which is what the API uses as `ca_id`; `ca_id` is the SMART id for display. `configurable_models` comes from `<ca>/datamodel.json`'s `configurable_models` list (`uuid`, `label` fields; check its shape in `export/datamodel_json.py`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_extract.py`:

```python
def _fake_export(root: Path, ca="ALPHA"):
    ca_dir = root / ca
    (ca_dir / "bundle").mkdir(parents=True)
    (ca_dir / "bundle" / "manifest.json").write_text(json.dumps({
        "conservation_area": {"id": "050500", "name": "Albay", "uuid": "0c7cbb41-1a60-485d-8513-8255206466a4"},
        "timezone": {"name": "Asia/Manila", "source": "inferred"}, "default_language": "en",
        "languages": [{"code": "en", "default": True}], "counts": {"patrols": 3}}))
    (ca_dir / "datamodel.json").write_text(json.dumps({"configurable_models": [{"uuid": "abc", "label": "Mobile"}]}))
    (ca_dir / "datamodel.xml").write_text("<DataModel/>")
    (root / ".export-staging").mkdir()
    return root


def test_describe_export_reads_each_bundle_manifest(tmp_path):
    sys.path.insert(0, str(ROOT / "web"))
    job = importlib.import_module("job")
    out = job.describe_export(_fake_export(tmp_path / "export"))
    assert out == [{"ca_id": "050500", "dir": "ALPHA", "name": "Albay", "languages": ["en"], "default_language": "en",
                    "configurable_models": [{"uuid": "abc", "label": "Mobile"}], "patrols": 3, "timezone": "Asia/Manila"}]


def test_put_export_publishes_every_ca_and_not_the_staging_dir(client, tmp_path):
    app, _ = client
    store = app.get_store()
    id = _dataset(store)
    store.put_export(id, _fake_export(tmp_path / "export"))
    assert store.export_exists(id, "ALPHA") and not store.export_exists(id, ".export-staging")
    got = store.fetch_export(id, "ALPHA", tmp_path / "fetched")
    assert (got / "bundle" / "manifest.json").is_file() and (got / "datamodel.xml").is_file()
```

Add `import json` to the file's imports.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_web_extract.py -k "describe_export or put_export" -v`
Expected: FAIL with `AttributeError: module 'job' has no attribute 'describe_export'` and `'LocalStore' object has no attribute 'put_export'`

- [ ] **Step 3: Implement the store methods**

In `LocalStore`, after `put_site`:

```python
    def put_export(self, id: str, export_dir: Path):
        dest = self._p(id) / "export"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(export_dir, dest, symlinks=False, ignore=shutil.ignore_patterns(".export-staging"))

    def export_exists(self, id: str, ca_dir: str) -> bool:
        return (self._p(id) / "export" / safe_relpath(ca_dir) / "bundle" / "manifest.json").is_file()

    def fetch_export(self, id: str, ca_dir: str, dest: Path) -> Path:
        return self._p(id) / "export" / safe_relpath(ca_dir)  # already local
```

In `GcpStore`, after `put_site`:

```python
    def put_export(self, id: str, export_dir: Path):
        from concurrent.futures import ThreadPoolExecutor
        export_dir = Path(export_dir)
        prefix = f"datasets/{id}/export/"
        for old in self.bucket.list_blobs(prefix=prefix):
            old.delete()
        files = [p for p in export_dir.rglob("*") if p.is_file() and ".export-staging" not in p.parts]
        def up(p: Path):
            rel = p.relative_to(export_dir).as_posix()
            self.bucket.blob(prefix + rel).upload_from_filename(str(p), content_type=site_content_type(rel))
        with ThreadPoolExecutor(max_workers=16) as ex:
            list(ex.map(up, files))

    def export_exists(self, id: str, ca_dir: str) -> bool:
        return self.bucket.blob(f"datasets/{id}/export/{safe_relpath(ca_dir)}/bundle/manifest.json").exists()

    def fetch_export(self, id: str, ca_dir: str, dest: Path) -> Path:
        prefix = f"datasets/{id}/export/{safe_relpath(ca_dir)}/"
        dest = Path(dest)
        for blob in self.bucket.list_blobs(prefix=prefix):
            target = dest / blob.name[len(prefix):]
            target.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(target))
        return dest
```

Add `"export"` to `DATASET_FIELDS` and to the tuple in `app._public` so the list and detail routes return it.

- [ ] **Step 4: Implement `describe_export` and publish from the job**

In `web/job.py` add:

```python
def describe_export(export_dir: Path) -> list:
    """One entry per conservation area that has a bundle, from its manifest
    and datamodel.json: what the load form needs to offer."""
    out = []
    for manifest_path in sorted(Path(export_dir).glob("*/bundle/manifest.json")):
        ca_dir = manifest_path.parent.parent
        m = json.loads(manifest_path.read_text())
        dmj = json.loads((ca_dir / "datamodel.json").read_text()) if (ca_dir / "datamodel.json").is_file() else {}
        ca = m.get("conservation_area", {})
        out.append({"ca_id": ca.get("id"), "dir": ca_dir.name, "name": ca.get("name"),
                    "languages": [l["code"] for l in m.get("languages", [])],
                    "default_language": m.get("default_language"),
                    "configurable_models": [{"uuid": c.get("uuid"), "label": c.get("label")}
                                            for c in dmj.get("configurable_models", [])],
                    "patrols": (m.get("counts") or {}).get("patrols", 0),
                    "timezone": (m.get("timezone") or {}).get("name")})
    return out
```

In `main`, after `store.put_site(dataset_id, site)` and before the `ready` update:

```python
        export_dir = work / "out" / "export"
        export = describe_export(export_dir) if export_dir.is_dir() else []
        if export:
            print("publishing export", flush=True)
            store.put_export(dataset_id, export_dir)
```

and add `export=export` to the `status="ready"` update.

- [ ] **Step 5: Run the test file**

Run: `uv run pytest tests/test_web_extract.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add web/store.py web/job.py web/app.py tests/test_web_extract.py
git commit -m "Extraction publishes the migration bundle and lists it on the dataset"
```

### Task B2: Sites and secrets in the store

**Files:**
- Modify: `web/store.py`
- Test: `tests/test_web_sites.py`

**Interfaces:**
- Produces on both stores: `list_sites() -> list`, `get_site(id) -> dict | None`, `create_site(doc: dict, token: str) -> str` (writes the secret `smart-able-site-<id>` then the doc with `secret_name`), `update_site(id, **fields)`, `delete_site(id)` (deletes the doc and the secret), `read_site_token(id) -> str` (raises `KeyError` when the site or secret is gone). `SITE_FIELDS = ("name", "url", "owner_uid", "owner_email", "shared_with", "secret_name", "token_hint", "checked_at", "checked_as", "created_at", "updated_at")`. Local secrets live in `LOCAL_DIR/secrets/<secret_name>`, mode 0600.

- [ ] **Step 1: Write the failing tests**

`tests/test_web_sites.py`:

```python
"""Sites: the EarthRanger targets a load writes to. The token lives only in
the secret store; the doc keeps a hint."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("fastapi")

OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("app", "store", "auth", "er_site"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    from fastapi.testclient import TestClient

    return app, TestClient(app.app)


def test_create_site_keeps_the_token_out_of_the_index(client, tmp_path):
    app, _ = client
    store = app.get_store()
    id = store.create_site({"name": "phinney", "url": "phinney.staging.pamdas.org", **OWNER}, "tok-secret-1234")
    doc = store.get_site(id)
    assert doc["secret_name"] == f"smart-able-site-{id}" and "tok-secret" not in str(doc)
    assert "tok-secret" not in (tmp_path / "data" / "sites.json").read_text()
    assert store.read_site_token(id) == "tok-secret-1234"
    assert oct((tmp_path / "data" / "secrets" / doc["secret_name"]).stat().st_mode)[-3:] == "600"


def test_delete_site_removes_the_secret(client):
    app, _ = client
    store = app.get_store()
    id = store.create_site({"name": "x", "url": "x.pamdas.org", **OWNER}, "t")
    store.delete_site(id)
    assert store.get_site(id) is None
    with pytest.raises(KeyError):
        store.read_site_token(id)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_web_sites.py -v`
Expected: FAIL with `AttributeError: 'LocalStore' object has no attribute 'create_site'`

- [ ] **Step 3: Implement LocalStore**

Add after `DATASET_FIELDS`:

```python
SITE_FIELDS = ("name", "url", "owner_uid", "owner_email", "shared_with", "secret_name", "token_hint",
               "checked_at", "checked_as", "created_at", "updated_at")
```

In `LocalStore`, a second index file `sites.json` with the same read/write helpers generalized:

```python
    def _read_file(self, path: Path) -> dict:
        return json.loads(path.read_text()) if path.exists() else {}

    def _write_file(self, path: Path, data: dict):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1))
        tmp.replace(path)

    # ---- sites
    def list_sites(self) -> list:
        return [dict(id=k, **v) for k, v in self._read_file(self.dir / "sites.json").items()]

    def get_site(self, id: str):
        d = self._read_file(self.dir / "sites.json").get(id)
        return dict(id=id, **d) if d else None

    def create_site(self, doc: dict, token: str) -> str:
        id = uuid.uuid4().hex[:12]
        secret = f"smart-able-site-{id}"
        self._write_secret(secret, token)
        with self.lock:
            data = self._read_file(self.dir / "sites.json")
            data[id] = {**doc, "secret_name": secret}
            self._write_file(self.dir / "sites.json", data)
        return id

    def update_site(self, id: str, **fields):
        with self.lock:
            data = self._read_file(self.dir / "sites.json")
            if id in data:
                data[id].update(fields); data[id]["updated_at"] = now(); self._write_file(self.dir / "sites.json", data)

    def delete_site(self, id: str):
        with self.lock:
            data = self._read_file(self.dir / "sites.json")
            doc = data.pop(id, None)
            self._write_file(self.dir / "sites.json", data)
        if doc:
            (self.dir / "secrets" / doc["secret_name"]).unlink(missing_ok=True)

    def read_site_token(self, id: str) -> str:
        doc = self.get_site(id)
        p = self.dir / "secrets" / doc["secret_name"] if doc else None
        if not p or not p.is_file():
            raise KeyError(id)
        return p.read_text()

    def _write_secret(self, name: str, value: str):
        d = self.dir / "secrets"
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.touch(mode=0o600, exist_ok=True)
        p.chmod(0o600)
        p.write_text(value)
```

Keep the existing `_read`/`_write` for datasets as they are (or have them call the new helpers with `self.index`).

- [ ] **Step 4: Implement GcpStore**

```python
    # ---- sites
    def _sites(self):
        return self.db.collection("sites")

    def list_sites(self) -> list:
        return [dict(id=d.id, **d.to_dict()) for d in self._sites().stream()]

    def get_site(self, id: str):
        d = self._sites().document(id).get()
        return dict(id=d.id, **d.to_dict()) if d.exists else None

    def create_site(self, doc: dict, token: str) -> str:
        ref = self._sites().document()
        secret = f"smart-able-site-{ref.id}"
        self._secret_create(secret, token)
        ref.set({**doc, "secret_name": secret})
        return ref.id

    def update_site(self, id: str, **fields):
        fields["updated_at"] = now()
        self._sites().document(id).update(fields)

    def delete_site(self, id: str):
        doc = self.get_site(id)
        self._sites().document(id).delete()
        if doc:
            self._secret_delete(doc["secret_name"])

    def read_site_token(self, id: str) -> str:
        doc = self.get_site(id)
        if not doc:
            raise KeyError(id)
        from google.api_core.exceptions import NotFound
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        try:
            r = client.access_secret_version(name=f"projects/{self.project}/secrets/{doc['secret_name']}/versions/latest")
        except NotFound:
            raise KeyError(id) from None
        return r.payload.data.decode("utf-8")

    def _secret_create(self, name: str, value: str):
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{self.project}"
        client.create_secret(parent=parent, secret_id=name,
                             secret={"replication": {"automatic": {}}})
        client.add_secret_version(parent=f"{parent}/secrets/{name}", payload={"data": value.encode("utf-8")})

    def _secret_delete(self, name: str):
        from google.api_core.exceptions import NotFound
        from google.cloud import secretmanager
        try:
            secretmanager.SecretManagerServiceClient().delete_secret(name=f"projects/{self.project}/secrets/{name}")
        except NotFound:
            pass
```

Add `"google-cloud-secret-manager>=2.20"` and `"httpx>=0.27"` to the `web` extra in `pyproject.toml` and run `uv lock`.

- [ ] **Step 5: Run the test file**

Run: `uv run pytest tests/test_web_sites.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add web/store.py pyproject.toml uv.lock tests/test_web_sites.py
git commit -m "Store: EarthRanger sites with tokens in the secret store"
```

### Task B3: The sites API and the token check

**Files:**
- Create: `web/er_site.py`
- Modify: `web/app.py`
- Test: `tests/test_web_sites.py`

**Interfaces:**
- Produces: `er_site.normalize_host(url: str) -> str` (bare host, lowercased; raises `ValueError` when empty or not a hostname). `er_site.check_token(host: str, token: str) -> str` does `GET https://<host>/api/v1.0/user/me` with `Authorization: Bearer <token>`, 15 s timeout, returns the username (`data.username`, falling back to `data.email`); raises `er_site.TokenRejected(reason)` on 401/403, `er_site.SiteUnreachable(reason)` on connection errors or other statuses. Routes as in the spec. The public shape of a site is `{id, name, url, owner_email, shared_with, token_hint, checked_at, checked_as, created_at, mine}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_sites.py`:

```python
@pytest.fixture
def er(monkeypatch):
    """Stand in for the EarthRanger site: records calls, answers as told."""
    calls = []
    state = {"user": "smart_migration", "reject": False}

    def check(host, token):
        import er_site
        calls.append((host, token))
        if state["reject"]:
            raise er_site.TokenRejected("401 Unauthorized")
        return state["user"]

    monkeypatch.setattr(importlib.import_module("er_site"), "check_token", check)
    monkeypatch.setattr(importlib.import_module("app"), "check_token", check, raising=False)
    return calls, state


@pytest.mark.parametrize("given", ["phinney.staging.pamdas.org", "https://phinney.staging.pamdas.org",
                                   "https://Phinney.staging.pamdas.org/api/v1.0/", "phinney.staging.pamdas.org/"])
def test_register_normalizes_the_url_to_a_host(client, er, given):
    _, c = client
    r = c.post("/api/sites", json={"name": "phinney", "url": given, "token": "abcd1234wxyz"})
    assert r.status_code == 201, r.text
    assert r.json()["url"] == "phinney.staging.pamdas.org"
    assert r.json()["token_hint"] == "wxyz" and r.json()["checked_as"] == "smart_migration"
    assert er[0] == [("phinney.staging.pamdas.org", "abcd1234wxyz")]


def test_the_same_host_can_be_registered_twice(client, er):
    _, c = client
    for t in ("tok-one-aaaa", "tok-two-bbbb"):
        assert c.post("/api/sites", json={"name": "n", "url": "x.pamdas.org", "token": t}).status_code == 201
    assert len(c.get("/api/sites").json()) == 2


def test_a_rejected_token_stores_nothing(client, er):
    app, c = client
    er[1]["reject"] = True
    r = c.post("/api/sites", json={"name": "n", "url": "x.pamdas.org", "token": "bad"})
    assert r.status_code == 400 and "401" in r.json()["detail"]
    assert app.get_store().list_sites() == []


def test_a_bad_url_is_a_400(client, er):
    _, c = client
    assert c.post("/api/sites", json={"name": "n", "url": "not a host", "token": "t"}).status_code == 400


def test_sites_are_visible_to_owner_and_shared_only(client, er):
    _, c = client
    id = c.post("/api/sites", json={"name": "n", "url": "x.pamdas.org", "token": "t"}).json()["id"]
    other = {"X-Dev-User": "other@earthranger.com"}
    assert c.get("/api/sites", headers=other).json() == []
    assert c.post(f"/api/sites/{id}/share", json={"email": "other@earthranger.com"}).status_code == 200
    seen = c.get("/api/sites", headers=other).json()
    assert [s["id"] for s in seen] == [id] and seen[0]["mine"] is False
    assert c.delete(f"/api/sites/{id}", headers=other).status_code == 403
    assert c.delete(f"/api/sites/{id}").status_code == 200
    assert c.get("/api/sites").json() == []


def test_the_token_never_appears_in_a_response(client, er):
    _, c = client
    r = c.post("/api/sites", json={"name": "n", "url": "x.pamdas.org", "token": "super-secret-token"})
    assert "super-secret-token" not in r.text and "super-secret-token" not in c.get("/api/sites").text
```

And a direct test of `er_site` with a fake transport:

```python
def test_check_token_reads_the_username(monkeypatch):
    import httpx
    er_site = importlib.import_module("er_site")

    def handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer tok"
        assert str(request.url) == "https://x.pamdas.org/api/v1.0/user/me"
        return httpx.Response(200, json={"data": {"username": "ops", "email": "ops@x"}})

    monkeypatch.setattr(er_site, "_transport", lambda: httpx.MockTransport(handler))
    assert er_site.check_token("x.pamdas.org", "tok") == "ops"


def test_check_token_distinguishes_rejection_from_unreachable(monkeypatch):
    import httpx
    er_site = importlib.import_module("er_site")
    monkeypatch.setattr(er_site, "_transport", lambda: httpx.MockTransport(lambda r: httpx.Response(401, json={})))
    with pytest.raises(er_site.TokenRejected):
        er_site.check_token("x.pamdas.org", "tok")
    monkeypatch.setattr(er_site, "_transport", lambda: httpx.MockTransport(lambda r: httpx.Response(502)))
    with pytest.raises(er_site.SiteUnreachable):
        er_site.check_token("x.pamdas.org", "tok")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_web_sites.py -v`
Expected: the new tests FAIL (`ModuleNotFoundError: er_site`, 404s on `/api/sites`)

- [ ] **Step 3: Implement `web/er_site.py`**

```python
"""One EarthRanger site as a load target: its host, and whether a token works there."""
import re
from urllib.parse import urlparse

import httpx

_HOST = re.compile(r"^[a-z0-9.-]+$")


class TokenRejected(Exception):
    pass


class SiteUnreachable(Exception):
    pass


def normalize_host(url: str) -> str:
    """'https://Site.pamdas.org/api/v1.0/' -> 'site.pamdas.org'."""
    s = (url or "").strip()
    if "://" not in s:
        s = "https://" + s
    host = (urlparse(s).hostname or "").lower()
    if not host or not _HOST.match(host) or "." not in host:
        raise ValueError("Enter the site's host name, like site.pamdas.org")
    return host


def _transport():
    return None  # httpx's default; tests swap in a MockTransport


def check_token(host: str, token: str) -> str:
    """The username the token resolves to on the site."""
    try:
        with httpx.Client(transport=_transport(), timeout=15) as c:
            r = c.get(f"https://{host}/api/v1.0/user/me", headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as e:
        raise SiteUnreachable(f"could not reach {host}: {type(e).__name__}") from e
    if r.status_code in (401, 403):
        raise TokenRejected(f"{host} answered {r.status_code} {r.reason_phrase}")
    if r.status_code != 200:
        raise SiteUnreachable(f"{host} answered {r.status_code} {r.reason_phrase}")
    data = (r.json() or {}).get("data") or {}
    return data.get("username") or data.get("email") or "?"
```

- [ ] **Step 4: Implement the routes in `web/app.py`**

Add to the imports: `from er_site import SiteUnreachable, TokenRejected, check_token, normalize_host`. Add the models and helpers:

```python
class SiteCreate(BaseModel):
    name: str
    url: str
    token: str


def _site_public(doc: dict, user: dict) -> dict:
    return {k: doc.get(k) for k in ("id", "name", "url", "owner_email", "shared_with", "token_hint", "checked_at",
                                    "checked_as", "created_at")} | {"mine": is_owner(doc, user)}


def _load_site(id: str, user: dict, owner: bool = False) -> dict:
    doc = get_store().get_site(id)
    if not doc or not can_read(doc, user):
        raise HTTPException(status_code=404, detail="Site not found")
    if owner and not is_owner(doc, user):
        raise HTTPException(status_code=403, detail="Only the owner can do that")
    return doc
```

And the routes, in a `# ---- sites` section after the dataset routes:

```python
@app.get("/api/sites")
async def list_sites(user=Depends(current_user)):
    docs = [d for d in get_store().list_sites() if can_read(d, user)]
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return [_site_public(d, user) for d in docs]


@app.post("/api/sites", status_code=201)
async def create_site(req: SiteCreate, user=Depends(current_user)):
    try:
        host = normalize_host(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = req.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="A token is required")
    try:
        checked_as = check_token(host, token)
    except TokenRejected as e:
        raise HTTPException(status_code=400, detail=f"The token was rejected: {e}")
    except SiteUnreachable as e:
        raise HTTPException(status_code=400, detail=str(e))
    store = get_store()
    id = store.create_site({"name": req.name.strip() or host, "url": host, "owner_uid": user["uid"],
                            "owner_email": user["email"], "shared_with": [], "token_hint": token[-4:],
                            "checked_at": now(), "checked_as": checked_as, "created_at": now(), "updated_at": now()},
                           token)
    return _site_public(store.get_site(id), user)


@app.delete("/api/sites/{id}")
async def delete_site(id: str, user=Depends(current_user)):
    _load_site(id, user, owner=True)
    get_store().delete_site(id)
    return {"ok": True}


@app.post("/api/sites/{id}/share")
async def share_site(id: str, req: ShareRequest, user=Depends(current_user)):
    doc = _load_site(id, user, owner=True)
    email = req.email.strip().lower()
    if not email_allowed(email):
        raise HTTPException(status_code=400, detail="Can only share with allowed addresses")
    shared = sorted(set(doc.get("shared_with", [])) | {email})
    get_store().update_site(id, shared_with=shared)
    return {"shared_with": shared}


@app.delete("/api/sites/{id}/share/{email}")
async def unshare_site(id: str, email: str, user=Depends(current_user)):
    doc = _load_site(id, user, owner=True)
    shared = [e for e in doc.get("shared_with", []) if e.lower() != email.strip().lower()]
    get_store().update_site(id, shared_with=shared)
    return {"shared_with": shared}
```

Update the module docstring's route list. In the test fixture `er`, the monkeypatch of `app.check_token` is what takes effect, since `app.py` imports the name; keep both patches.

- [ ] **Step 5: Run the test file**

Run: `uv run pytest tests/test_web_sites.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add web/er_site.py web/app.py tests/test_web_sites.py
git commit -m "API: register, share and remove EarthRanger sites"
```

### Task B4: Loads in the store: documents, claims, storage, cascade

**Files:**
- Modify: `web/store.py`
- Test: `tests/test_web_loads.py`

**Interfaces:**
- Produces on both stores: `list_loads(dataset_id) -> list`, `get_load(id)`, `create_load(doc) -> str`, `update_load(id, **fields)`, `delete_load(id)` (doc and `datasets/<dataset_id>/loads/<id>/`), `claim_load(id, status: str) -> bool` (`status` is `planning` or `queued`; refuses when `load_in_progress(doc)`), `start_load(id, mode: str) -> str` (`mode` is `plan` or `run`; Cloud Run execution with env `LOAD_ID` and `MODE`, local subprocess of `web/load_job.py`), `put_load_file(dataset_id, load_id, name, path)`, `get_load_file(dataset_id, load_id, name) -> (chunks, size, ctype) | None`, `fetch_load_dir(dataset_id, load_id, dest) -> Path`, `delete_dataset_loads(dataset_id)`. Module-level: `LOAD_ACTIVE = ("planning", "queued", "running", "continuing")`, `LOAD_STALE_AFTER`, `load_in_progress(doc) -> bool` measured from `started_at` when `running`, else `claimed_at`. `LOAD_FIELDS` per the spec. `delete_storage(id)` already removes `datasets/<id>/` wholesale; `delete(id)` for a dataset must also call `delete_dataset_loads`.

- [ ] **Step 1: Write the failing tests**

`tests/test_web_loads.py`:

```python
"""Loads: one attempt to put a conservation area into a site. Claims and
holds work as for extraction; a dataset's loads go with it."""
from __future__ import annotations

import importlib
import json
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("fastapi")

OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}
EXPORT = [{"ca_id": "050500", "dir": "ALPHA", "name": "Albay", "languages": ["en"], "default_language": "en",
           "configurable_models": [{"uuid": "abc", "label": "Mobile"}], "patrols": 3, "timezone": "Asia/Manila"}]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("app", "store", "auth", "er_site"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    from fastapi.testclient import TestClient

    return app, TestClient(app.app)


def _dataset(store, export=EXPORT, status="ready"):
    id = store.create({"name": "x", "source_name": "backup.zip", "status": status, "export": export,
                       "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00", **OWNER})
    if export:
        b = store._p(id) / "export" / "ALPHA" / "bundle"
        b.mkdir(parents=True)
        (b / "manifest.json").write_text("{}")
    return id


def _site(store):
    return store.create_site({"name": "s", "url": "x.pamdas.org", "created_at": "2026-10-21T00:00:00+00:00", **OWNER}, "tok")


def _load(store, dataset_id, site_id, status="planned", **extra):
    return store.create_load({"dataset_id": dataset_id, "ca_id": "ALPHA", "site_id": site_id, "status": status,
                              "stage": None, "options": {"language": "en", "configurable_model": None, "roster_group": None},
                              "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00",
                              "continuations": 0, **OWNER, **extra})


def test_claim_admits_exactly_one_of_many(client):
    app, _ = client
    store = app.get_store()
    id = _load(store, _dataset(store), _site(store))
    results, start = [], threading.Barrier(16)

    def claim():
        start.wait()
        results.append(store.claim_load(id, "queued"))

    threads = [threading.Thread(target=claim) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1
    assert store.get_load(id)["status"] == "queued" and store.get_load(id)["claimed_at"]


@pytest.mark.parametrize("status, anchor", [("running", "started_at"), ("queued", "claimed_at"),
                                            ("planning", "claimed_at"), ("continuing", "claimed_at")])
def test_a_stale_hold_lapses(client, status, anchor):
    app, _ = client
    store = app.get_store()
    old = (datetime.now(timezone.utc) - timedelta(hours=26)).isoformat(timespec="seconds")
    id = _load(store, _dataset(store), _site(store), status=status, **{anchor: old})
    assert sys.modules["store"].load_in_progress(store.get_load(id)) is False
    assert store.claim_load(id, "queued") is True


def test_a_fresh_hold_refuses(client):
    app, _ = client
    store = app.get_store()
    id = _load(store, _dataset(store), _site(store), status="running",
               started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    assert store.claim_load(id, "queued") is False


def test_load_files_round_trip_and_go_with_the_load(client, tmp_path):
    app, _ = client
    store = app.get_store()
    ds = _dataset(store)
    id = _load(store, ds, _site(store))
    src = tmp_path / "plan.json"
    src.write_text('{"patrols": {"total": 3}}')
    store.put_load_file(ds, id, "plan.json", src)
    chunks, size, ctype = store.get_load_file(ds, id, "plan.json")
    assert b"".join(chunks) == src.read_bytes() and ctype == "application/json"
    fetched = store.fetch_load_dir(ds, id, tmp_path / "fetched")
    assert (fetched / "plan.json").is_file()
    store.delete_load(id)
    assert store.get_load(id) is None and store.get_load_file(ds, id, "plan.json") is None


def test_deleting_a_dataset_deletes_its_loads(client):
    app, c = client
    store = app.get_store()
    ds = _dataset(store)
    id = _load(store, ds, _site(store), status="running",
               started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    assert c.delete(f"/api/datasets/{ds}").status_code == 200
    assert store.get_load(id) is None and store.list_loads(ds) == []


def test_start_load_runs_the_job_with_its_mode(client, monkeypatch):
    app, _ = client
    store = app.get_store()
    seen = {}
    monkeypatch.setattr(store, "load_job_command", lambda id, mode: [sys.executable, "-c",
                        f"import pathlib; pathlib.Path({str(store.dir / 'ran')!r}).write_text({mode!r})"])
    id = _load(store, _dataset(store), _site(store))
    assert store.start_load(id, "plan") == "local-thread"
    import time
    deadline = time.time() + 5
    while time.time() < deadline and not (store.dir / "ran").exists():
        time.sleep(0.05)
    assert (store.dir / "ran").read_text() == "plan"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_web_loads.py -v`
Expected: FAIL with `AttributeError: 'LocalStore' object has no attribute 'create_load'`

- [ ] **Step 3: Implement the module-level pieces**

After the extraction constants in `store.py`:

```python
LOAD_FIELDS = ("dataset_id", "ca_id", "site_id", "owner_uid", "owner_email", "options", "status", "stage",
               "created_at", "updated_at", "execution", "continuations", "plan", "findings", "progress",
               "log_tail", "error", "started_at", "claimed_at")
LOAD_ACTIVE = ("planning", "queued", "running", "continuing")
LOAD_STALE_AFTER = timedelta(seconds=int(os.environ.get("LOAD_STALE_AFTER_SECONDS", 90000)))


def load_in_progress(doc: dict) -> bool:
    """A load holds its slot while an execution is planning, queued, running
    or continuing, until the hold goes stale (a job killed outright cannot
    release it)."""
    if doc.get("status") not in LOAD_ACTIVE:
        return False
    since = doc.get("started_at") if doc.get("status") == "running" else doc.get("claimed_at")
    try:
        since = datetime.fromisoformat(since or doc["updated_at"])
    except (KeyError, TypeError, ValueError):
        return True
    return datetime.now(timezone.utc) - since < LOAD_STALE_AFTER
```

- [ ] **Step 4: Implement LocalStore**

```python
    # ---- loads
    def _loads_path(self) -> Path:
        return self.dir / "loads.json"

    def list_loads(self, dataset_id: str) -> list:
        return [dict(id=k, **v) for k, v in self._read_file(self._loads_path()).items() if v.get("dataset_id") == dataset_id]

    def get_load(self, id: str):
        d = self._read_file(self._loads_path()).get(id)
        return dict(id=id, **d) if d else None

    def create_load(self, doc: dict) -> str:
        id = uuid.uuid4().hex[:12]
        with self.lock:
            data = self._read_file(self._loads_path()); data[id] = doc; self._write_file(self._loads_path(), data)
        return id

    def update_load(self, id: str, **fields):
        with self.lock:
            data = self._read_file(self._loads_path())
            if id in data:
                data[id].update(fields); data[id]["updated_at"] = now(); self._write_file(self._loads_path(), data)

    def delete_load(self, id: str):
        with self.lock:
            data = self._read_file(self._loads_path())
            doc = data.pop(id, None)
            self._write_file(self._loads_path(), data)
        if doc:
            shutil.rmtree(self._p(doc["dataset_id"]) / "loads" / id, ignore_errors=True)

    def delete_dataset_loads(self, dataset_id: str):
        for l in self.list_loads(dataset_id):
            self.delete_load(l["id"])

    def claim_load(self, id: str, status: str) -> bool:
        with self.lock:
            data = self._read_file(self._loads_path())
            doc = data.get(id)
            if doc is None or load_in_progress(doc):
                return False
            doc.update(status=status, error=None, claimed_at=now(), updated_at=now())
            self._write_file(self._loads_path(), data)
            return True

    def _load_dir(self, dataset_id: str, load_id: str) -> Path:
        return self._p(dataset_id) / "loads" / load_id

    def put_load_file(self, dataset_id: str, load_id: str, name: str, path: Path):
        dest = self._load_dir(dataset_id, load_id) / safe_relpath(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)

    def get_load_file(self, dataset_id: str, load_id: str, name: str):
        f = self._load_dir(dataset_id, load_id) / safe_relpath(name)
        if not f.is_file():
            return None
        size = f.stat().st_size
        def chunks():
            with open(f, "rb") as fh:
                while True:
                    b = fh.read(1 << 20)
                    if not b:
                        break
                    yield b
        return chunks(), size, site_content_type(name)

    def fetch_load_dir(self, dataset_id: str, load_id: str, dest: Path) -> Path:
        src = self._load_dir(dataset_id, load_id)
        dest = Path(dest)
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            dest.mkdir(parents=True, exist_ok=True)
        return dest

    def load_job_command(self, id: str, mode: str) -> list:
        return [os.environ.get("LOAD_PYTHON", sys.executable), str(ROOT / "web" / "load_job.py"), id, mode]

    def start_load(self, id: str, mode: str) -> str:
        def run():
            proc = subprocess.Popen(self.load_job_command(id, mode),
                                    env={**os.environ, "BACKEND": "local", "LOAD_ID": id, "MODE": mode},
                                    start_new_session=True)
            proc.wait()
        threading.Thread(target=run, daemon=True).start()
        return "local-thread"
```

`LOAD_PYTHON` lets a local run point at the er-smart-sync venv's interpreter (Task B9's docker-compose sets it to `/opt/load/bin/python`). The local backend does not enforce a timeout on loads: continuation (Task B7) handles the clock from inside the job. Change `delete(self, id)` for datasets to call `self.delete_dataset_loads(id)` first.

- [ ] **Step 5: Implement GcpStore**

```python
    # ---- loads
    def _loads(self):
        return self.db.collection("loads")

    def list_loads(self, dataset_id: str) -> list:
        return [dict(id=d.id, **d.to_dict()) for d in self._loads().where("dataset_id", "==", dataset_id).stream()]

    def get_load(self, id: str):
        d = self._loads().document(id).get()
        return dict(id=d.id, **d.to_dict()) if d.exists else None

    def create_load(self, doc: dict) -> str:
        ref = self._loads().document()
        ref.set(doc)
        return ref.id

    def update_load(self, id: str, **fields):
        fields["updated_at"] = now()
        self._loads().document(id).update(fields)

    def delete_load(self, id: str):
        doc = self.get_load(id)
        self._loads().document(id).delete()
        if doc:
            for b in self.bucket.list_blobs(prefix=f"datasets/{doc['dataset_id']}/loads/{id}/"):
                b.delete()

    def delete_dataset_loads(self, dataset_id: str):
        for l in self.list_loads(dataset_id):
            self._loads().document(l["id"]).delete()   # the files go with delete_storage(dataset_id)

    def claim_load(self, id: str, status: str) -> bool:
        from google.cloud import firestore
        ref = self._loads().document(id)

        @firestore.transactional
        def claim(tx) -> bool:
            snap = ref.get(transaction=tx)
            if not snap.exists or load_in_progress(snap.to_dict()):
                return False
            tx.update(ref, {"status": status, "error": None, "claimed_at": now(), "updated_at": now()})
            return True

        return claim(self.db.transaction())

    def put_load_file(self, dataset_id: str, load_id: str, name: str, path: Path):
        rel = safe_relpath(name)
        self.bucket.blob(f"datasets/{dataset_id}/loads/{load_id}/{rel}").upload_from_filename(
            str(path), content_type=site_content_type(rel))

    def get_load_file(self, dataset_id: str, load_id: str, name: str):
        blob = self.bucket.blob(f"datasets/{dataset_id}/loads/{load_id}/{safe_relpath(name)}")
        if not blob.exists():
            return None
        blob.reload()
        def chunks():
            with blob.open("rb") as fh:
                while True:
                    b = fh.read(1 << 20)
                    if not b:
                        break
                    yield b
        return chunks(), blob.size, blob.content_type or site_content_type(name)

    def fetch_load_dir(self, dataset_id: str, load_id: str, dest: Path) -> Path:
        prefix = f"datasets/{dataset_id}/loads/{load_id}/"
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for blob in self.bucket.list_blobs(prefix=prefix):
            target = dest / blob.name[len(prefix):]
            target.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(target))
        return dest

    def start_load(self, id: str, mode: str) -> str:
        from google.cloud import run_v2
        client = run_v2.JobsClient()
        name = f"projects/{self.project}/locations/{self.region}/jobs/{os.environ.get('LOAD_JOB', 'smart-able-load')}"
        req = run_v2.RunJobRequest(name=name, overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[run_v2.RunJobRequest.Overrides.ContainerOverride(
                env=[run_v2.EnvVar(name="LOAD_ID", value=id), run_v2.EnvVar(name="MODE", value=mode)])]))
        op = client.run_job(request=req)
        return getattr(op.metadata, "name", "") or "started"
```

The Firestore `where` on `dataset_id` needs no composite index (single field). Add `datasets/<id>/loads/` to the "Files" row of the table in `web/DEPLOY.md`.

- [ ] **Step 6: Run the test file and the extraction tests**

Run: `uv run pytest tests/test_web_loads.py tests/test_web_extract.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add web/store.py web/DEPLOY.md tests/test_web_loads.py
git commit -m "Store: loads with claims, files and the job launcher; deleted with their dataset"
```

### Task B5: The loads API

**Files:**
- Modify: `web/app.py`
- Test: `tests/test_web_loads.py`

**Interfaces:**
- Consumes: store methods from Task B4, `_load_site` from Task B3.
- Produces: the routes in the spec. `_load_public(doc, user)` returns every `LOAD_FIELDS` key plus `id`, `mine`, `held` (`load_in_progress`), and `site` (`{id, name, url}` or `null` when the site is gone). `POST /api/datasets/{id}/loads` body is `LoadCreate(ca_id: str, site_id: str, options: dict = {})`; `options` is normalized to exactly `{language, configurable_model, roster_group}`, `language` defaulting to the export entry's `default_language`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_loads.py`:

```python
@pytest.fixture
def launches(client, monkeypatch):
    app, _ = client
    calls = []
    monkeypatch.setattr(app.get_store(), "start_load", lambda id, mode: calls.append((id, mode)) or "exec-1")
    return calls


def test_create_load_plans_first(client, launches):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    r = c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": site, "options": {"roster_group": "Rangers"}})
    assert r.status_code == 201, r.text
    load = r.json()
    assert load["status"] == "planning" and load["site"] == {"id": site, "name": "s", "url": "x.pamdas.org"}
    assert load["options"] == {"language": "en", "configurable_model": None, "roster_group": "Rangers"}
    assert launches == [(load["id"], "plan")]
    assert c.get(f"/api/datasets/{ds}/loads").json()[0]["id"] == load["id"]
    assert c.get(f"/api/loads/{load['id']}").json()["held"] is True


def test_create_load_refuses_bad_inputs(client, launches):
    app, c = client
    store = app.get_store()
    site = _site(store)
    no_export = _dataset(store, export=[])
    assert c.post(f"/api/datasets/{no_export}/loads", json={"ca_id": "ALPHA", "site_id": site}).status_code == 400
    ds = _dataset(store)
    assert c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "NOPE", "site_id": site}).status_code == 400
    empty = _dataset(store, export=[{**EXPORT[0], "patrols": 0}])
    assert c.post(f"/api/datasets/{empty}/loads", json={"ca_id": "ALPHA", "site_id": site}).status_code == 400
    assert c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": "missing"}).status_code == 404
    assert c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": site, "options": {"language": "xx"}}).status_code == 400
    assert launches == []


def test_a_second_active_load_for_the_same_target_is_refused(client, launches):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    body = {"ca_id": "ALPHA", "site_id": site}
    assert c.post(f"/api/datasets/{ds}/loads", json=body).status_code == 201
    assert c.post(f"/api/datasets/{ds}/loads", json=body).status_code == 409
    other = _site(store)
    assert c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": other}).status_code == 201


def test_run_confirms_a_plan_and_continues_a_stopped_load(client, launches):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    planned = _load(store, ds, site, status="planned")
    assert c.post(f"/api/loads/{planned}/run").status_code == 200
    assert store.get_load(planned)["status"] == "queued" and launches[-1] == (planned, "run")
    stopped = _load(store, ds, site, status="needs_attention")
    assert c.post(f"/api/loads/{stopped}/run").status_code == 200
    done = _load(store, ds, site, status="done")
    assert c.post(f"/api/loads/{done}/run").status_code == 409
    assert c.post(f"/api/loads/{done}/replan").status_code == 200
    assert store.get_load(done)["status"] == "planning" and launches[-1] == (done, "plan")
    assert c.post(f"/api/loads/{planned}/replan").status_code == 409   # it is queued now


def test_a_removed_site_blocks_run_and_replan(client, launches):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    id = _load(store, ds, site, status="needs_attention")
    store.delete_site(site)
    before = store.get_load(id)
    assert c.post(f"/api/loads/{id}/run").status_code == 409
    assert c.post(f"/api/loads/{id}/replan").status_code == 409
    assert store.get_load(id) == before and launches == []
    assert c.get(f"/api/loads/{id}").json()["site"] is None


def test_permissions_follow_the_dataset(client, launches):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    id = _load(store, ds, site)
    other = {"X-Dev-User": "other@earthranger.com"}
    assert c.get(f"/api/loads/{id}", headers=other).status_code == 404
    assert c.post(f"/api/loads/{id}/run", headers=other).status_code == 404
    c.post(f"/api/datasets/{ds}/share", json={"email": "other@earthranger.com"})
    assert c.get(f"/api/loads/{id}", headers=other).status_code == 200
    # the site is not shared with them, so they cannot start a new load into it
    assert c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": site}, headers=other).status_code == 404


def test_delete_and_files(client, tmp_path):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    id = _load(store, ds, site, status="running", started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    assert c.delete(f"/api/loads/{id}").status_code == 409
    store.update_load(id, status="done")
    src = tmp_path / "log.txt"; src.write_text("hello")
    store.put_load_file(ds, id, "log.txt", src)
    assert c.get(f"/api/loads/{id}/files/log.txt").text == "hello"
    assert c.get(f"/api/loads/{id}/files/nope.txt").status_code == 404
    assert c.get(f"/api/loads/{id}/files/..%2Fsecret").status_code in (400, 404)
    assert c.delete(f"/api/loads/{id}").status_code == 200
    assert store.get_load(id) is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_web_loads.py -v`
Expected: the new tests FAIL with 404/405 on the routes

- [ ] **Step 3: Implement**

In `web/app.py`, import `LOAD_ACTIVE, load_in_progress` from `store`, add:

```python
class LoadCreate(BaseModel):
    ca_id: str
    site_id: str
    options: dict = {}


def _load_public(doc: dict, user: dict) -> dict:
    site = get_store().get_site(doc.get("site_id", "")) if doc.get("site_id") else None
    return {k: doc.get(k) for k in LOAD_FIELDS} | {
        "id": doc["id"], "mine": is_owner(doc, user), "held": load_in_progress(doc),
        "site": {"id": site["id"], "name": site.get("name"), "url": site.get("url")} if site else None}


def _load_load(id: str, user: dict) -> dict:
    doc = get_store().get_load(id)
    if not doc:
        raise HTTPException(status_code=404, detail="Load not found")
    _load(doc["dataset_id"], user)   # read on the dataset is the permission
    return doc


def _launch(load_id: str, mode: str):
    """Start the job for a load that already holds its slot."""
    store = get_store()
    try:
        execution = store.start_load(load_id, mode)
    except Exception as e:  # noqa: BLE001
        logging.exception("could not start load %s", load_id)
        store.update_load(load_id, status="failed", error=f"Could not start the job: {type(e).__name__}: {e}")
        raise HTTPException(status_code=502, detail="Could not start the load job") from e
    store.update_load(load_id, execution=execution)


def _start(load_id: str, mode: str, claim_status: str):
    if not get_store().claim_load(load_id, claim_status):
        raise HTTPException(status_code=409, detail="This load is already planning or running")
    _launch(load_id, mode)
```

Import `LOAD_FIELDS` too. Routes:

```python
@app.post("/api/datasets/{id}/loads", status_code=201)
async def create_load(id: str, req: LoadCreate, user=Depends(current_user)):
    doc = _load(id, user)
    site = _load_site(req.site_id, user)
    entry = next((e for e in doc.get("export") or [] if e.get("dir") == req.ca_id), None)
    if not entry:
        raise HTTPException(status_code=400, detail="No migration bundle for that conservation area; re-extract the dataset")
    if not entry.get("patrols"):
        raise HTTPException(status_code=400, detail="That conservation area has no patrols to load")
    language = req.options.get("language") or entry.get("default_language")
    if language not in entry.get("languages", []):
        raise HTTPException(status_code=400, detail=f"Language {language!r} is not in the bundle")
    cm = req.options.get("configurable_model") or None
    if cm and cm not in [c["uuid"] for c in entry.get("configurable_models", [])]:
        raise HTTPException(status_code=400, detail="Unknown configurable model")
    store = get_store()
    for other in store.list_loads(id):
        if other.get("ca_id") == req.ca_id and other.get("site_id") == req.site_id and load_in_progress(other):
            raise HTTPException(status_code=409, detail="A load of this conservation area into that site is already active")
    load_id = store.create_load({
        "dataset_id": id, "ca_id": req.ca_id, "site_id": site["id"], "owner_uid": user["uid"], "owner_email": user["email"],
        "options": {"language": language, "configurable_model": cm,
                    "roster_group": (req.options.get("roster_group") or "").strip() or None},
        "status": "planning", "stage": None, "claimed_at": now(),   # created holding its slot: no claim race
        "created_at": now(), "updated_at": now(), "continuations": 0,
        "plan": None, "findings": [], "progress": None, "log_tail": None, "error": None})
    _launch(load_id, "plan")
    return _load_public(store.get_load(load_id), user)


@app.get("/api/datasets/{id}/loads")
async def list_loads(id: str, user=Depends(current_user)):
    _load(id, user)
    docs = get_store().list_loads(id)
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return [_load_public(d, user) for d in docs]


@app.get("/api/loads/{id}")
async def get_load(id: str, user=Depends(current_user)):
    return _load_public(_load_load(id, user), user)


def _needs_site(doc: dict):
    if not get_store().get_site(doc.get("site_id", "")):
        raise HTTPException(status_code=409, detail="The site was removed; register it again and start a new load")


@app.post("/api/loads/{id}/run")
async def run_load(id: str, user=Depends(current_user)):
    doc = _load_load(id, user)
    if doc.get("status") not in ("planned", "needs_attention"):
        raise HTTPException(status_code=409, detail=f"A {doc.get('status')} load cannot be run; plan it again first")
    _needs_site(doc)
    _start(id, "run", "queued")
    return _load_public(get_store().get_load(id), user)


@app.post("/api/loads/{id}/replan")
async def replan_load(id: str, user=Depends(current_user)):
    doc = _load_load(id, user)
    if doc.get("status") not in ("planned", "needs_attention", "failed", "done") or load_in_progress(doc):
        raise HTTPException(status_code=409, detail=f"A {doc.get('status')} load cannot be planned again now")
    _needs_site(doc)
    _start(id, "plan", "planning")
    return _load_public(get_store().get_load(id), user)


@app.delete("/api/loads/{id}")
async def delete_load(id: str, user=Depends(current_user)):
    doc = _load_load(id, user)
    if load_in_progress(doc):
        raise HTTPException(status_code=409, detail="Wait for the load to stop before deleting it")
    get_store().delete_load(id)
    return {"ok": True}


@app.get("/api/loads/{id}/files/{name}")
async def load_file(id: str, name: str, user=Depends(current_user)):
    doc = _load_load(id, user)
    try:
        found = get_store().get_load_file(doc["dataset_id"], id, name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad path")
    if not found:
        raise HTTPException(status_code=404, detail="Not found")
    chunks, size, ctype = found
    return StreamingResponse(chunks, media_type=ctype, headers={"Content-Length": str(size)})
```

Note `replan` on a `planned` load is allowed by status but refused while held: a `planned` load is never held, so a stale `planned` plan can be refreshed. The test expects 409 for the load that was just queued by `run`, which the hold check gives. Update the module docstring's route list.

- [ ] **Step 4: Run the test file**

Run: `uv run pytest tests/test_web_loads.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add web/app.py tests/test_web_loads.py
git commit -m "API: create, plan, run, continue, delete loads and read their files"
```

### Task B6: Findings and the plan, as pure functions

**Files:**
- Create: `web/findings.py`
- Test: `tests/test_findings.py`

**Interfaces:**
- Produces, all pure and importable without er-smart-sync or Google libraries:

```python
MAX_PATROLS = 50
LIST_CAP = 200

def finding(stage, code, severity, title, detail="", fix="", patrols=()) -> dict
def from_checklist(items: list[dict]) -> list[dict]          # items are ChecklistItem.to_dict()
def from_preflight(report_json: dict) -> list[dict]           # the dict render_json produces (blocking, warnings)
def from_failed_patrols(failed: dict, ids: dict) -> list[dict]   # ImportResult.failed, {uuid: smart id}
def token_rejected(detail: str) -> dict
def has_blocking(findings: list[dict]) -> bool
def build_plan(*, datamodel_stats: dict, dry_calls: list, pd_changes: list, pd_stats: dict,
               roster_group: str | None, patrols: list[dict], ledger_done: set, counts: dict) -> dict
```

`from_checklist` maps `code → code`, `title → title`, `steps` joined with newlines into `fix`, severity `blocking` for codes in `("enable_patrol_schemas", "permission_patrol_types", "permission_segment_schema", "permission_subjects", "permission_patrol_config", "permission_subject_group", "team", "roster_group")` and `warning` otherwise (`patrol_type_icons`, `station_names`), stage `patrol_datamodel`, `affected.count` 0. `from_preflight` maps each entry's `code`, `level → severity`, `message → title`, `fix`, `examples` joined into `detail`, `affected_patrols → affected`, stage `preflight`. `from_failed_patrols` returns one blocking finding, stage `import`, code `patrols_failed`, title `"N patrols failed to import"`, detail one line per patrol `"<smart id>: <error>"`, affected the uuids. `build_plan` returns the dict in the spec: `event_categories`/`event_types` from `dry_calls` (`post_event_category` → create with `args[0]["value"]` and `display`; `post_event_type` → create, `patch_event_type` → update, payload `args[0]`, `unchanged` from `datamodel_stats["event_types_unchanged"]` and `["categories_existing"]`); `patrol_types`, `choices`, `subjects` from `pd_changes` by `kind` and `action` (`created` → create, `updated` → update, subject `deactivated` → deactivate; entries carry `value` or `id`); `universal_patrol_fields` `"write"` if `pd_stats["schema_written"]`, `"skip"` if `pd_stats["schema_skipped"]`, else `"merge"`; `roster` `{"group": roster_group, "add": pd_stats["subjects_grouped"]}`; `patrols` `{"total": len(patrols), "first", "last"` (min and max `start_date`), `"already_done": len(ledger_done)`, `"events": counts["observations"], "track_points": counts["track_points"]}`. Every list is `[{"value", "label"}]` capped at `LIST_CAP` with `"more": n` on the group when cut.

- [ ] **Step 1: Write the failing tests**

`tests/test_findings.py`:

```python
"""Findings and the plan are data the UI renders; the job only assembles them."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture
def findings(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    sys.modules.pop("findings", None)
    return importlib.import_module("findings")


def test_checklist_items_become_findings_with_their_severity(findings):
    out = findings.from_checklist([
        {"code": "team", "title": "Create the patrol team Alpha", "steps": ["Django admin > Teams.", "Re-run."]},
        {"code": "patrol_type_icons", "title": "Pick icons", "steps": ["Admin > Patrol types."]}])
    assert out[0] == {"stage": "patrol_datamodel", "code": "team", "severity": "blocking",
                      "title": "Create the patrol team Alpha", "detail": "",
                      "fix": "Django admin > Teams.\nRe-run.", "affected": {"count": 0, "patrols": []}}
    assert out[1]["severity"] == "warning"
    assert findings.has_blocking(out) and not findings.has_blocking(out[1:])


def test_preflight_findings_keep_their_patrols_capped(findings):
    many = [f"{i:032x}" for i in range(80)]
    out = findings.from_preflight({"blocking": [{"code": "team_missing", "level": "blocking", "message": "7 teams missing",
                                                 "fix": "Create them", "count": 7, "examples": ["A", "B"],
                                                 "affected_patrols": many}],
                                   "warnings": [{"code": "collection_type", "level": "warning", "message": "m", "fix": "f",
                                                 "count": 0, "examples": [], "affected_patrols": []}]})
    assert out[0]["stage"] == "preflight" and out[0]["severity"] == "blocking" and out[0]["title"] == "7 teams missing"
    assert out[0]["detail"] == "A\nB" and out[0]["affected"] == {"count": 80, "patrols": many[:50]}
    assert out[1]["severity"] == "warning"


def test_failed_patrols_become_one_blocking_finding(findings):
    out = findings.from_failed_patrols({"u1": "500 on track", "u2": "timeout"}, {"u1": "P-1", "u2": "P-2"})
    assert len(out) == 1 and out[0]["code"] == "patrols_failed" and out[0]["stage"] == "import"
    assert out[0]["title"] == "2 patrols failed to import" and "P-1: 500 on track" in out[0]["detail"]
    assert out[0]["affected"] == {"count": 2, "patrols": ["u1", "u2"]}


def test_token_rejected_is_a_blocking_finding(findings):
    f = findings.token_rejected("401 Unauthorized")
    assert f["severity"] == "blocking" and f["code"] == "site_token_rejected" and "register" in f["fix"].lower()


def test_build_plan_groups_dry_run_writes(findings):
    calls = [("post_event_category", ({"value": "smart-050500", "display": "Albay"},), {}),
             ("post_event_type", ({"value": "smart-ca-import_animals", "display": "Animals"},), {}),
             ("patch_event_type", ({"value": "smart-ca-import_threats", "display": "Threats"},), {}),
             ("get_event_types", (), {})]
    changes = [{"kind": "patrol_type", "action": "created", "value": "patrol_foot"},
               {"kind": "choice", "action": "updated", "value": "law", "id": "c1", "before": {}},
               {"kind": "subject", "action": "created", "id": "s1", "value": "Ana Cruz"},
               {"kind": "subject", "action": "deactivated", "id": "s2"},
               {"kind": "universal_patrol_fields", "action": "written", "before_file": None}]
    plan = findings.build_plan(datamodel_stats={"event_types_unchanged": 5, "categories_existing": 1},
                               dry_calls=calls, pd_changes=changes,
                               pd_stats={"schema_written": True, "schema_skipped": None, "subjects_grouped": 2},
                               roster_group="Rangers",
                               patrols=[{"uuid": "a", "start_date": "2019-03-04"}, {"uuid": "b", "start_date": "2024-11-30"}],
                               ledger_done={"a"}, counts={"observations": 10, "track_points": 400})
    assert plan["event_categories"] == {"create": [{"value": "smart-050500", "label": "Albay"}], "update": [], "unchanged": 1}
    assert plan["event_types"]["create"] == [{"value": "smart-ca-import_animals", "label": "Animals"}]
    assert plan["event_types"]["update"] == [{"value": "smart-ca-import_threats", "label": "Threats"}]
    assert plan["event_types"]["unchanged"] == 5
    assert plan["patrol_types"] == {"create": [{"value": "patrol_foot", "label": "patrol_foot"}], "update": []}
    assert plan["choices"]["update"] == [{"value": "law", "label": "law"}]
    assert plan["subjects"] == {"create": [{"value": "s1", "label": "Ana Cruz"}], "update": [],
                                "deactivate": [{"value": "s2", "label": "s2"}]}
    assert plan["universal_patrol_fields"] == "write" and plan["roster"] == {"group": "Rangers", "add": 2}
    assert plan["patrols"] == {"total": 2, "first": "2019-03-04", "last": "2024-11-30", "already_done": 1,
                               "events": 10, "track_points": 400}


def test_build_plan_caps_long_lists(findings):
    calls = [("post_event_type", ({"value": f"t{i}", "display": f"T{i}"},), {}) for i in range(250)]
    plan = findings.build_plan(datamodel_stats={}, dry_calls=calls, pd_changes=[], pd_stats={}, roster_group=None,
                               patrols=[], ledger_done=set(), counts={})
    assert len(plan["event_types"]["create"]) == 200 and plan["event_types"]["more"] == 50
    assert plan["patrols"]["first"] is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_findings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'findings'`

- [ ] **Step 3: Implement `web/findings.py`**

```python
"""Findings and the plan: the data the load page renders. A finding is where
the job stopped and what a human does about it; the plan is what a run
would write. Pure functions, no er-smart-sync or Google imports, so the
service and the job both use them."""
MAX_PATROLS = 50
LIST_CAP = 200
BLOCKING_CHECKLIST = ("enable_patrol_schemas", "permission_patrol_types", "permission_segment_schema",
                      "permission_subjects", "permission_patrol_config", "permission_subject_group", "team",
                      "roster_group")


def finding(stage, code, severity, title, detail="", fix="", patrols=()) -> dict:
    patrols = list(patrols)
    return {"stage": stage, "code": code, "severity": severity, "title": title, "detail": detail, "fix": fix,
            "affected": {"count": len(patrols), "patrols": patrols[:MAX_PATROLS]}}


def from_checklist(items: list) -> list:
    return [finding("patrol_datamodel", i["code"], "blocking" if i["code"] in BLOCKING_CHECKLIST else "warning",
                    i["title"], fix="\n".join(i.get("steps") or [])) for i in items]


def from_preflight(report: dict) -> list:
    out = []
    for f in list(report.get("blocking") or []) + list(report.get("warnings") or []):
        out.append(finding("preflight", f["code"], f["level"], f["message"], detail="\n".join(f.get("examples") or []),
                           fix=f.get("fix") or "", patrols=f.get("affected_patrols") or []))
    return out


def from_failed_patrols(failed: dict, ids: dict) -> list:
    if not failed:
        return []
    n = len(failed)
    detail = "\n".join(f"{ids.get(u, u)}: {err}" for u, err in failed.items())
    return [finding("import", "patrols_failed", "blocking", f"{n} patrol{'s' if n != 1 else ''} failed to import",
                    detail=detail, fix="Read each error; fix the site if it names a missing team, subject or event type, "
                    "then press Continue. Only these patrols are retried.", patrols=list(failed))]


def token_rejected(detail: str) -> dict:
    return finding("datamodel", "site_token_rejected", "blocking", "The site's token no longer works", detail=detail,
                   fix="Register the site again with a working token, then start a new load.")


def has_blocking(findings: list) -> bool:
    return any(f.get("severity") == "blocking" for f in findings)


def _cap(items: list) -> tuple:
    return items[:LIST_CAP], max(0, len(items) - LIST_CAP)


def _entry(value, label=None) -> dict:
    return {"value": value, "label": label or value}


def _group(**lists) -> dict:
    out, more = {}, 0
    for k, v in lists.items():
        if isinstance(v, list):
            out[k], cut = _cap(v)
            more += cut
        else:
            out[k] = v
    if more:
        out["more"] = more
    return out


def build_plan(*, datamodel_stats, dry_calls, pd_changes, pd_stats, roster_group, patrols, ledger_done, counts) -> dict:
    cats, types = {"create": [], "update": []}, {"create": [], "update": []}
    for name, args, kwargs in dry_calls:
        payload = args[0] if args else kwargs.get("data") or kwargs.get("event_type") or {}
        e = _entry(payload.get("value"), payload.get("display"))
        if name == "post_event_category":
            cats["create"].append(e)
        elif name == "patch_event_category":
            cats["update"].append(e)
        elif name == "post_event_type":
            types["create"].append(e)
        elif name == "patch_event_type":
            types["update"].append(e)
    by_kind = {"patrol_type": {"create": [], "update": []}, "choice": {"create": [], "update": []},
               "subject": {"create": [], "update": [], "deactivate": []}}
    action_key = {"created": "create", "updated": "update", "deactivated": "deactivate"}
    for c in pd_changes:
        k = action_key.get(c.get("action"))
        if c.get("kind") in by_kind and k in by_kind[c["kind"]]:
            ident = c.get("id") if c.get("kind") == "subject" else c.get("value")
            by_kind[c["kind"]][k].append(_entry(ident or c.get("value"), c.get("value") if c.get("kind") == "subject" else None))
    dates = sorted(p["start_date"] for p in patrols if p.get("start_date"))
    return {
        "event_categories": _group(**cats, unchanged=datamodel_stats.get("categories_existing", 0)),
        "event_types": _group(**types, unchanged=datamodel_stats.get("event_types_unchanged", 0)),
        "patrol_types": _group(**by_kind["patrol_type"]),
        "universal_patrol_fields": "write" if pd_stats.get("schema_written") else "skip" if pd_stats.get("schema_skipped") else "merge",
        "choices": _group(**by_kind["choice"]),
        "subjects": _group(**by_kind["subject"]),
        "roster": {"group": roster_group, "add": pd_stats.get("subjects_grouped", 0)},
        "patrols": {"total": len(patrols), "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
                    "already_done": len(ledger_done), "events": counts.get("observations", 0),
                    "track_points": counts.get("track_points", 0)},
    }
```

Check `_sync_subjects` in er-smart-sync's `patrol_datamodel.py` (around line 336) for the exact keys a subject change carries (`id`, and whether it has `name` or `value`); adjust `_entry` for subjects so the label is the subject's name when present.

- [ ] **Step 4: Run the test file**

Run: `uv run pytest tests/test_findings.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add web/findings.py tests/test_findings.py
git commit -m "Findings and plan builders for hosted loads"
```

### Task B7: The load job

**Files:**
- Create: `web/load_job.py`
- Test: `tests/test_load_job.py`

**Interfaces:**
- Consumes: store methods (Task B4), `findings` (Task B6), `er_site.check_token` (Task B3), er-smart-sync 0.9.0 (Part A).
- Produces: `main(load_id: str, mode: str) -> int` and `Runner`. The job talks to er-smart-sync only through a `Migration` object so tests can substitute one:

```python
class Migration:                      # duck-typed; ErSmartSyncMigration is the real one
    dry_calls: list                   # DryRunERClient.calls, empty for a real run
    def push_datamodel(self) -> dict                      # synchronizer datamodel_stats
    def patrol_datamodel(self, out_dir: Path) -> tuple    # (checklist dicts, stats dict, changes list)
    def preflight(self) -> dict                           # the dict render_json produces
    def patrols(self) -> list                             # bundle patrols: dicts with uuid, id, start_date
    def counts(self) -> dict                              # manifest counts
    def ledger_done(self) -> set                          # patrol uuids with every stage done
    def import_patrols(self, progress, stop) -> dict      # {"imported": [...], "failed": {uuid: err}, "stopped_early": bool}

def make_migration(*, bundle_dir: Path, load_dir: Path, host: str, token: str, options: dict,
                   dry_run: bool, ca_identifier: str) -> Migration
```

`Runner(store, load_id, mode, *, work: Path, migration_factory=make_migration, check_token=er_site.check_token, clock=time.monotonic, env=os.environ)` with `run() -> int`. Exit codes: 0 for every recorded outcome (planned, done, needs_attention, continuing, failed), 2 when the load doc is missing.

`ca_identifier` is `"smart-" + <ca_id from the export entry>` lowercased, non-alphanumerics replaced by `-`, cut to 30 characters. `event_type_prefix` for preflight and import is `"smart-ca-import"` without a configurable model and `f"smart-ca-import_{cm_uuid}"` with one (the CLI's `_FILE_BASED_CA_UUID` convention).

- [ ] **Step 1: Write the failing tests**

`tests/test_load_job.py`:

```python
"""The load job: stages in order, the stop rule, continuation, and every
exit path recording an outcome on the load."""
from __future__ import annotations

import importlib
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("fastapi")

OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}
EXPORT = [{"ca_id": "050500", "dir": "ALPHA", "name": "Albay", "languages": ["en"], "default_language": "en",
           "configurable_models": [{"uuid": "abc", "label": "Mobile"}], "patrols": 3, "timezone": "Asia/Manila"}]
TEAM = {"code": "team", "title": "Create the patrol team Alpha", "steps": ["Admin > Teams."]}
ICONS = {"code": "patrol_type_icons", "title": "Pick icons", "steps": ["Admin > Patrol types."]}
PATROLS = [{"uuid": "u1", "id": "P-1", "start_date": "2019-03-04"}, {"uuid": "u2", "id": "P-2", "start_date": "2019-03-05"},
           {"uuid": "u3", "id": "P-3", "start_date": "2019-03-06"}]


class FakeMigration:
    def __init__(self, *, checklist=(), preflight=None, failed=None, per_patrol_seconds=0, clock=None, raise_in=None):
        self.dry_calls = []
        self.checklist = list(checklist)
        self.preflight_report = preflight or {"blocking": [], "warnings": []}
        self.failed = failed or {}
        self.calls = []
        self.per_patrol_seconds = per_patrol_seconds
        self.clock = clock
        self.raise_in = raise_in
        self.done = set()

    def _call(self, name):
        self.calls.append(name)
        if self.raise_in == name:
            raise RuntimeError(f"boom in {name}")

    def push_datamodel(self):
        self._call("push_datamodel"); return {"event_types_created": 2, "event_types_unchanged": 0}

    def patrol_datamodel(self, out_dir):
        self._call("patrol_datamodel")
        (Path(out_dir) / "checklist.md").write_text("# checklist")
        return self.checklist, {"schema_written": True, "subjects_grouped": 1}, [{"kind": "patrol_type", "action": "created", "value": "patrol_foot"}]

    def preflight(self):
        self._call("preflight"); return self.preflight_report

    def patrols(self):
        return PATROLS

    def counts(self):
        return {"observations": 9, "track_points": 300}

    def ledger_done(self):
        return set(self.done)

    def import_patrols(self, progress, stop):
        self._call("import_patrols")
        imported, stopped_early = [], False
        for i, p in enumerate(PATROLS):
            if stop.is_set():
                stopped_early = True
                break
            if self.clock is not None:
                self.clock.advance(self.per_patrol_seconds)
            if p["uuid"] not in self.failed:
                imported.append(p["uuid"]); self.done.add(p["uuid"])
            progress({"total": len(PATROLS), "done": i + 1, "failed": sum(1 for u in self.failed if u in [q["uuid"] for q in PATROLS[:i + 1]]), "already_imported": 0})
        return {"imported": imported, "failed": dict(self.failed), "stopped_early": stopped_early}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("store", "load_job", "findings", "er_site"):
        sys.modules.pop(m, None)
    store = importlib.import_module("store").get_store()
    load_job = importlib.import_module("load_job")
    ds = store.create({"name": "x", "source_name": "b.zip", "status": "ready", "export": EXPORT,
                       "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00", **OWNER})
    b = store._p(ds) / "export" / "ALPHA" / "bundle"
    b.mkdir(parents=True)
    (b / "manifest.json").write_text(json.dumps({"counts": {"observations": 9, "track_points": 300}}))
    site = store.create_site({"name": "s", "url": "x.pamdas.org", "created_at": "2026-10-21T00:00:00+00:00", **OWNER}, "tok")
    return store, load_job, ds, site, tmp_path


def _load(store, ds, site, status, **extra):
    return store.create_load({"dataset_id": ds, "ca_id": "ALPHA", "site_id": site, "status": status, "stage": None,
                              "options": {"language": "en", "configurable_model": None, "roster_group": "Rangers"},
                              "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00",
                              "continuations": 0, "findings": [], **OWNER, **extra})


def _run(env, mode, migration, status, clock=None, env_vars=None, check_token=lambda host, token: "ops"):
    store, load_job, ds, site, tmp = env
    id = _load(store, ds, site, status)
    seen = {}
    factory = lambda **kw: seen.update(kw) or migration
    runner = load_job.Runner(store, id, mode, work=tmp / "work", migration_factory=factory, check_token=check_token,
                             clock=clock or Clock(), env={"LOAD_SOFT_DEADLINE_SECONDS": "100", "LOAD_MAX_CONTINUATIONS": "2", **(env_vars or {})})
    rc = runner.run()
    return rc, store.get_load(id), seen


def test_plan_mode_writes_the_plan_and_imports_nothing(env):
    m = FakeMigration(checklist=[ICONS])
    rc, load, seen = _run(env, "plan", m, "planning")
    assert rc == 0 and load["status"] == "planned" and load["stage"] == "import"
    assert m.calls == ["push_datamodel", "patrol_datamodel", "preflight"]
    assert seen["dry_run"] is True and seen["host"] == "x.pamdas.org" and seen["token"] == "tok"
    assert seen["ca_identifier"] == "smart-050500" and seen["options"]["roster_group"] == "Rangers"
    assert load["plan"]["patrols"] == {"total": 3, "first": "2019-03-04", "last": "2019-03-06", "already_done": 0,
                                       "events": 9, "track_points": 300}
    assert [f["code"] for f in load["findings"]] == ["patrol_type_icons"]
    store = env[0]
    assert store.get_load_file(load["dataset_id"], load["id"], "plan.json") is not None
    assert store.get_load_file(load["dataset_id"], load["id"], "checklist.json") is not None


def test_plan_mode_with_blocking_findings_is_still_planned(env):
    rc, load, _ = _run(env, "plan", FakeMigration(checklist=[TEAM]), "planning")
    assert load["status"] == "planned" and load["findings"][0]["severity"] == "blocking"


def test_run_stops_after_patrol_datamodel_on_a_blocking_item(env):
    m = FakeMigration(checklist=[TEAM])
    rc, load, _ = _run(env, "run", m, "queued")
    assert rc == 0 and load["status"] == "needs_attention" and load["stage"] == "patrol_datamodel"
    assert m.calls == ["push_datamodel", "patrol_datamodel"]
    assert load["findings"][0]["code"] == "team"


def test_run_stops_after_preflight_on_a_blocking_finding(env):
    pre = {"blocking": [{"code": "team_missing", "level": "blocking", "message": "m", "fix": "f", "count": 1,
                         "examples": [], "affected_patrols": ["u1"]}], "warnings": []}
    m = FakeMigration(checklist=[ICONS], preflight=pre)
    rc, load, _ = _run(env, "run", m, "queued")
    assert load["status"] == "needs_attention" and load["stage"] == "preflight"
    assert "import_patrols" not in m.calls
    assert [f["code"] for f in load["findings"]] == ["patrol_type_icons", "team_missing"]


def test_run_imports_when_only_warnings_remain(env):
    m = FakeMigration(checklist=[ICONS])
    rc, load, _ = _run(env, "run", m, "queued")
    assert load["status"] == "done" and load["stage"] == "import"
    assert m.calls[-1] == "import_patrols"
    assert load["progress"] == {"patrols_total": 3, "done": 3, "failed": 0, "skipped": 0, "events": 9, "track_points": 300}
    assert "patrol_type_icons" in [f["code"] for f in load["findings"]]
    store = env[0]
    assert store.get_load_file(load["dataset_id"], load["id"], "log.txt") is not None
    assert load["log_tail"]


def test_failed_patrols_need_attention(env):
    m = FakeMigration(failed={"u2": "500 on the track"})
    rc, load, _ = _run(env, "run", m, "queued")
    assert load["status"] == "needs_attention"
    f = [f for f in load["findings"] if f["code"] == "patrols_failed"][0]
    assert f["affected"]["patrols"] == ["u2"] and "P-2: 500 on the track" in f["detail"]
    assert load["progress"]["failed"] == 1


def test_the_soft_deadline_stops_and_continues(env, monkeypatch):
    store = env[0]
    starts = []
    monkeypatch.setattr(store, "start_load", lambda id, mode: starts.append((id, mode)) or "exec-2")
    clock = Clock()
    m = FakeMigration(per_patrol_seconds=60, clock=clock)
    rc, load, _ = _run(env, "run", m, "queued", clock=clock)
    assert load["status"] == "continuing" and load["continuations"] == 1
    assert starts == [(load["id"], "run")]
    assert load["progress"]["done"] < 3


def test_too_many_continuations_fail(env, monkeypatch):
    store, load_job, ds, site, tmp = env
    monkeypatch.setattr(store, "start_load", lambda id, mode: "exec-3")
    clock = Clock()
    id = _load(store, ds, site, "queued", continuations=2)
    m = FakeMigration(per_patrol_seconds=60, clock=clock)
    runner = load_job.Runner(store, id, "run", work=tmp / "work", migration_factory=lambda **kw: m,
                             check_token=lambda h, t: "ops", clock=clock,
                             env={"LOAD_SOFT_DEADLINE_SECONDS": "100", "LOAD_MAX_CONTINUATIONS": "2"})
    assert runner.run() == 0
    load = store.get_load(id)
    assert load["status"] == "failed" and "not finishing" in load["error"]


def test_an_exception_in_a_stage_records_failed(env):
    rc, load, _ = _run(env, "run", FakeMigration(raise_in="preflight"), "queued")
    assert load["status"] == "failed" and "boom in preflight" in load["error"] and load["stage"] == "preflight"


def test_a_rejected_token_needs_attention(env):
    import er_site

    def rejected(host, token):
        raise er_site.TokenRejected("401 Unauthorized")

    m = FakeMigration()
    rc, load, _ = _run(env, "run", m, "queued", check_token=rejected)
    assert load["status"] == "needs_attention" and load["findings"][0]["code"] == "site_token_rejected"
    assert m.calls == []


def test_a_missing_site_fails(env):
    store, load_job, ds, site, tmp = env
    id = _load(store, ds, site, "queued")
    store.delete_site(site)
    runner = load_job.Runner(store, id, "run", work=tmp / "work", migration_factory=lambda **kw: FakeMigration(),
                             check_token=lambda h, t: "ops", clock=Clock(), env={})
    assert runner.run() == 0
    assert store.get_load(id)["status"] == "failed" and "site" in store.get_load(id)["error"].lower()


def test_a_missing_load_exits_2(env):
    store, load_job, ds, site, tmp = env
    assert load_job.Runner(store, "nope", "run", work=tmp / "work", migration_factory=lambda **kw: FakeMigration(),
                           check_token=lambda h, t: "ops", clock=Clock(), env={}).run() == 2


def test_a_claimed_slot_is_marked_running_with_a_start_time(env):
    store, load_job, ds, site, tmp = env
    id = _load(store, ds, site, "queued")
    m = FakeMigration()
    seen_running = {}
    real_update = store.update_load

    def spy(load_id, **fields):
        if fields.get("status") == "running":
            seen_running.update(fields)
        real_update(load_id, **fields)

    store.update_load = spy
    load_job.Runner(store, id, "run", work=tmp / "work", migration_factory=lambda **kw: m,
                    check_token=lambda h, t: "ops", clock=Clock(), env={}).run()
    assert seen_running.get("started_at")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_load_job.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'load_job'`

- [ ] **Step 3: Implement `web/load_job.py`: the runner**

```python
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
FILE_BASED_CA_UUID = "smart-ca-import"


def ca_identifier(ca_id: str) -> str:
    """The ER event-category identifier: smart-<ca id>, made safe (2-30 chars of [A-Za-z0-9_-])."""
    s = re.sub(r"[^a-z0-9_-]+", "-", f"smart-{ca_id or 'ca'}".lower()).strip("-")
    return (s if len(s) >= 2 else "smart-ca")[:30]


class Runner:
    def __init__(self, store, load_id, mode, *, work: Path, migration_factory=None, check_token=None,
                 clock=time.monotonic, env=None):
        self.store, self.load_id, self.mode = store, load_id, mode
        self.work = Path(work)
        self.migration_factory = migration_factory or make_migration
        self.check_token = check_token or default_check_token
        self.clock = clock
        env = os.environ if env is None else env
        self.soft_deadline = int(env.get("LOAD_SOFT_DEADLINE_SECONDS", 79200))
        self.max_continuations = int(env.get("LOAD_MAX_CONTINUATIONS", 10))
        self.log_lines: list = []
        self.load_dir: Path | None = None
        self.started = self.clock()

    # ---- bookkeeping
    def _update(self, **fields):
        self.store.update_load(self.load_id, **fields)

    def _log(self, line: str):
        print(line, flush=True)
        self.log_lines.append(line)
        if self.load_dir:
            with open(self.load_dir / "log.txt", "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _tail(self) -> str:
        return "\n".join(self.log_lines[-LOG_TAIL:])

    def _push_files(self):
        """Everything in the load's folder goes back to the store: ledger,
        checklist, run records, plan, findings, log."""
        if not self.load_dir:
            return
        for p in sorted(self.load_dir.iterdir()):
            if p.is_file():
                self.store.put_load_file(self.dataset_id, self.load_id, p.name, p)

    def _finish(self, status: str, **fields):
        self._push_files()
        self._update(status=status, log_tail=self._tail(), **fields)
        self._log(f"load {self.load_id}: {status}")

    # ---- the run
    def run(self) -> int:
        load = self.store.get_load(self.load_id)
        if not load:
            print(f"no load {self.load_id}", file=sys.stderr)
            return 2
        self.dataset_id = load["dataset_id"]
        self._update(status="running", error=None, started_at=now())
        self.work.mkdir(parents=True, exist_ok=True)
        findings: list = []
        stage = None
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
            self._log(f"{self.mode}: {entry.get('name')} ({entry.get('ca_id')}) -> {site['url']} "
                      f"(continuation {load.get('continuations', 0)})")
            try:
                who = self.check_token(site["url"], token)
            except TokenRejected as e:
                self._finish("needs_attention", stage="datamodel", findings=[F.token_rejected(str(e))])
                return 0
            self._log(f"token works as {who}")
            export_dir = self.store.fetch_export(self.dataset_id, load["ca_id"], self.work / "export")
            dry = self.mode == "plan"
            m = self.migration_factory(bundle_dir=Path(export_dir) / "bundle", load_dir=self.load_dir, host=site["url"],
                                       token=token, options=load["options"], dry_run=dry,
                                       ca_identifier=ca_identifier(entry.get("ca_id")))
            del token

            stage = "datamodel"
            self._update(stage=stage)
            dm_stats = m.push_datamodel()
            self._log(f"datamodel: {dm_stats}")

            stage = "patrol_datamodel"
            self._update(stage=stage)
            checklist, pd_stats, pd_changes = m.patrol_datamodel(self.load_dir)
            (self.load_dir / "checklist.json").write_text(json.dumps(checklist, indent=1))
            findings += F.from_checklist(checklist)
            self._log(f"patrol-datamodel: {len(checklist)} checklist item(s)")
            if not dry and F.has_blocking(findings):
                self._finish("needs_attention", stage=stage, findings=findings)
                return 0

            stage = "preflight"
            self._update(stage=stage, findings=findings)
            report = m.preflight()
            findings += F.from_preflight(report)
            self._log(f"preflight: {len(report.get('blocking') or [])} blocking, {len(report.get('warnings') or [])} warning(s)")
            if not dry and F.has_blocking(findings):
                self._finish("needs_attention", stage=stage, findings=findings)
                return 0

            stage = "import"
            self._update(stage=stage, findings=findings)
            patrols = m.patrols()
            if dry:
                plan = F.build_plan(datamodel_stats=dm_stats, dry_calls=m.dry_calls, pd_changes=pd_changes, pd_stats=pd_stats,
                                    roster_group=load["options"].get("roster_group"), patrols=patrols,
                                    ledger_done=m.ledger_done(), counts=m.counts())
                (self.load_dir / "plan.json").write_text(json.dumps(plan, indent=1))
                (self.load_dir / "findings.json").write_text(json.dumps(findings, indent=1))
                self._finish("planned", stage=stage, findings=findings, plan=plan)
                return 0
            return self._import(m, load, findings, patrols)
        except Exception as e:  # noqa: BLE001
            logging.exception("load %s failed", self.load_id)
            self._log(f"error: {type(e).__name__}: {e}")
            self._finish("failed", stage=stage, error=f"{type(e).__name__}: {e}", findings=findings)
            return 0
        finally:
            if not os.environ.get("JOB_KEEP_WORK"):
                shutil.rmtree(self.work, ignore_errors=True)

    def _import(self, m, load, findings, patrols) -> int:
        counts = m.counts()
        total = len(patrols)
        stop = threading.Event()
        last_push = {"t": self.clock(), "n": 0}
        last: dict = {}

        def progress(p: dict):
            last.update(p)
            self._update(progress={"patrols_total": total, "done": p["done"], "failed": p["failed"],
                                   "skipped": p.get("already_imported", 0), "events": counts.get("observations", 0),
                                   "track_points": counts.get("track_points", 0)})
            if self.clock() - self.started >= self.soft_deadline:
                stop.set()
            if p["done"] - last_push["n"] >= 10 or self.clock() - last_push["t"] >= 30:
                self._push_files()  # the ledger above all: what a continuation resumes from
                last_push.update(t=self.clock(), n=p["done"])

        watcher = threading.Thread(target=self._watch_deadline, args=(stop,), daemon=True)
        watcher.start()
        result = m.import_patrols(progress, stop)
        stop.set()
        ids = {p["uuid"]: p.get("id") or p["uuid"] for p in patrols}
        findings = findings + F.from_failed_patrols(result.get("failed") or {}, ids)
        self._update(progress={"patrols_total": total, "done": len(result.get("imported") or []) + len(result.get("failed") or {}),
                               "failed": len(result.get("failed") or {}), "skipped": last.get("already_imported", 0),
                               "events": counts.get("observations", 0), "track_points": counts.get("track_points", 0)})
        if result.get("stopped_early"):
            n = load.get("continuations", 0) + 1
            if n > self.max_continuations:
                self._finish("failed", stage="import", findings=findings,
                             error=f"the import is not finishing after {self.max_continuations} continuations")
                return 0
            self._finish("continuing", stage="import", findings=findings, continuations=n, claimed_at=now())
            execution = self.store.start_load(self.load_id, "run")
            self._update(execution=execution)
            return 0
        if F.has_blocking(findings):
            self._finish("needs_attention", stage="import", findings=findings)
        else:
            self._finish("done", stage="import", findings=findings)
        return 0

    def _watch_deadline(self, stop: threading.Event):
        """Set the stop event at the soft deadline even while a patrol is in
        flight, so a slow one cannot push the run past the hard cap."""
        while not stop.is_set():
            if self.clock() - self.started >= self.soft_deadline:
                stop.set()
                return
            time.sleep(5)
```

The final `progress` update in `_import` uses `imported + failed` for `done` and the last callback's `already_imported` for `skipped`, so the counts a user sees at the end match what the callback reported.

- [ ] **Step 4: Implement the real migration and `main`**

Append to `web/load_job.py`:

```python
class ErSmartSyncMigration:
    """er-smart-sync, called as a library, for one bundle against one site."""

    def __init__(self, *, bundle_dir, load_dir, host, token, options, dry_run, ca_identifier, er_client=None):
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
        self.dry = dry_run
        self.client = DryRunERClient(client) if dry_run else client
        self.dry_calls = self.client.calls if dry_run else []
        self.api = ERPatrolAPI(self.client)
        self.ledger = ImportLedger(self.load_dir / "import-ledger.json",
                                   f"{host}|{self.bundle.ca_uuid}", read_only=dry_run)
        self.ns = namespace(self.endpoint, self.bundle.ca_uuid, None)
        self.event_type_prefix = f"{FILE_BASED_CA_UUID}_{self.cm_uuid}" if self.cm_uuid else FILE_BASED_CA_UUID

    def _cm_file(self):
        if not self.cm_uuid:
            return None
        safe = re.sub(r"[^A-Za-z0-9_-]", "", self.cm_uuid)
        f = self.bundle_dir.parent / f"configurable_model_{safe}.xml"
        return str(f) if f.is_file() else None

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
            raise RuntimeError("patrol-datamodel: " + "; ".join(result.stats.errors))
        stats = {k: getattr(result.stats, k) for k in ("schema_written", "schema_skipped", "subjects_grouped")}
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
        opts = patrol_import.ImportOptions(event_type_prefix=self.event_type_prefix, event_type_version="v2",
                                           timezone=self.bundle.manifest.timezone.get("name"))
        result = patrol_import.run_import(self.api, self.bundle, endpoint=self.endpoint, ledger=self.ledger, opts=opts,
                                          ns=self.ns, importer_version=pkg_version("er-smart-sync"),
                                          report=getattr(self, "_report", None), progress=progress, stop=stop)
        return {"imported": list(result.imported), "failed": dict(result.failed), "stopped_early": result.stopped_early}


def make_migration(**kw):
    return ErSmartSyncMigration(**kw)


def main(load_id: str, mode: str) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    work = Path(os.environ.get("JOB_WORK_DIR") or tempfile.mkdtemp(prefix="smart-able-load-"))
    return Runner(get_store(), load_id, mode, work=work / load_id).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.environ["LOAD_ID"],
                  sys.argv[2] if len(sys.argv) > 2 else os.environ.get("MODE", "run")))
```

Check `Bundle.manifest` in er-smart-sync's `bundle/__init__.py` (the `Manifest` dataclass at line 26) for the attribute names `timezone` and `counts` and adjust. The er-smart-sync log output (its `logging` calls) should reach `log.txt`: in `main`, add a `logging.FileHandler` on the root logger pointing at the load dir once `Runner` has created it; simplest is a handler that appends to `self.log_lines` via a small `logging.Handler` subclass installed in `Runner.run` after `self.load_dir` is set, and removed in `finally`.

- [ ] **Step 5: Run the test file**

Run: `uv run pytest tests/test_load_job.py -v`
Expected: all PASS. The fake-migration tests never import er-smart-sync.

- [ ] **Step 6: Commit**

```bash
git add web/load_job.py tests/test_load_job.py
git commit -m "Load job: plan and run the migration, stop on findings, continue past the soft deadline"
```

### Task B8: The UI

**Files:**
- Modify: `web/templates/index.html`, `web/static/app.js`, `web/static/app.css`
- Test: manual, against the local backend (steps below); the API is covered by Tasks B3 and B5.

**Interfaces:**
- Consumes: `/api/sites`, `/api/datasets` (with `export`), `/api/datasets/{id}/loads`, `/api/loads/{id}`, `/api/loads/{id}/run`, `/api/loads/{id}/replan`, `DELETE /api/loads/{id}`, `/api/loads/{id}/files/{name}`.

- [ ] **Step 1: Template**

In `index.html`, inside `#appUI`, add a Sites panel between the upload panel and the datasets panel, and a hidden load page section after the datasets panel:

```html
      <div class="panel">
        <h2>EarthRanger sites</h2>
        <p class="muted tiny">Sites a dataset can be loaded into. A site you share lets that person write to it with your token.</p>
        <form id="siteForm" class="row">
          <input type="text" id="siteName" placeholder="Name (e.g. phinney staging)" required>
          <input type="text" id="siteUrl" placeholder="site.pamdas.org" required>
          <input type="password" id="siteToken" placeholder="API token" required autocomplete="off">
          <button type="submit" class="primary" id="siteBtn"><span class="mi" aria-hidden="true">add</span>Add site</button>
        </form>
        <p class="tiny" id="siteError"></p>
        <div id="sites"></div>
      </div>
```

```html
      <section id="loadPage" class="panel" hidden>
        <div class="row"><button class="ghost" id="loadBack"><span class="mi" aria-hidden="true">arrow_back</span>Datasets</button><h2 id="loadTitle"></h2></div>
        <div id="loadStages" class="stages"></div>
        <div id="loadActions" class="row"></div>
        <div id="loadFindings"></div>
        <div id="loadPlan"></div>
        <div id="loadProgress"></div>
      </section>
```

- [ ] **Step 2: Styles**

Append to `app.css`:

```css
.stages { display: flex; gap: 6px; margin: 10px 0; flex-wrap: wrap; }
.stage { padding: 4px 10px; border-radius: 99px; background: var(--chip); font-size: 12px; }
.stage.done { background: var(--accent); color: var(--accent-ink); }
.stage.current { outline: 2px solid var(--brand); }
.stage.stopped { background: #f6d9d3; color: var(--danger); }
.finding { border-left: 3px solid var(--line); padding: 6px 10px; margin: 8px 0; }
.finding.blocking { border-color: var(--danger); }
.finding.warning { border-color: #c99a2e; }
.finding pre { white-space: pre-wrap; font-size: 12px; margin: 4px 0; }
.plan details { margin: 4px 0; }
.plan summary { cursor: pointer; }
.pill.needs_attention { background: #f6e3c4; color: #6b4b00; }
.pill.done { background: var(--accent); color: var(--accent-ink); }
.pill.planned { background: #dde8f6; color: #1d3f6e; }
.loads { margin-top: 6px; font-size: 12.5px; }
.loads a { cursor: pointer; text-decoration: underline; }
```

- [ ] **Step 3: Sites in `app.js`**

Add after `loadList`:

```js
// ---- sites
async function loadSites() {
  const list = await api('/api/sites');
  const host = $('#sites');
  if (!list.length) { host.innerHTML = '<p class="muted tiny">No sites yet.</p>'; return list; }
  host.innerHTML = '<table><thead><tr><th>Site</th><th>Host</th><th>Token</th><th>Owner</th><th>Shared with</th><th></th></tr></thead><tbody>' +
    list.map(s => '<tr data-id="' + s.id + '">' +
      '<td><b>' + esc(s.name) + '</b></td><td>' + esc(s.url) + '</td>' +
      '<td class="tiny">…' + esc(s.token_hint) + ' as ' + esc(s.checked_as) + '</td>' +
      '<td>' + (s.mine ? 'you' : esc(s.owner_email)) + '</td>' +
      '<td>' + ((s.shared_with || []).map(esc).join('<br>') || '<span class="tiny">—</span>') + '</td>' +
      '<td class="actions">' +
        (s.mine ? '<button data-act="siteShare"><span class="mi" aria-hidden="true">share</span>Share</button> ' : '') +
        (s.mine ? '<button data-act="siteDelete" class="danger" title="Remove this site and its token"><span class="mi" aria-hidden="true">delete</span></button>' : '') +
      '</td></tr>').join('') + '</tbody></table>';
  host.querySelectorAll('button[data-act]').forEach(b => b.onclick = () => siteAction(b.dataset.act, list.find(s => s.id === b.closest('tr').dataset.id)));
  return list;
}

async function siteAction(act, s) {
  try {
    if (act === 'siteShare') return shareDialog(s, '/api/sites/', 'People you share with can load datasets into this site using your token.');
    if (act === 'siteDelete') { if (!confirm('Remove "' + s.name + '"? Loads already made keep their records but cannot be continued.')) return; await api('/api/sites/' + s.id, { method: 'DELETE' }); return loadSites(); }
  } catch (e) { alert(e.message); }
}

async function addSite(ev) {
  ev.preventDefault();
  const btn = $('#siteBtn'); btn.disabled = true; $('#siteError').textContent = 'Checking the token…';
  try {
    await api('/api/sites', { method: 'POST', body: JSON.stringify({ name: $('#siteName').value, url: $('#siteUrl').value, token: $('#siteToken').value }) });
    $('#siteForm').reset(); $('#siteError').textContent = '';
    loadSites();
  } catch (e) { $('#siteError').textContent = e.message; }
  finally { btn.disabled = false; }
}
```

Generalize `shareDialog(d)` to `shareDialog(d, base = '/api/datasets/', note)` using `base + d.id + '/share'` and the note text in place of the fixed sentence, and re-render with `loadList()` or `loadSites()` depending on `base`. In `boot`, add `$('#siteForm').onsubmit = addSite;` and `$('#loadBack').onclick = showDatasets;`. In `showApp`, call `loadSites()` after `loadList()`.

- [ ] **Step 4: The load form and loads on the card**

In `loadList`, after the Open button add, for `ready` datasets with a non-empty `export`:

```js
        (d.status === 'ready' && (d.export || []).length ? '<button data-act="load"><span class="mi" aria-hidden="true">cloud_upload</span>Load into EarthRanger</button> ' : '') +
        (d.status === 'ready' && !(d.export || []).length ? '<span class="tiny" title="Run the extraction again to build the migration bundle">re-extract to enable loading</span> ' : '') +
```

and under the status cell, a `loads` list fetched lazily: after rendering, for each `ready` dataset call `renderLoads(d.id)`:

```js
async function renderLoads(id) {
  const loads = await api('/api/datasets/' + id + '/loads');
  const td = $('tr[data-id="' + id + '"] td:nth-child(3)');
  if (!td || !loads.length) return;
  td.insertAdjacentHTML('beforeend', '<div class="loads">' + loads.map(l =>
    '<div><a data-load="' + l.id + '">' + esc(l.site ? l.site.url : 'removed site') + ' · ' + esc(l.ca_id) + '</a> <span class="pill ' + esc(l.status) + '">' + esc(l.status) + '</span>' +
    (l.progress && ['running', 'continuing', 'needs_attention', 'done'].includes(l.status) ? ' <span class="tiny">' + l.progress.done + ' of ' + l.progress.patrols_total + ' patrols</span>' : '') + '</div>').join('') + '</div>');
  td.querySelectorAll('a[data-load]').forEach(a => a.onclick = () => showLoad(a.dataset.load));
  if (loads.some(l => l.held)) { clearTimeout(pollTimer); pollTimer = setTimeout(loadList, 5000); }
}
```

In `action`, add:

```js
    if (act === 'load') return loadDialog(d);
```

```js
async function loadDialog(d) {
  const sites = await api('/api/sites');
  if (!sites.length) return alert('Register an EarthRanger site first.');
  const render = () => {
    const ca = d.export.find(e => e.dir === $('#ldCa').value) || d.export[0];
    $('#ldLang').innerHTML = ca.languages.map(l => '<option' + (l === ca.default_language ? ' selected' : '') + '>' + esc(l) + '</option>').join('');
    $('#ldCm').innerHTML = '<option value="">none</option>' + ca.configurable_models.map(m => '<option value="' + esc(m.uuid) + '">' + esc(m.label) + '</option>').join('');
  };
  dialog('Load "' + d.name + '" into EarthRanger',
    '<p class="muted tiny">First a plan is made without writing anything. You confirm it before the site is changed.</p>' +
    '<form id="ldForm" class="col">' +
    '<label>Conservation area <select id="ldCa">' + d.export.map(e => '<option value="' + esc(e.dir) + '">' + esc(e.name || e.ca_id) + ' (' + e.patrols + ' patrols)</option>').join('') + '</select></label>' +
    '<label>Site <select id="ldSite">' + sites.map(s => '<option value="' + esc(s.id) + '">' + esc(s.name) + ' · ' + esc(s.url) + '</option>').join('') + '</select></label>' +
    '<label>Label language <select id="ldLang"></select></label>' +
    '<label>Configurable model <select id="ldCm"></select></label>' +
    '<label>Roster group <input type="text" id="ldRoster" placeholder="optional; default: the patrol configuration\'s first member group"></label>' +
    '<div class="row right"><button type="submit" class="primary">Make the plan</button></div></form>');
  render(); $('#ldCa').onchange = render;
  $('#ldForm').onsubmit = async ev => {
    ev.preventDefault();
    try {
      const l = await api('/api/datasets/' + d.id + '/loads', { method: 'POST', body: JSON.stringify({ ca_id: $('#ldCa').value, site_id: $('#ldSite').value,
        options: { language: $('#ldLang').value, configurable_model: $('#ldCm').value || null, roster_group: $('#ldRoster').value } }) });
      $('#modal').hidden = true; showLoad(l.id);
    } catch (e) { alert(e.message); }
  };
}
```

Add `.col { display: flex; flex-direction: column; gap: 8px; } .col label { display: flex; flex-direction: column; gap: 2px; font-size: 12.5px; } .col select, .col input { padding: 7px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); font: inherit; }` to `app.css`.

- [ ] **Step 5: The load page**

```js
// ---- the load page
let loadTimer = null, currentLoad = null;
function showDatasets() { clearTimeout(loadTimer); currentLoad = null; $('#loadPage').hidden = true; $('#appUI > .panel').forEach?.(p => p.hidden = false); document.querySelectorAll('#appUI > .panel').forEach(p => p.hidden = false); loadList(); }

async function showLoad(id) {
  currentLoad = id;
  document.querySelectorAll('#appUI > .panel').forEach(p => p.hidden = true);
  $('#loadPage').hidden = false;
  await renderLoad();
}

const STAGES = ['datamodel', 'patrol_datamodel', 'preflight', 'import'];
const STAGE_LABEL = { datamodel: 'Event types', patrol_datamodel: 'Patrol setup', preflight: 'Preflight', import: 'Patrols' };

async function renderLoad() {
  const l = await api('/api/loads/' + currentLoad);
  $('#loadTitle').textContent = esc(l.ca_id) + ' → ' + (l.site ? l.site.name + ' (' + l.site.url + ')' : 'removed site') + ' · ' + l.status + (l.mode === 'plan' ? '' : '');
  const idx = STAGES.indexOf(l.stage);
  const active = l.held;
  $('#loadStages').innerHTML = STAGES.map((s, i) => '<span class="stage ' +
    (i < idx || (i === idx && ['done', 'planned'].includes(l.status)) ? 'done' : i === idx && active ? 'current' : i === idx && ['needs_attention', 'failed'].includes(l.status) ? 'stopped' : '') +
    '">' + STAGE_LABEL[s] + '</span>').join('');
  const blocking = (l.findings || []).some(f => f.severity === 'blocking');
  let actions = '';
  if (!active && l.site) {
    if (l.status === 'planned' && !blocking) actions += '<button class="primary" data-run><span class="mi" aria-hidden="true">play_arrow</span>Confirm and load</button> ';
    if (l.status === 'needs_attention') actions += '<button class="primary" data-run><span class="mi" aria-hidden="true">play_arrow</span>Continue</button> ';
    if (['planned', 'needs_attention', 'failed', 'done'].includes(l.status)) actions += '<button data-replan><span class="mi" aria-hidden="true">refresh</span>Plan again</button> ';
  }
  if (!active) actions += '<button class="danger" data-del><span class="mi" aria-hidden="true">delete</span>Delete this load</button>';
  if (l.error) actions += '<div class="tiny" style="color:var(--danger)">' + esc(l.error) + '</div>';
  $('#loadActions').innerHTML = actions;
  const run = $('#loadActions [data-run]'); if (run) run.onclick = async () => { try { await api('/api/loads/' + l.id + '/run', { method: 'POST' }); renderLoad(); } catch (e) { alert(e.message); } };
  const re = $('#loadActions [data-replan]'); if (re) re.onclick = async () => { try { await api('/api/loads/' + l.id + '/replan', { method: 'POST' }); renderLoad(); } catch (e) { alert(e.message); } };
  const del = $('#loadActions [data-del]'); if (del) del.onclick = async () => { if (!confirm('Delete this load\'s records? Nothing in EarthRanger is removed.')) return; await api('/api/loads/' + l.id, { method: 'DELETE' }); showDatasets(); };
  const fs = (l.findings || []).slice().sort((a, b) => (a.severity === 'blocking' ? 0 : 1) - (b.severity === 'blocking' ? 0 : 1));
  $('#loadFindings').innerHTML = fs.length ? '<h3>Findings</h3>' + fs.map(f => '<div class="finding ' + esc(f.severity) + '"><b>' + esc(f.title) + '</b> <span class="tiny">' + esc(f.severity) + ' · ' + esc(STAGE_LABEL[f.stage] || f.stage) + (f.affected && f.affected.count ? ' · ' + f.affected.count + ' patrols' : '') + '</span>' +
    (f.detail ? '<pre>' + esc(f.detail) + '</pre>' : '') + (f.fix ? '<div class="tiny"><b>Fix:</b> ' + esc(f.fix) + '</div>' : '') + '</div>').join('') :
    (['planned', 'done'].includes(l.status) ? '<p class="muted tiny">No findings.</p>' : '');
  $('#loadPlan').innerHTML = l.plan ? '<h3>Plan</h3><div class="plan">' + renderPlan(l.plan) + '</div>' : '';
  const p = l.progress;
  $('#loadProgress').innerHTML = (p ? '<h3>Progress</h3><p>' + p.done + ' of ' + p.patrols_total + ' patrols' + (p.failed ? ', ' + p.failed + ' failed' : '') + (p.skipped ? ', ' + p.skipped + ' already there' : '') + '</p>' : '') +
    (l.continuations ? '<p class="tiny">Continued ' + l.continuations + ' time(s) past the job limit.</p>' : '') +
    (l.log_tail ? '<details><summary class="tiny">Log tail</summary><pre class="log">' + esc(l.log_tail) + '</pre></details>' : '') +
    '<p class="tiny">Files: ' + ['plan.json', 'findings.json', 'checklist.json', 'checklist.md', 'import-ledger.json', 'log.txt'].map(n => '<a href="/api/loads/' + l.id + '/files/' + n + '" download>' + n + '</a>').join(' · ') + '</p>';
  clearTimeout(loadTimer);
  if (active) loadTimer = setTimeout(renderLoad, 4000);
}

function renderPlan(plan) {
  const group = (title, g) => {
    if (!g) return '';
    const parts = [];
    for (const k of ['create', 'update', 'deactivate']) if (Array.isArray(g[k]) && g[k].length)
      parts.push('<details><summary>' + k + ' ' + g[k].length + (g.more ? '+' : '') + '</summary><ul>' + g[k].map(e => '<li>' + esc(e.label) + ' <span class="tiny">' + esc(e.value) + '</span></li>').join('') + (g.more ? '<li class="tiny">and ' + g.more + ' more</li>' : '') + '</ul></details>');
    if (g.unchanged) parts.push('<span class="tiny">' + g.unchanged + ' unchanged</span>');
    return '<div><b>' + title + '</b> ' + (parts.join(' ') || '<span class="tiny">nothing to do</span>') + '</div>';
  };
  const p = plan.patrols || {};
  return group('Event categories', plan.event_categories) + group('Event types', plan.event_types) + group('Patrol types', plan.patrol_types) +
    '<div><b>Universal patrol fields</b> ' + esc(plan.universal_patrol_fields) + '</div>' + group('Choices', plan.choices) + group('Subjects', plan.subjects) +
    '<div><b>Roster</b> ' + (plan.roster && plan.roster.group ? esc(plan.roster.group) + ': ' : '') + ((plan.roster || {}).add || 0) + ' to add</div>' +
    '<div><b>Patrols</b> ' + p.total + (p.first ? ' from ' + esc(p.first) + ' to ' + esc(p.last) : '') + (p.already_done ? ', ' + p.already_done + ' already imported' : '') + ' · ' + p.events + ' observations · ' + p.track_points + ' track points</div>';
}
```

Remove the stray `$('#appUI > .panel').forEach?.(...)` fragment in `showDatasets` (keep the `document.querySelectorAll` line).

- [ ] **Step 6: Try it locally**

```sh
uv sync --extra web --extra dev
cd web && BACKEND=local AUTH_DISABLED=true LOAD_PYTHON=$PWD/../.venv-load/bin/python uv run uvicorn app:app --reload --port 8080
```

(`.venv-load` is the er-smart-sync venv from Task B9's local setup; without it, use the fake path: `LOAD_PYTHON` unset and expect the job to fail with `ModuleNotFoundError`, which the page shows as a `failed` load.) Register a site with a real staging token, upload the small Conservation Area export from `~/projects/smart-migration-artifacts`, press Load, read the plan, confirm, watch progress. Check: the Sites table hides the token, the load line appears on the card, the load page polls while held and stops when done, Plan again works on a done load.

- [ ] **Step 7: Commit**

```bash
git add web/templates/index.html web/static/app.js web/static/app.css
git commit -m "UI: sites, the load form, loads on the dataset card, and the load page"
```

### Task B9: Image, deployment, infrastructure, docs

**Files:**
- Modify: `web/Dockerfile.job`, `web/docker-compose.yml`, `.github/workflows/deploy.yml`, `web/infra/main.tf`, `web/DEPLOY.md`, `README.md`
- Create: `web/requirements-load.txt`

**Interfaces:**
- Produces: the load venv at `/opt/load` in the job image; Cloud Run Job `smart-able-load`; Secret Manager API and IAM; env vars on the service and both jobs.

- [ ] **Step 1: The load venv**

`web/requirements-load.txt`:

```
er-smart-sync @ git+https://github.com/PADAS/earthranger-smart-utils@v0.9.0
google-cloud-firestore>=2.20
google-cloud-storage>=2.19
google-cloud-run>=0.10
google-cloud-secret-manager>=2.20
httpx>=0.27
```

In `web/Dockerfile.job`, after the `uv sync` RUN:

```dockerfile
# er-smart-sync pins pydantic 1 and the web extra needs pydantic 2, so the
# load job gets its own venv; web/load_job.py runs under it
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* && \
    uv venv /opt/load --python 3.12 && uv pip install --python /opt/load/bin/python -r web/requirements-load.txt
```

Leave `CMD ["python", "web/job.py"]`; the load job is deployed with a command override.

For local runs, add to `web/DEPLOY.md`'s "Running locally" section:

```sh
uv venv .venv-load && uv pip install --python .venv-load/bin/python -r web/requirements-load.txt
LOAD_PYTHON=$PWD/.venv-load/bin/python   # for the service's env, so start_load uses it
```

and in `web/docker-compose.yml` set `LOAD_PYTHON=/opt/load/bin/python` in the service's environment. Add `.venv-load/` to `.gitignore`.

- [ ] **Step 2: Deploy the load job**

In `deploy.yml`, add `LOAD_JOB: smart-able-load` to `env`, and after "Deploy the extraction job":

```yaml
      - name: Deploy the load job
        run: |
          gcloud run jobs deploy ${{ env.LOAD_JOB }} \
            --image "${{ env.GCP_REGION }}-docker.pkg.dev/${{ env.GCP_PROJECT_ID }}/${{ env.AR_REPOSITORY }}/${{ env.JOB }}:${{ github.sha }}" \
            --region ${{ env.GCP_REGION }} \
            --service-account ${{ vars.GCP_RUNTIME_SERVICE_ACCOUNT }} \
            --command /opt/load/bin/python --args web/load_job.py \
            --memory 2Gi --cpu 1 --task-timeout 24h --max-retries 0 \
            --set-env-vars "BACKEND=gcp,GCP_PROJECT_ID=${{ env.GCP_PROJECT_ID }},GCP_REGION=${{ env.GCP_REGION }},GCS_BUCKET=${{ vars.GCS_BUCKET }},LOAD_JOB=${{ env.LOAD_JOB }},LOAD_SOFT_DEADLINE_SECONDS=79200,LOAD_MAX_CONTINUATIONS=10"
```

Add `LOAD_JOB=${{ env.LOAD_JOB }}` and `LOAD_STALE_AFTER_SECONDS=90000` to the service's `env_vars`.

- [ ] **Step 3: Infrastructure**

In `web/infra/main.tf`, add `"secretmanager.googleapis.com"` to the `google_project_service.apis` list (find it near the top of the file), and after `google_project_iam_member.runtime`:

```hcl
# the service creates, reads and deletes one secret per registered
# EarthRanger site; the condition keeps it to those secrets
resource "google_project_iam_member" "runtime_site_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.admin"
  member  = "serviceAccount:${google_service_account.runtime.email}"
  condition {
    title      = "smart-able site tokens only"
    expression = "resource.name.startsWith(\"projects/${var.project_number}/secrets/smart-able-site-\")"
  }
}
```

Secret resource names carry the project number, not the id; add `variable "project_number"` to `variables.tf` with a description, set it in `terraform.tfvars.example`, or read it with a `data "google_project" "current" {}` block and use `data.google_project.current.number`. Creating a secret is checked against the project, not a resource name, so the condition cannot gate `create`; `roles/secretmanager.admin` at project scope with this condition lets the runtime account create any secret but access or delete only `smart-able-site-*` ones. Note that in the comment. Run `tofu plan` and `tofu apply` from `web/infra`.

- [ ] **Step 4: Docs**

In `web/DEPLOY.md`: add rows for the load job and the two collections to "How it fits together"; a "Loading into EarthRanger" section that says what a site registration stores where, the plan/confirm flow, what `needs_attention` means, continuation and the three `LOAD_*` variables, and that deleting a dataset deletes its loads but never EarthRanger data. In "Data handling", add that site tokens live in Secret Manager under `smart-able-site-<id>`, deleted with the site. In `README.md`, change the Load row of the stage table to say the hosted app runs it (link to `web/DEPLOY.md`) and the CLI path remains. Add the local `.venv-load` setup to the "Running locally" section.

- [ ] **Step 5: Build the job image locally to prove the venv**

```sh
docker build -f web/Dockerfile.job -t smart-able-job:local .
docker run --rm smart-able-job:local /opt/load/bin/python -c "import er_smart_sync, pydantic, google.cloud.firestore; print(pydantic.VERSION)"
docker run --rm smart-able-job:local python -c "import pydantic; print(pydantic.VERSION)"
```

Expected: the first prints a 1.x version, the second a 2.x version.

- [ ] **Step 6: Commit**

```bash
git add web/Dockerfile.job web/requirements-load.txt web/docker-compose.yml .gitignore .github/workflows/deploy.yml web/infra web/DEPLOY.md README.md
git commit -m "Deploy the load job with its own er-smart-sync venv; Secret Manager for site tokens"
```

### Task B10: End-to-end plan on the local backend

**Files:**
- Test: `tests/test_load_e2e.py`

**Interfaces:**
- Consumes: everything above; er-smart-sync importable (the test skips otherwise, so it runs only under `.venv-load`'s interpreter: `.venv-load/bin/python -m pytest tests/test_load_e2e.py` after `uv pip install --python .venv-load/bin/python pytest duckdb`).

- [ ] **Step 1: Write the test**

```python
"""The whole plan path for real: a synthetic SMART database is extracted and
exported, the dataset is loaded in plan mode through er-smart-sync's dry-run
client against a fake EarthRanger, and the plan has the expected counts."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("er_smart_sync")
pytest.importorskip("fastapi")

OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}


class FakeER:
    """Reads only: an empty site. Writes never reach it (DryRunERClient)."""

    def __getattr__(self, name):
        if name.startswith("get_"):
            return lambda *a, **k: [] if "s" in name[-2:] or name.endswith("list") else {}
        raise AttributeError(name)


def test_plan_mode_end_to_end(smart_parquet, tmp_path, monkeypatch):
    from export.__main__ import main as export_main

    work = smart_parquet.parent
    site_data = work / "site" / "data"
    site_data.mkdir(parents=True)
    (site_data / "timezones.json").write_text(json.dumps({"default": "Asia/Manila", "byCa": {"ALPHA": "Asia/Manila"}}))
    assert export_main(["--work", str(work), "--site-data", str(site_data), "--source-kind", "backup", "--source-file", "x.zip"]) == 0

    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("store", "job", "load_job", "findings", "er_site"):
        sys.modules.pop(m, None)
    store = importlib.import_module("store").get_store()
    job = importlib.import_module("job")
    load_job = importlib.import_module("load_job")

    ds = store.create({"name": "alpha", "source_name": "x.zip", "status": "ready", "created_at": "2026-10-21T00:00:00+00:00",
                       "updated_at": "2026-10-21T00:00:00+00:00", **OWNER})
    store.put_export(ds, work / "export")
    export = job.describe_export(work / "export")
    store.update(ds, export=export)
    assert [e["dir"] for e in export] == ["ALPHA"] and export[0]["patrols"] == 2

    site = store.create_site({"name": "fake", "url": "fake.pamdas.org", "created_at": "2026-10-21T00:00:00+00:00", **OWNER}, "tok")
    load_id = store.create_load({"dataset_id": ds, "ca_id": "ALPHA", "site_id": site, "status": "planning", "stage": None,
                                 "options": {"language": "en", "configurable_model": None, "roster_group": None},
                                 "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00",
                                 "continuations": 0, "findings": [], **OWNER})

    def factory(**kw):
        return load_job.ErSmartSyncMigration(er_client=FakeER(), **kw)

    rc = load_job.Runner(store, load_id, "plan", work=tmp_path / "work", migration_factory=factory,
                         check_token=lambda h, t: "ops", env={}).run()
    load = store.get_load(load_id)
    assert rc == 0 and load["status"] == "planned", load.get("error")
    plan = load["plan"]
    assert plan["patrols"]["total"] == 2 and plan["patrols"]["already_done"] == 0
    assert plan["event_types"]["create"], "the dry run should plan event types for the synthetic data model"
    assert any(e["value"] == "patrol_foot" for e in plan["patrol_types"]["create"])
    codes = {f["code"] for f in load["findings"]}
    assert "team" in codes   # Team One is not on the fake site
    assert store.get_load_file(ds, load_id, "plan.json") and store.get_load_file(ds, load_id, "checklist.md")
```

- [ ] **Step 2: Run it under the load venv**

Run: `uv pip install --python .venv-load/bin/python pytest duckdb && .venv-load/bin/python -m pytest tests/test_load_e2e.py -v`
Expected: PASS. Where `FakeER` returns the wrong shape for a read (ER's list endpoints answer dicts with `results` in some erclient methods), extend `FakeER` with that method explicitly rather than loosening the assertion.

- [ ] **Step 3: Run the full suite under the project venv to show nothing else broke**

Run: `uv run pytest -q`
Expected: all PASS; `test_load_e2e.py` reports skipped there.

- [ ] **Step 4: Commit**

```bash
git add tests/test_load_e2e.py
git commit -m "End-to-end plan test through er-smart-sync's dry-run client"
```

### Task B11: Manual check against phinney staging and release

- [ ] **Step 1: Seed and compare**

Deploy with a tag (`git tag -a v0.3.0 && git push origin v0.3.0`, after merging `feat/hosted-load`). In the app: register `phinney.staging.pamdas.org` with the `smart_migration` token from `~/padas/earthranger-smart-utils/sync-phinney.yaml`; upload the Lawin backup from `~/projects/smart-migration-artifacts`; when ready, load Guinobatan (050504) with language `en`, no configurable model, roster group `Rangers`. Read the plan: the subjects and patrol types should be mostly `update`/unchanged, and `already_done` is 0 because the hosted ledger is new. Confirm. Expected within the first minutes: `needs_attention` with the seven missing small teams from the memory note, or a run that skips the 38 patrols already there (das answers duplicate ids with 500, which the importer recovers from by reading the patrol). Record what happened in `docs/decisions.md` under a dated entry, with the time one patrol took from the log.

- [ ] **Step 2: Update the memory note** on phinney's state if the site changed.
