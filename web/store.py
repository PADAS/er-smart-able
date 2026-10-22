"""Datasets: where their metadata, uploaded backups and extracted sites live,
and how an extraction is started.

A dataset is one SMART conservation-area backup or export, owned by the user
who uploaded it (owner_uid) and visible to the owner and to the emails in
shared_with, as in gundi-webhook-editor.

Two backends, chosen by BACKEND:
- gcp:   Firestore collection "datasets", a GCS bucket with
         datasets/<id>/upload/<file> and datasets/<id>/site/..., and a Cloud
         Run Job that runs the extraction.
- local: a JSON index and a directory tree under LOCAL_DIR, and the
         extraction as a background subprocess. For development and tests.

Both expose the same methods, so app.py and job.py do not care which.
"""
import json
import logging
import mimetypes
import os
import shutil
import signal
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = os.environ.get("BACKEND", "gcp")
ROOT = Path(__file__).resolve().parent.parent  # the smart-able checkout
DATASET_FIELDS = ("name", "owner_uid", "owner_email", "shared_with", "status", "created_at", "updated_at",
                  "source_name", "source_size", "cas", "db_version", "counts", "error", "execution", "log_tail",
                  "extract_claimed_at", "started_at", "export")
SITE_FIELDS = ("name", "url", "owner_uid", "owner_email", "shared_with", "secret_name", "token_hint",
               "checked_at", "checked_as", "created_at", "updated_at")

now = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")

# An extraction holds its dataset while queued or running. A run lasts at most
# EXTRACT_TIMEOUT: Cloud Run enforces it as --task-timeout in deploy.yml, the
# local backend kills its worker. A run killed outright never records
# "failed", so once EXTRACT_STALE_AFTER has passed since the claim (queued) or
# the job's start (running), the hold lapses. It must exceed EXTRACT_TIMEOUT.
EXTRACT_ACTIVE = ("queued", "running")
EXTRACT_TIMEOUT = timedelta(seconds=int(os.environ.get("EXTRACT_TIMEOUT_SECONDS", 7200)))
EXTRACT_STALE_AFTER = timedelta(seconds=int(os.environ.get("EXTRACT_STALE_AFTER_SECONDS", 9000)))


def extract_in_progress(doc: dict) -> bool:
    status = doc.get("status")
    if status not in EXTRACT_ACTIVE:
        return False
    since = doc.get("started_at") if status == "running" else doc.get("extract_claimed_at")
    try:
        since = datetime.fromisoformat(since or doc["updated_at"])
    except (KeyError, TypeError, ValueError):
        return True
    return datetime.now(timezone.utc) - since < EXTRACT_STALE_AFTER


LOAD_FIELDS = ("dataset_id", "ca_id", "site_id", "owner_uid", "owner_email", "options", "status", "stage", "stages", "mode",
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


def target_held(loads, doc: dict, except_id: str | None = None) -> bool:
    """Another load of the same conservation area into the same site is in
    progress. Two executions writing one target would race the schema and
    patrol writes with separate ledgers."""
    return any(l.get("id") != except_id and l.get("dataset_id") == doc.get("dataset_id")
               and l.get("ca_id") == doc.get("ca_id") and l.get("site_id") == doc.get("site_id")
               and load_in_progress(l) for l in loads)


def is_owner(doc: dict, user: dict) -> bool:
    return doc.get("owner_uid") == user["uid"]


def can_read(doc: dict, user: dict) -> bool:
    return is_owner(doc, user) or (user.get("email") or "").lower() in [e.lower() for e in doc.get("shared_with", [])]


def site_content_type(relpath: str) -> str:
    ct, _ = mimetypes.guess_type(relpath)
    return ct or "application/octet-stream"


def safe_relpath(relpath: str) -> str:
    """A site-relative path with no way out of the dataset's folder."""
    parts = [p for p in relpath.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError("bad path")
    return "/".join(parts)


class LocalStore:
    def __init__(self):
        self.dir = Path(os.environ.get("LOCAL_DIR", ROOT / "web-data")).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index = self.dir / "datasets.json"
        self.lock = threading.Lock()

    # ---- metadata
    def _read_file(self, path: Path) -> dict:
        return json.loads(path.read_text()) if path.exists() else {}

    def _write_file(self, path: Path, data: dict):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1))
        tmp.replace(path)

    def _read(self) -> dict:
        return self._read_file(self.index)

    def _write(self, data: dict):
        self._write_file(self.index, data)

    def list_datasets(self) -> list:
        return [dict(id=k, **v) for k, v in self._read().items()]

    def get(self, id: str):
        d = self._read().get(id)
        return dict(id=id, **d) if d else None

    def create(self, doc: dict) -> str:
        id = uuid.uuid4().hex[:12]
        with self.lock:
            data = self._read(); data[id] = doc; self._write(data)
        return id

    def update(self, id: str, **fields):
        with self.lock:
            data = self._read()
            if id in data:
                data[id].update(fields); data[id]["updated_at"] = now(); self._write(data)

    def delete(self, id: str):
        self.delete_dataset_loads(id)
        with self.lock:
            data = self._read(); data.pop(id, None); self._write(data)

    def claim_extract(self, id: str) -> bool:
        """Mark the dataset queued unless an extraction already holds it."""
        with self.lock:
            data = self._read()
            doc = data.get(id)
            if doc is None or extract_in_progress(doc):
                return False
            doc.update(status="queued", error=None, extract_claimed_at=now(), updated_at=now())
            self._write(data)
            return True

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
        try:
            with self.lock:
                data = self._read_file(self.dir / "sites.json")
                data[id] = {**doc, "secret_name": secret}
                self._write_file(self.dir / "sites.json", data)
        except BaseException:
            (self.dir / "secrets" / secret).unlink(missing_ok=True)   # no orphan token behind a failed registration
            raise
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

    # ---- storage
    def _p(self, id: str) -> Path:
        return self.dir / "datasets" / id

    def upload_target(self, id: str, filename: str, content_type: str) -> dict:
        return {"method": "PUT", "url": f"/api/datasets/{id}/upload", "headers": {"Content-Type": content_type or "application/octet-stream"}}

    def upload_path(self, id: str, filename: str) -> Path:
        return self._p(id) / "upload" / Path(filename).name

    def upload_exists(self, id: str, filename: str) -> bool:
        p = self.upload_path(id, filename)
        return p.is_file() and p.stat().st_size > 0

    def fetch_upload(self, id: str, filename: str, dest_dir: Path) -> Path:
        return self._p(id) / "upload" / Path(filename).name  # already local

    def put_site(self, id: str, site_dir: Path):
        dest = self._p(id) / "site"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(site_dir, dest, symlinks=False, ignore=shutil.ignore_patterns("index.html"))

    def put_export(self, id: str, export_dir: Path):
        dest = self._p(id) / "export"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(export_dir, dest, symlinks=False, ignore=shutil.ignore_patterns(".export-staging"))

    def export_exists(self, id: str, ca_dir: str) -> bool:
        return (self._p(id) / "export" / safe_relpath(ca_dir) / "bundle" / "manifest.json").is_file()

    def fetch_export(self, id: str, ca_dir: str, dest: Path) -> Path:
        return self._p(id) / "export" / safe_relpath(ca_dir)  # already local

    def open_site_file(self, id: str, relpath: str):
        f = self._p(id) / "site" / safe_relpath(relpath)
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
        return chunks(), size, site_content_type(relpath)

    def delete_storage(self, id: str):
        shutil.rmtree(self._p(id), ignore_errors=True)

    # ---- extraction
    def job_command(self, id: str) -> list:
        return [sys.executable, str(ROOT / "web" / "job.py"), id]

    def start_extract(self, id: str) -> str:
        """Run the job in a background thread of this process, killed with
        everything it started once it passes EXTRACT_TIMEOUT, as Cloud Run
        would."""
        def run():
            proc = subprocess.Popen(self.job_command(id), env={**os.environ, "BACKEND": "local"},
                                    start_new_session=True)
            try:
                proc.wait(timeout=EXTRACT_TIMEOUT.total_seconds())
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
                self.update(id, status="failed", error=f"Extraction timed out after {EXTRACT_TIMEOUT}")
        threading.Thread(target=run, daemon=True).start()
        return "local-thread"

    # ---- loads
    def _loads_path(self) -> Path:
        return self.dir / "loads.json"

    def list_loads(self, dataset_id: str) -> list:
        return [dict(id=k, **v) for k, v in self._read_file(self._loads_path()).items() if v.get("dataset_id") == dataset_id]

    def get_load(self, id: str):
        d = self._read_file(self._loads_path()).get(id)
        return dict(id=id, **d) if d else None

    def create_load(self, doc: dict):
        """The new load's id, or None when it would hold a target another
        load already holds. Decided under the lock, so two creates cannot
        both pass."""
        id = uuid.uuid4().hex[:12]
        with self.lock:
            data = self._read_file(self._loads_path())
            if doc.get("status") in LOAD_ACTIVE and target_held([dict(id=k, **v) for k, v in data.items()], doc):
                return None
            data[id] = doc; self._write_file(self._loads_path(), data)
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
            if doc is None or load_in_progress(doc) or target_held([dict(id=k, **v) for k, v in data.items()], doc, id):
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
        """Launch now, reap in the background: the load job calls this for its
        own continuation and exits right after, and a daemon thread may never
        run before the interpreter shuts down."""
        proc = subprocess.Popen(self.load_job_command(id, mode),
                                env={**os.environ, "BACKEND": "local", "LOAD_ID": id, "MODE": mode},
                                start_new_session=True)
        threading.Thread(target=proc.wait, daemon=True).start()
        return "local-thread"


class GcpStore:
    def __init__(self):
        from google.cloud import firestore, storage
        self.project = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.region = os.environ.get("GCP_REGION", "us-central1")
        self.bucket_name = os.environ["GCS_BUCKET"]
        self.job_name = os.environ.get("EXTRACT_JOB", "smart-able-extract")
        self.db = firestore.Client(project=self.project)
        self.gcs = storage.Client(project=self.project)
        self.bucket = self.gcs.bucket(self.bucket_name)

    # ---- metadata
    def _col(self):
        return self.db.collection("datasets")

    def list_datasets(self) -> list:
        return [dict(id=d.id, **d.to_dict()) for d in self._col().stream()]

    def get(self, id: str):
        d = self._col().document(id).get()
        return dict(id=d.id, **d.to_dict()) if d.exists else None

    def create(self, doc: dict) -> str:
        ref = self._col().document()
        ref.set(doc)
        return ref.id

    def update(self, id: str, **fields):
        fields["updated_at"] = now()
        self._col().document(id).update(fields)

    def delete(self, id: str):
        self.delete_dataset_loads(id)
        self._col().document(id).delete()

    def claim_extract(self, id: str) -> bool:
        """Mark the dataset queued unless an extraction already holds it. A
        transaction, so two requests cannot both see it free."""
        from google.cloud import firestore
        ref = self._col().document(id)

        @firestore.transactional
        def claim(tx) -> bool:
            snap = ref.get(transaction=tx)
            if not snap.exists or extract_in_progress(snap.to_dict()):
                return False
            tx.update(ref, {"status": "queued", "error": None, "extract_claimed_at": now(), "updated_at": now()})
            return True

        return claim(self.db.transaction())

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
        try:
            self._secret_create(secret, token)
            ref.set({**doc, "secret_name": secret})
        except BaseException:
            try:   # no orphan token behind a failed registration
                self._secret_delete(secret)
            except Exception:  # noqa: BLE001
                logging.exception("could not delete secret %s after a failed site registration", secret)
            raise
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

    # ---- storage
    def _signer(self):
        """Signed URLs without a key file: sign through the IAM API with the
        runtime service account (needs roles/iam.serviceAccountTokenCreator on itself)."""
        import google.auth
        from google.auth.transport import requests as g_requests
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(g_requests.Request())
        return {"service_account_email": getattr(creds, "service_account_email", None), "access_token": creds.token}

    def upload_target(self, id: str, filename: str, content_type: str) -> dict:
        from datetime import timedelta
        blob = self.bucket.blob(f"datasets/{id}/upload/{Path(filename).name}")
        ct = content_type or "application/octet-stream"
        url = blob.generate_signed_url(version="v4", expiration=timedelta(hours=6), method="PUT",
                                       content_type=ct, **self._signer())
        return {"method": "PUT", "url": url, "headers": {"Content-Type": ct}}

    def upload_exists(self, id: str, filename: str) -> bool:
        return self.bucket.blob(f"datasets/{id}/upload/{Path(filename).name}").exists()

    def fetch_upload(self, id: str, filename: str, dest_dir: Path) -> Path:
        dest = Path(dest_dir) / Path(filename).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.bucket.blob(f"datasets/{id}/upload/{Path(filename).name}").download_to_filename(str(dest))
        return dest

    def put_site(self, id: str, site_dir: Path):
        from concurrent.futures import ThreadPoolExecutor
        site_dir = Path(site_dir)
        prefix = f"datasets/{id}/site/"
        for old in self.bucket.list_blobs(prefix=prefix):
            old.delete()
        files = [p for p in site_dir.rglob("*") if p.is_file() and p.name != "index.html"]
        def up(p: Path):
            rel = p.relative_to(site_dir).as_posix()
            self.bucket.blob(prefix + rel).upload_from_filename(str(p), content_type=site_content_type(rel))
        with ThreadPoolExecutor(max_workers=16) as ex:
            list(ex.map(up, files))

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

    def open_site_file(self, id: str, relpath: str):
        blob = self.bucket.blob(f"datasets/{id}/site/{safe_relpath(relpath)}")
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
        return chunks(), blob.size, blob.content_type or site_content_type(relpath)

    def delete_storage(self, id: str):
        for b in self.bucket.list_blobs(prefix=f"datasets/{id}/"):
            b.delete()

    # ---- extraction
    def start_extract(self, id: str) -> str:
        from google.cloud import run_v2
        client = run_v2.JobsClient()
        name = f"projects/{self.project}/locations/{self.region}/jobs/{self.job_name}"
        req = run_v2.RunJobRequest(name=name, overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[run_v2.RunJobRequest.Overrides.ContainerOverride(
                env=[run_v2.EnvVar(name="DATASET_ID", value=id)])]))
        op = client.run_job(request=req)
        return getattr(op.metadata, "name", "") or "started"

    # ---- loads
    def _loads(self):
        return self.db.collection("loads")

    def list_loads(self, dataset_id: str) -> list:
        return [dict(id=d.id, **d.to_dict()) for d in self._loads().where("dataset_id", "==", dataset_id).stream()]

    def get_load(self, id: str):
        d = self._loads().document(id).get()
        return dict(id=d.id, **d.to_dict()) if d.exists else None

    def _target_loads(self, doc: dict):
        return (self._loads().where("dataset_id", "==", doc.get("dataset_id"))
                .where("ca_id", "==", doc.get("ca_id")).where("site_id", "==", doc.get("site_id")))

    def create_load(self, doc: dict):
        """The new load's id, or None when it would hold a target another
        load already holds. A transaction over the target's loads, so two
        creates cannot both pass."""
        from google.cloud import firestore
        ref = self._loads().document()

        @firestore.transactional
        def create(tx):
            if doc.get("status") in LOAD_ACTIVE:
                others = [dict(id=d.id, **d.to_dict()) for d in tx.get(self._target_loads(doc))]
                if target_held(others, doc):
                    return None
            tx.set(ref, doc)
            return ref.id

        return create(self.db.transaction())

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
            others = [dict(id=d.id, **d.to_dict()) for d in tx.get(self._target_loads(snap.to_dict()))]
            if target_held(others, snap.to_dict(), id):
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


_store = None


def get_store():
    global _store
    if _store is None:
        _store = LocalStore() if BACKEND == "local" else GcpStore()
    return _store
