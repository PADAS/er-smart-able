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
import mimetypes
import os
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = os.environ.get("BACKEND", "gcp")
ROOT = Path(__file__).resolve().parent.parent  # the smart-able checkout
DATASET_FIELDS = ("name", "owner_uid", "owner_email", "shared_with", "status", "created_at", "updated_at",
                  "source_name", "source_size", "cas", "db_version", "counts", "error", "execution", "log_tail")

now = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    def _read(self) -> dict:
        return json.loads(self.index.read_text()) if self.index.exists() else {}

    def _write(self, data: dict):
        tmp = self.index.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1))
        tmp.replace(self.index)

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
        with self.lock:
            data = self._read(); data.pop(id, None); self._write(data)

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
    def start_extract(self, id: str) -> str:
        """Run the job in a background thread of this process."""
        def run():
            subprocess.run([sys.executable, str(ROOT / "web" / "job.py"), id], env={**os.environ, "BACKEND": "local"})
        threading.Thread(target=run, daemon=True).start()
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
        self._col().document(id).delete()

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


_store = None


def get_store():
    global _store
    if _store is None:
        _store = LocalStore() if BACKEND == "local" else GcpStore()
    return _store
