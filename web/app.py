"""smart-able as a web service: sign in, upload a SMART backup or export,
have it extracted, browse the result, share it with colleagues.

Routes:
  GET  /                      the app page (sign-in, dataset list, upload, share)
  GET  /api/config            Firebase web config for the sign-in
  POST /api/session           id token -> session cookie;  POST /api/signout
  GET  /api/me
  GET  /api/help              the help drawer's sections (web/help/*.md and the quirks doc)
  GET  /api/datasets          datasets the user owns or is shared on; ?all=1 from support staff: everyone's
                              (support staff, auth.is_support, may open every GET below on any dataset,
                              site or load, and nothing that writes)
  POST /api/datasets          create one; returns where to PUT the file
  PUT  /api/datasets/{id}/upload    (local backend only; GCS takes signed PUTs)
  POST /api/datasets/{id}/extract   start the extraction job
  GET  /api/datasets/{id}     status, counts, log tail
  DELETE /api/datasets/{id}   owner only
  POST /api/datasets/{id}/share {email};  DELETE /api/datasets/{id}/share/{email}
  GET  /api/sites             sites (EarthRanger targets) the user owns or is shared on; ?all=1 as above
  POST /api/sites             {name, url, token}; checks the token, stores it as a secret
  PATCH  /api/sites/{id}       the owner renames it or replaces its token (checked first)
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
from datetime import date
import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from auth import AUTH_DISABLED, allowed_entries, current_user, email_allowed, end_session, start_session
from er_site import HostError, SiteUnreachable, TokenRejected, check_token, normalize_host
from errors import ApiError
from findings import EVENT_CATEGORY, SET_NAME_MAX, ca_identifier, set_category
from store import (LOAD_ACTIVE, load_working, LOAD_FIELDS, ROOT, LocalStore, access, can_read, can_view, extract_in_progress, get_store, is_owner,
                   load_in_progress, now, safe_relpath, stored_name, upload_expires_at)

logging.basicConfig(level=logging.INFO)
HERE = Path(__file__).resolve().parent
BROWSER = ROOT / "browse" / "index.html"
# The docs page, built into the image (web/Dockerfile) and served instead of
# each dataset's copy, so a docs or style change reaches every dataset like
# the browser page does. Falls back to the dataset's copy when absent.
QUIRKS = ROOT / "browse" / "quirks.html"
APP_VERSION = os.environ.get("APP_VERSION", "dev")
# the page asks for its script and stylesheet by content, so a browser holding the previous
# deploy's copies fetches the new ones
ASSETS = {name: hashlib.sha256((HERE / "static" / name).read_bytes()).hexdigest()[:12] for name in ("app.css", "app.js", "i18n.js", "pages.js", "er-tokens.css", "fonts/roboto.css")}
# the language menu and the message files: the registry is read once, and one hash over every message
# file keeps a browser from holding last deploy's messages
LOCALES = HERE / "static" / "locales"
LANGUAGES = json.loads((LOCALES / "languages.json").read_text(encoding="utf-8"))
LOCALES_V = hashlib.sha256(b"".join(p.read_bytes() for p in sorted(LOCALES.glob("*.json")))).hexdigest()[:12]

app = FastAPI(title="smart-able")


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    """422 without the submitted values: a body can carry a token."""
    return JSONResponse(status_code=422, content={"detail": [{k: v for k, v in e.items() if k != "input"}
                                                             for e in exc.errors()], "code": "invalid_request"})


@app.exception_handler(ApiError)
async def _api_error(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code, "values": exc.values})
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
    return {k: doc.get(k) for k in ("id", "name", "owner_email", "shared_with", "status", "created_at", "updated_at", "started_at", "finished_at",
                                    "source_name", "source_size", "cas", "db_version", "counts", "error", "export")} | {
        "mine": is_owner(doc, user), "access": access(doc, user), "extract_held": extract_in_progress(doc)}


SUPPORT_LOG_EVERY_SECONDS = 600
_support_log = logging.getLogger("support")   # printed by basicConfig's handler, above
_support_log.setLevel(logging.INFO)   # the record is not to be lost to a level someone sets elsewhere
_viewed: dict = {}   # (viewer, kind, id) -> when it was last logged, by this process's clock


def _record_view(user: dict, kind: str, id: str = "", owner: str = ""):
    """The record of a support view: who looked at whose what. Once per viewer, kind and id in ten
    minutes, because the dataset and load pages poll. Never a token, a file's contents or a name from
    the data."""
    key, at = (user["email"].lower(), kind, id), time.monotonic()
    last = _viewed.get(key)
    if last is not None and at - last < SUPPORT_LOG_EVERY_SECONDS:
        return
    if len(_viewed) > 10000:
        _viewed.clear()
    _viewed[key] = at
    _support_log.info("support_view viewer=%s kind=%s id=%s owner=%s", user["email"], kind, id, owner)


def _viewing(doc: dict, user: dict, kind: str, id: str | None = None):
    """Record it if this user reaches the dataset only through support view."""
    if access(doc, user) == "support":
        _record_view(user, kind, id or doc["id"], doc.get("owner_email") or "")


def _load(id: str, user: dict, owner: bool = False, view: bool = False) -> dict:
    """The dataset, if this user may read it. view=True also admits the support staff, who may look and
    nothing else: only routes that read pass it, so a route that writes stays closed to them."""
    doc = get_store().get(id)
    if not doc or not (can_view if view else can_read)(doc, user):
        raise ApiError(404, "dataset_not_found", "Dataset not found")
    if owner and not is_owner(doc, user):
        raise ApiError(403, "owner_only", "Only the owner can do that")
    return doc


# ---------------------------------------------------------------- pages
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"version": APP_VERSION, "assets": ASSETS,
                                                                  "languages": LANGUAGES, "locales_v": LOCALES_V})


@app.get("/api/config")
async def config():
    return {"apiKey": os.environ.get("FIREBASE_API_KEY", ""), "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN", ""),
            "projectId": os.environ.get("FIREBASE_PROJECT_ID", ""), "authDisabled": AUTH_DISABLED,
            "authEmulatorUrl": os.environ.get("FIREBASE_AUTH_EMULATOR_URL", ""),
            "allowed": allowed_entries(), "version": APP_VERSION}


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
def help_sections(lang: str = "en", user=Depends(current_user)):   # a plain def: file reads and Markdown off the event loop
    import help_pages
    if lang not in {l["code"] for l in LANGUAGES}:   # checked before it names a folder; anything else is English
        lang = "en"
    return {"sections": help_pages.sections(lang)}


# ---------------------------------------------------------------- datasets
@app.get("/api/datasets")
async def list_datasets(everyone: bool = Query(False, alias="all"), user=Depends(current_user)):
    see = can_view if everyone and user.get("support") else can_read   # ?all=1 means nothing from anyone else
    if see is can_view:
        _record_view(user, "list", "datasets")
    docs = [d for d in get_store().list_datasets() if see(d, user)]
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return [_public(d, user) for d in docs]


@app.post("/api/datasets", status_code=201)
async def create_dataset(req: DatasetCreate, user=Depends(current_user)):
    name = req.name.strip() or Path(req.filename).stem
    if not re.search(r"\.(zip|bak)$", req.filename, re.I):
        raise ApiError(400, "upload_not_zip", "Upload a SMART backup or Conservation Area export as a .zip")
    store = get_store()
    id = store.create({"name": name, "owner_uid": user["uid"], "owner_email": user["email"], "shared_with": [],
                       "status": "uploading", "created_at": now(), "updated_at": now(),
                       "source_name": stored_name(req.filename), "source_size": req.size})
    return {"id": id, "upload": store.upload_target(id, stored_name(req.filename), req.content_type)}


@app.put("/api/datasets/{id}/upload")
async def upload(id: str, request: Request, user=Depends(current_user)):
    """Local backend only: in production the browser PUTs straight to GCS."""
    doc = _load(id, user, owner=True)
    store = get_store()
    if not isinstance(store, LocalStore):
        raise ApiError(400, "upload_direct", "Uploads go straight to storage on this deployment")
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
    if any(load_working(l) for l in store.list_loads(id)):   # a load reads the bundle this would replace
        raise ApiError(409, "load_running", "Wait for the running load to stop first")
    missing = ApiError(400, "upload_incomplete", "The upload is missing or incomplete; delete this dataset and upload again")
    if doc.get("upload_deleted_at") or not store.upload_exists(id, doc["source_name"]):
        raise missing
    if not store.claim_extract(id):   # held by an extraction, or the backup's deletion was reserved meanwhile
        raise missing if (store.get(id) or {}).get("upload_deleted_at") else ApiError(409, "extract_active", "An extraction is already queued or running")
    try:
        execution = store.start_extract(id)
    except Exception as e:  # noqa: BLE001  the job did not start: say so, and leave the dataset retryable
        logging.exception("could not start extraction for %s", id)
        store.update(id, status="failed", error=f"Could not start the extraction: {type(e).__name__}: {e}")
        raise ApiError(502, "extract_start_failed", "Could not start the extraction job") from e
    # status is not set here: the job may already have marked the dataset running
    store.update(id, execution=execution)
    return {"ok": True, "execution": execution}


@app.get("/api/datasets/{id}")
async def get_dataset(id: str, user=Depends(current_user)):
    doc = _load(id, user, view=True)
    _viewing(doc, user, "dataset")
    out = _public(doc, user)
    # the uploaded backup is stored apart from what was extracted, and for a limited time: say so (one
    # storage lookup, so on this page only, not for every dataset in the list)
    out["upload"] = {"present": bool(doc.get("source_name")) and get_store().upload_exists(id, doc["source_name"]),
                     "expires_at": upload_expires_at(doc), "deleted_at": doc.get("upload_deleted_at")}
    if out["access"] in ("owner", "support"):
        out["log_tail"] = doc.get("log_tail")
    return out


@app.delete("/api/datasets/{id}/upload")
def delete_upload(id: str, user=Depends(current_user)):   # a plain def: the storage call is off the event loop
    """The owner removes the uploaded backup ahead of its expiry. The extracted data, bundles and loads stay."""
    doc = _load(id, user, owner=True)
    store = get_store()
    # reserved first, atomically with claiming an extraction: an extraction cannot start between this
    # check and the file going, and this cannot go ahead while one is reading the file
    if not store.claim_upload_delete(id):
        raise ApiError(409, "dataset_extracting", "The dataset is being extracted; wait for it to finish")
    if doc.get("source_name"):
        store.delete_upload(id, doc["source_name"])
    return {"ok": True}


@app.delete("/api/datasets/{id}")
async def delete_dataset(id: str, user=Depends(current_user)):
    _load(id, user, owner=True)
    store = get_store()
    if any(load_in_progress(l) for l in store.list_loads(id)):
        raise ApiError(409, "load_running_delete", "Wait for the running load to stop (or delete it) first")
    store.delete_storage(id)
    store.delete(id)
    return {"ok": True}


@app.post("/api/datasets/{id}/share")
async def share(id: str, req: ShareRequest, user=Depends(current_user)):
    doc = _load(id, user, owner=True)
    email = req.email.strip().lower()
    if not email_allowed(email):
        raise ApiError(400, "share_not_allowed", "Can only share with allowed addresses")
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


class SiteEdit(BaseModel):
    """What can change on a site: its name and its token. Not its host: another host is another site."""
    model_config = {"extra": "forbid"}
    name: Optional[str] = None
    token: Optional[str] = None


def _site_public(doc: dict, user: dict) -> dict:
    out = {k: doc.get(k) for k in ("id", "name", "url", "owner_email", "shared_with", "token_hint", "checked_at",
                                   "checked_as", "created_at")} | {"mine": is_owner(doc, user), "access": access(doc, user)}
    if out["access"] == "support":
        out["token_hint"] = None   # a viewer has no use for any part of the token
    return out


def _load_site(id: str, user: dict, owner: bool = False) -> dict:
    doc = get_store().get_site(id)
    if not doc or not can_read(doc, user):
        raise ApiError(404, "site_not_found", "Site not found")
    if owner and not is_owner(doc, user):
        raise ApiError(403, "owner_only", "Only the owner can do that")
    return doc


@app.get("/api/sites")
async def list_sites(everyone: bool = Query(False, alias="all"), user=Depends(current_user)):
    see = can_view if everyone and user.get("support") else can_read
    if see is can_view:
        _record_view(user, "list", "sites")
    docs = [d for d in get_store().list_sites() if see(d, user)]
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return [_site_public(d, user) for d in docs]


@app.post("/api/sites", status_code=201)
def create_site(req: SiteCreate, user=Depends(current_user)):
    try:
        host = normalize_host(req.url)
    except HostError as e:
        raise ApiError(400, e.code, str(e))
    except ValueError as e:   # urlparse's own refusal of a malformed bracketed host
        raise ApiError(400, "site_host_missing", str(e))
    token = req.token.strip()
    if not token:
        raise ApiError(400, "token_required", "A token is required")
    checked_as = _checked_token(host, token)
    store = get_store()
    id = store.create_site({"name": req.name.strip() or host, "url": host, "owner_uid": user["uid"],
                            "owner_email": user["email"], "shared_with": [], "token_hint": token[-4:],
                            "checked_at": now(), "checked_as": checked_as, "created_at": now(), "updated_at": now()},
                           token)
    return _site_public(store.get_site(id), user)


def _checked_token(host: str, token: str) -> str:
    """The user the token works as on the site, or the error the site form shows."""
    try:
        return check_token(host, token)
    except TokenRejected as e:
        raise ApiError(400, "token_rejected", f"The token was rejected: {e}", reason=str(e))
    except SiteUnreachable as e:
        raise ApiError(400, "site_unreachable", str(e), reason=str(e))


@app.patch("/api/sites/{id}")
def edit_site(id: str, req: SiteEdit, user=Depends(current_user)):
    """The owner renames a site or replaces its token. A new token is checked against the site before
    anything is stored, and not swapped under a load that is using the old one."""
    doc = _load_site(id, user, owner=True)
    store = get_store()
    fields = {}
    if req.name is not None:
        fields["name"] = req.name.strip() or doc["url"]
    token = (req.token or "").strip()
    if token:
        if any(load_in_progress(l) for l in store.site_loads(id)):
            raise ApiError(409, "site_busy", "Wait for the load into this site to stop before replacing its token")
        checked_as = _checked_token(doc["url"], token)
        store.replace_site_token(id, token)
        fields.update(token_hint=token[-4:], checked_at=now(), checked_as=checked_as)
    if fields:
        store.update_site(id, **fields)
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
        raise ApiError(400, "share_not_allowed", "Can only share with allowed addresses")
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
LOAD_SCOPES = ("all", "datamodel")   # the data model and patrols, or the data model only


def _window_date(value, which: str) -> str | None:
    """One end of a load's date window: a YYYY-MM-DD day, or None for an open end."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except (AttributeError, TypeError, ValueError):
        raise ApiError(400, "window_not_date", f"The window's {which} must be a date (YYYY-MM-DD)", which=which) from None


class LoadCreate(BaseModel):
    ca_id: str
    site_id: str
    options: dict = {}


LOAD_DETAIL_ONLY = ("plan", "findings", "rangers", "log_tail", "stages")


def _load_public(doc: dict, user: dict, dataset: Optional[dict] = None) -> dict:
    dataset = dataset or get_store().get(doc.get("dataset_id") or "-")
    site = get_store().get_site(doc.get("site_id", "")) if doc.get("site_id") else None
    out = {k: doc.get(k) for k in LOAD_FIELDS}
    # loads made before event_category existed run with the default (load_job's fallback)
    out["options"] = {"event_category": None, "event_type_set": None, "scope": "all", "since": None, "until": None, **(out.get("options") or {})}
    # a load is reached through its dataset: seen through support view if the dataset is
    reach = "support" if dataset and access(dataset, user) == "support" else "owner" if is_owner(doc, user) else "shared"
    return out | {
        "id": doc["id"], "mine": is_owner(doc, user), "access": reach, "held": load_in_progress(doc),
        "dataset_extracting": bool(dataset and extract_in_progress(dataset)),   # run and plan-again are refused meanwhile
        "site": {"id": site["id"], "name": site.get("name"), "url": site.get("url")} if site else None}


def _load_load(id: str, user: dict, view: bool = False) -> dict:
    doc = get_store().get_load(id)
    if not doc:
        raise ApiError(404, "load_not_found", "Load not found")
    _load(doc["dataset_id"], user, view=view)   # read on the dataset is the permission
    return doc


def _launch(load_id: str, mode: str):
    """Start the job for a load that already holds its slot."""
    store = get_store()
    try:
        execution = store.start_load(load_id, mode)
    except Exception as e:  # noqa: BLE001
        logging.exception("could not start load %s", load_id)
        store.update_load(load_id, status="failed", error=f"Could not start the job: {type(e).__name__}: {e}")
        raise ApiError(502, "load_start_failed", "Could not start the load job") from e
    store.update_load(load_id, execution=execution)


def _not_extracting(dataset: Optional[dict]):
    """A load reads the dataset's bundle, which an extraction rewrites."""
    if dataset and extract_in_progress(dataset):
        raise ApiError(409, "dataset_extracting", "The dataset is being extracted; wait for it to finish")


def _start(load_id: str, mode: str, claim_status: str):
    dataset_id = (get_store().get_load(load_id) or {}).get("dataset_id")
    _not_extracting(get_store().get(dataset_id) if dataset_id else None)
    if not get_store().claim_load(load_id, claim_status):
        raise ApiError(409, "load_active_same", "This load, or another load of this conservation area into that site, "
                                                "is already planning or running")
    _launch(load_id, mode)


@app.post("/api/datasets/{id}/loads", status_code=201)
def create_load(id: str, req: LoadCreate, user=Depends(current_user)):
    doc = _load(id, user)
    _not_extracting(doc)
    site = _load_site(req.site_id, user)
    entry = next((e for e in doc.get("export") or [] if e.get("dir") == req.ca_id), None)
    if not entry:
        raise ApiError(400, "no_bundle", "No migration bundle for that conservation area; re-extract the dataset")
    scope = req.options.get("scope") or "all"
    if scope not in LOAD_SCOPES:
        raise ApiError(400, "scope_invalid", "What to load must be the data model only, or the data model and patrols")
    since, until = _window_date(req.options.get("since"), "start"), _window_date(req.options.get("until"), "end")
    if scope == "datamodel" and (since or until):
        raise ApiError(400, "window_without_patrols", "A date window applies to patrols; a data-model-only load has none")
    if since and until and since > until:
        raise ApiError(400, "window_reversed", "The window's start is after its end")
    if scope == "all" and not entry.get("patrols"):
        raise ApiError(400, "no_patrols", "That conservation area has no patrols to load; load the data model only")
    language = req.options.get("language") or entry.get("default_language")
    if language not in entry.get("languages", []):
        raise ApiError(400, "language_not_in_bundle", f"Language {language!r} is not in the bundle", language=language)
    cm = req.options.get("configurable_model") or None
    if cm and cm not in [c["uuid"] for c in entry.get("configurable_models", [])]:
        raise ApiError(400, "unknown_model", "Unknown configurable model")
    # the set: which event types and lists this load shares with other areas' loads into the site
    set_name = req.options.get("event_type_set")
    if set_name is not None and not isinstance(set_name, str):
        raise ApiError(400, "event_type_set_invalid", f"The event type set's name must be 1-{SET_NAME_MAX} characters")
    set_name = (set_name or "").strip() or None
    if set_name and not cm:
        raise ApiError(400, "set_without_model", "Only a load with a configurable model has an event type set")
    if cm and not set_name:
        set_name = (next(c.get("label") for c in entry["configurable_models"] if c["uuid"] == cm) or cm).strip()[:SET_NAME_MAX]
    if set_name and len(set_name) > SET_NAME_MAX:
        raise ApiError(400, "event_type_set_invalid", f"The event type set's name must be 1-{SET_NAME_MAX} characters")
    category = req.options.get("event_category")
    if category is None or (isinstance(category, str) and not category.strip()):
        category = set_category(set_name) if set_name else ca_identifier(entry.get("ca_id"))
    elif not isinstance(category, str) or not EVENT_CATEGORY.fullmatch(category.strip()):
        raise ApiError(400, "event_category_invalid", "The event category must be 2-30 letters, digits, '-' or '_'")
    category = category.strip()
    store = get_store()
    load_id = store.create_load({
        "dataset_id": id, "ca_id": req.ca_id, "site_id": site["id"], "owner_uid": user["uid"], "owner_email": user["email"],
        "options": {"language": language, "configurable_model": cm, "event_type_set": set_name,
                    "roster_group": (req.options.get("roster_group") or "").strip() or None,
                    "event_category": category, "scope": scope, "since": since, "until": until},
        "status": "planning", "stage": None, "claimed_at": now(),   # created holding its slot: no claim race
        "created_at": now(), "updated_at": now(), "continuations": 0,
        "plan": None, "findings": [], "progress": None, "log_tail": None, "error": None})
    if load_id is None:
        raise ApiError(409, "load_active", "A load of this conservation area into that site is already active")
    _launch(load_id, "plan")
    return _load_public(store.get_load(load_id), user)


@app.get("/api/datasets/{id}/loads")
async def list_loads(id: str, user=Depends(current_user)):
    dataset = _load(id, user, view=True)
    _viewing(dataset, user, "dataset")
    docs = get_store().list_loads(id)
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    # the list shows a line per load: the page-sized fields stay with GET /api/loads/{id}
    return [{k: v for k, v in _load_public(d, user, dataset).items() if k not in LOAD_DETAIL_ONLY} for d in docs]


@app.get("/api/loads/{id}")
async def get_load(id: str, user=Depends(current_user)):
    doc = _load_load(id, user, view=True)
    out = _load_public(doc, user)
    if out["access"] == "support":
        _record_view(user, "load", id, doc.get("owner_email") or "")
    return out


def _stale(doc: dict) -> bool:
    """Its job was killed outright and the hold has lapsed."""
    return doc.get("status") in LOAD_ACTIVE and not load_in_progress(doc)


def _needs_site(doc: dict, user: dict):
    """Run and replan write (or plan writing) with the site owner's token, so
    the site's sharing applies as well as the dataset's."""
    site = get_store().get_site(doc.get("site_id", ""))
    if not site:
        raise ApiError(409, "site_removed", "The site was removed; register it again and start a new load")
    if not can_read(site, user):
        raise ApiError(403, "site_no_access", "You do not have access to that site")


@app.post("/api/loads/{id}/run")
def run_load(id: str, user=Depends(current_user)):
    doc = _load_load(id, user)
    if not (doc.get("status") in ("planned", "needs_attention") or _stale(doc)):
        raise ApiError(409, "load_cannot_run", f"A {doc.get('status')} load cannot be run; plan it again first", status=doc.get("status"))
    _needs_site(doc, user)
    _start(id, "run", "queued")
    return _load_public(get_store().get_load(id), user)


@app.post("/api/loads/{id}/replan")
def replan_load(id: str, user=Depends(current_user)):
    doc = _load_load(id, user)
    if not (doc.get("status") in ("planned", "needs_attention", "failed", "done") or _stale(doc)) or load_in_progress(doc):
        raise ApiError(409, "load_cannot_plan", f"A {doc.get('status')} load cannot be planned again now", status=doc.get("status"))
    _needs_site(doc, user)
    _start(id, "plan", "planning")
    return _load_public(get_store().get_load(id), user)


@app.delete("/api/loads/{id}")
async def delete_load(id: str, user=Depends(current_user)):
    doc = _load_load(id, user)
    if load_in_progress(doc):
        raise ApiError(409, "load_delete_running", "Wait for the load to stop before deleting it")
    get_store().delete_load(id)
    return {"ok": True}


@app.get("/api/loads/{id}/files/{name}")
async def load_file(id: str, name: str, user=Depends(current_user)):
    doc = _load_load(id, user, view=True)
    try:
        found = get_store().get_load_file(doc["dataset_id"], id, name)
    except ValueError:
        raise ApiError(400, "bad_path", "Bad path")
    if not found:
        raise ApiError(404, "not_found", "Not found")
    dataset = get_store().get(doc["dataset_id"])
    if dataset and access(dataset, user) == "support":   # the file as the store resolved it, not as the caller spelled it
        _record_view(user, "load_file", f"{id}/{safe_relpath(name)}", doc.get("owner_email") or "")
    chunks, size, ctype = found
    return StreamingResponse(chunks, media_type=ctype, headers={"Content-Length": str(size)})


@app.get("/d/{id}")
async def site_root_redirect(id: str):
    return RedirectResponse(url=f"/d/{id}/")


@app.get("/d/{id}/")
async def site_index(id: str, user=Depends(current_user)):
    doc = _load(id, user, view=True)
    _viewing(doc, user, "browser")
    if doc.get("status") != "ready":
        raise ApiError(409, "dataset_status", f"Dataset is {doc.get('status')}", status=doc.get("status"))
    return FileResponse(BROWSER, media_type="text/html")


@app.get("/d/{id}/{path:path}")
async def site_file(id: str, path: str, user=Depends(current_user)):
    _viewing(_load(id, user, view=True), user, "browser")
    if path in ("", "index.html"):
        return FileResponse(BROWSER, media_type="text/html")
    if path == "quirks.html" and QUIRKS.is_file():
        return FileResponse(QUIRKS, media_type="text/html")
    try:
        found = get_store().open_site_file(id, path)
    except ValueError:
        raise ApiError(400, "bad_path", "Bad path")
    if not found:
        raise ApiError(404, "not_found", "Not found")
    chunks, size, ctype = found
    headers = {"Content-Length": str(size), "Cache-Control": "private, max-age=3600"}
    return StreamingResponse(chunks, media_type=ctype, headers=headers)
