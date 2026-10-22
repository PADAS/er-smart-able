"""smart-able as a web service: sign in, upload a SMART backup or export,
have it extracted, browse the result, share it with colleagues.

Routes:
  GET  /                      the app page (sign-in, dataset list, upload, share)
  GET  /api/config            Firebase web config for the sign-in
  POST /api/session           id token -> session cookie;  POST /api/signout
  GET  /api/me
  GET  /api/datasets          datasets the user owns or is shared on
  POST /api/datasets          create one; returns where to PUT the file
  PUT  /api/datasets/{id}/upload    (local backend only; GCS takes signed PUTs)
  POST /api/datasets/{id}/extract   start the extraction job
  GET  /api/datasets/{id}     status, counts, log tail
  DELETE /api/datasets/{id}   owner only
  POST /api/datasets/{id}/share {email};  DELETE /api/datasets/{id}/share/{email}
  GET  /api/sites             sites (EarthRanger targets) the user owns or is shared on
  POST /api/sites             {name, url, token}; checks the token, stores it as a secret
  DELETE /api/sites/{id}      owner only
  POST /api/sites/{id}/share {email};  DELETE /api/sites/{id}/share/{email}
  GET  /api/datasets/{id}/loads   POST: {ca_id, site_id, options}; starts planning
  GET  /api/loads/{id};  DELETE /api/loads/{id}
  POST /api/loads/{id}/run    confirm a plan / continue a stopped load
  POST /api/loads/{id}/replan plan again
  GET  /api/loads/{id}/files/{name}   a load's log, plan and reports
  GET  /d/{id}/               the browser for that dataset (index.html from this
                              checkout, data and photos from the dataset's store)
"""
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from auth import AUTH_DISABLED, current_user, email_allowed, end_session, start_session
from er_site import SiteUnreachable, TokenRejected, check_token, normalize_host
from findings import EVENT_CATEGORY, ca_identifier
from store import (LOAD_ACTIVE, LOAD_FIELDS, ROOT, LocalStore, can_read, extract_in_progress, get_store, is_owner,
                   load_in_progress, now)

logging.basicConfig(level=logging.INFO)
HERE = Path(__file__).resolve().parent
BROWSER = ROOT / "browse" / "index.html"
# The docs page, built into the image (web/Dockerfile) and served instead of
# each dataset's copy, so a docs or style change reaches every dataset like
# the browser page does. Falls back to the dataset's copy when absent.
QUIRKS = ROOT / "browse" / "quirks.html"
APP_VERSION = os.environ.get("APP_VERSION", "dev")

app = FastAPI(title="smart-able")


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    """422 without the submitted values: a body can carry a token."""
    return JSONResponse(status_code=422, content={"detail": [{k: v for k, v in e.items() if k != "input"}
                                                             for e in exc.errors()]})
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


class DatasetCreate(BaseModel):
    name: str
    filename: str
    size: int = 0
    content_type: str = "application/zip"


class ShareRequest(BaseModel):
    email: str


class SessionRequest(BaseModel):
    idToken: str = ""


def _public(doc: dict, user: dict) -> dict:
    return {k: doc.get(k) for k in ("id", "name", "owner_email", "shared_with", "status", "created_at", "updated_at",
                                    "source_name", "source_size", "cas", "db_version", "counts", "error", "export")} | {
        "mine": is_owner(doc, user), "extract_held": extract_in_progress(doc)}


def _load(id: str, user: dict, owner: bool = False) -> dict:
    doc = get_store().get(id)
    if not doc or not can_read(doc, user):
        raise HTTPException(status_code=404, detail="Dataset not found")
    if owner and not is_owner(doc, user):
        raise HTTPException(status_code=403, detail="Only the owner can do that")
    return doc


# ---------------------------------------------------------------- pages
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"version": APP_VERSION})


@app.get("/api/config")
async def config():
    return {"apiKey": os.environ.get("FIREBASE_API_KEY", ""), "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN", ""),
            "projectId": os.environ.get("FIREBASE_PROJECT_ID", ""), "authDisabled": AUTH_DISABLED,
            "authEmulatorUrl": os.environ.get("FIREBASE_AUTH_EMULATOR_URL", ""),
            "allowed": os.environ.get("ALLOWED_EMAILS", "@earthranger.com"), "version": APP_VERSION}


# ---------------------------------------------------------------- session
@app.post("/api/session")
async def session(req: SessionRequest, request: Request, response: Response):
    return start_session(response, request, req.idToken)


@app.post("/api/signout")
async def signout(response: Response):
    end_session(response)
    return {"ok": True}


@app.get("/api/me")
async def me(user=Depends(current_user)):
    return user


@app.get("/api/help")
def help_sections(user=Depends(current_user)):   # a plain def: file reads and Markdown off the event loop
    import help_pages
    return {"sections": help_pages.sections()}


# ---------------------------------------------------------------- datasets
@app.get("/api/datasets")
async def list_datasets(user=Depends(current_user)):
    docs = [d for d in get_store().list_datasets() if can_read(d, user)]
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return [_public(d, user) for d in docs]


@app.post("/api/datasets", status_code=201)
async def create_dataset(req: DatasetCreate, user=Depends(current_user)):
    name = req.name.strip() or Path(req.filename).stem
    if not re.search(r"\.(zip|bak)$", req.filename, re.I):
        raise HTTPException(status_code=400, detail="Upload a SMART backup or Conservation Area export as a .zip")
    store = get_store()
    id = store.create({"name": name, "owner_uid": user["uid"], "owner_email": user["email"], "shared_with": [],
                       "status": "uploading", "created_at": now(), "updated_at": now(),
                       "source_name": Path(req.filename).name, "source_size": req.size})
    return {"id": id, "upload": store.upload_target(id, req.filename, req.content_type)}


@app.put("/api/datasets/{id}/upload")
async def upload(id: str, request: Request, user=Depends(current_user)):
    """Local backend only: in production the browser PUTs straight to GCS."""
    doc = _load(id, user, owner=True)
    store = get_store()
    if not isinstance(store, LocalStore):
        raise HTTPException(status_code=400, detail="Uploads go straight to storage on this deployment")
    dest = store.upload_path(id, doc["source_name"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with open(dest, "wb") as f:
        async for chunk in request.stream():
            f.write(chunk)
            size += len(chunk)
    store.update(id, status="uploaded", source_size=size)
    return {"ok": True, "size": size}


@app.post("/api/datasets/{id}/extract")
async def extract(id: str, user=Depends(current_user)):
    doc = _load(id, user, owner=True)
    store = get_store()
    if not store.upload_exists(id, doc["source_name"]):
        raise HTTPException(status_code=400, detail="The upload is missing or incomplete; delete this dataset and upload again")
    if not store.claim_extract(id):
        raise HTTPException(status_code=409, detail="An extraction is already queued or running")
    try:
        execution = store.start_extract(id)
    except Exception as e:  # noqa: BLE001  the job did not start: say so, and leave the dataset retryable
        logging.exception("could not start extraction for %s", id)
        store.update(id, status="failed", error=f"Could not start the extraction: {type(e).__name__}: {e}")
        raise HTTPException(status_code=502, detail="Could not start the extraction job") from e
    # status is not set here: the job may already have marked the dataset running
    store.update(id, execution=execution)
    return {"ok": True, "execution": execution}


@app.get("/api/datasets/{id}")
async def get_dataset(id: str, user=Depends(current_user)):
    doc = _load(id, user)
    out = _public(doc, user)
    if is_owner(doc, user):
        out["log_tail"] = doc.get("log_tail")
    return out


@app.delete("/api/datasets/{id}")
async def delete_dataset(id: str, user=Depends(current_user)):
    _load(id, user, owner=True)
    store = get_store()
    if any(load_in_progress(l) for l in store.list_loads(id)):
        raise HTTPException(status_code=409, detail="Wait for the running load to stop (or delete it) first")
    store.delete_storage(id)
    store.delete(id)
    return {"ok": True}


@app.post("/api/datasets/{id}/share")
async def share(id: str, req: ShareRequest, user=Depends(current_user)):
    doc = _load(id, user, owner=True)
    email = req.email.strip().lower()
    if not email_allowed(email):
        raise HTTPException(status_code=400, detail="Can only share with allowed addresses")
    shared = sorted(set(doc.get("shared_with", [])) | {email})
    get_store().update(id, shared_with=shared)
    return {"shared_with": shared}


@app.delete("/api/datasets/{id}/share/{email}")
async def unshare(id: str, email: str, user=Depends(current_user)):
    doc = _load(id, user, owner=True)
    shared = [e for e in doc.get("shared_with", []) if e.lower() != email.strip().lower()]
    get_store().update(id, shared_with=shared)
    return {"shared_with": shared}


# ---------------------------------------------------------------- sites


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


@app.get("/api/sites")
async def list_sites(user=Depends(current_user)):
    docs = [d for d in get_store().list_sites() if can_read(d, user)]
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return [_site_public(d, user) for d in docs]


@app.post("/api/sites", status_code=201)
def create_site(req: SiteCreate, user=Depends(current_user)):
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
def delete_site(id: str, user=Depends(current_user)):
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


# ---------------------------------------------------------------- the browser
class LoadCreate(BaseModel):
    ca_id: str
    site_id: str
    options: dict = {}


def _load_public(doc: dict, user: dict) -> dict:
    site = get_store().get_site(doc.get("site_id", "")) if doc.get("site_id") else None
    out = {k: doc.get(k) for k in LOAD_FIELDS}
    # loads made before event_category existed run with the default (load_job's fallback)
    out["options"] = {"event_category": None, **(out.get("options") or {})}
    return out | {
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
        raise HTTPException(status_code=409, detail="This load, or another load of this conservation area into that site, "
                                                    "is already planning or running")
    _launch(load_id, mode)


@app.post("/api/datasets/{id}/loads", status_code=201)
def create_load(id: str, req: LoadCreate, user=Depends(current_user)):
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
    category = req.options.get("event_category")
    if category is None or (isinstance(category, str) and not category.strip()):
        category = ca_identifier(entry.get("ca_id"))
    elif not isinstance(category, str) or not EVENT_CATEGORY.fullmatch(category.strip()):
        raise HTTPException(status_code=400, detail="The event category must be 2-30 letters, digits, '-' or '_'")
    category = category.strip()
    store = get_store()
    load_id = store.create_load({
        "dataset_id": id, "ca_id": req.ca_id, "site_id": site["id"], "owner_uid": user["uid"], "owner_email": user["email"],
        "options": {"language": language, "configurable_model": cm,
                    "roster_group": (req.options.get("roster_group") or "").strip() or None,
                    "event_category": category},
        "status": "planning", "stage": None, "claimed_at": now(),   # created holding its slot: no claim race
        "created_at": now(), "updated_at": now(), "continuations": 0,
        "plan": None, "findings": [], "progress": None, "log_tail": None, "error": None})
    if load_id is None:
        raise HTTPException(status_code=409, detail="A load of this conservation area into that site is already active")
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


def _stale(doc: dict) -> bool:
    """Its job was killed outright and the hold has lapsed."""
    return doc.get("status") in LOAD_ACTIVE and not load_in_progress(doc)


def _needs_site(doc: dict, user: dict):
    """Run and replan write (or plan writing) with the site owner's token, so
    the site's sharing applies as well as the dataset's."""
    site = get_store().get_site(doc.get("site_id", ""))
    if not site:
        raise HTTPException(status_code=409, detail="The site was removed; register it again and start a new load")
    if not can_read(site, user):
        raise HTTPException(status_code=403, detail="You do not have access to that site")


@app.post("/api/loads/{id}/run")
def run_load(id: str, user=Depends(current_user)):
    doc = _load_load(id, user)
    if not (doc.get("status") in ("planned", "needs_attention") or _stale(doc)):
        raise HTTPException(status_code=409, detail=f"A {doc.get('status')} load cannot be run; plan it again first")
    _needs_site(doc, user)
    _start(id, "run", "queued")
    return _load_public(get_store().get_load(id), user)


@app.post("/api/loads/{id}/replan")
def replan_load(id: str, user=Depends(current_user)):
    doc = _load_load(id, user)
    if not (doc.get("status") in ("planned", "needs_attention", "failed", "done") or _stale(doc)) or load_in_progress(doc):
        raise HTTPException(status_code=409, detail=f"A {doc.get('status')} load cannot be planned again now")
    _needs_site(doc, user)
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


@app.get("/d/{id}")
async def site_root_redirect(id: str):
    return RedirectResponse(url=f"/d/{id}/")


@app.get("/d/{id}/")
async def site_index(id: str, user=Depends(current_user)):
    doc = _load(id, user)
    if doc.get("status") != "ready":
        raise HTTPException(status_code=409, detail=f"Dataset is {doc.get('status')}")
    return FileResponse(BROWSER, media_type="text/html")


@app.get("/d/{id}/{path:path}")
async def site_file(id: str, path: str, user=Depends(current_user)):
    _load(id, user)
    if path in ("", "index.html"):
        return FileResponse(BROWSER, media_type="text/html")
    if path == "quirks.html" and QUIRKS.is_file():
        return FileResponse(QUIRKS, media_type="text/html")
    try:
        found = get_store().open_site_file(id, path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad path")
    if not found:
        raise HTTPException(status_code=404, detail="Not found")
    chunks, size, ctype = found
    headers = {"Content-Length": str(size), "Cache-Control": "private, max-age=3600"}
    return StreamingResponse(chunks, media_type=ctype, headers=headers)
