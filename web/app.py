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
  GET  /d/{id}/               the browser for that dataset (index.html from this
                              checkout, data and photos from the dataset's store)
"""
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from auth import AUTH_DISABLED, current_user, email_allowed, end_session, start_session
from store import ROOT, LocalStore, can_read, get_store, is_owner, now

logging.basicConfig(level=logging.INFO)
HERE = Path(__file__).resolve().parent
BROWSER = ROOT / "browse" / "index.html"
APP_VERSION = os.environ.get("APP_VERSION", "dev")

app = FastAPI(title="smart-able")
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
                                    "source_name", "source_size", "cas", "db_version", "counts", "error")} | {
        "mine": is_owner(doc, user)}


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
    return templates.TemplateResponse("index.html", {"request": request, "version": APP_VERSION})


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
    if doc.get("status") == "running":
        raise HTTPException(status_code=409, detail="Extraction already running")
    store = get_store()
    if not store.upload_exists(id, doc["source_name"]):
        raise HTTPException(status_code=400, detail="The upload is missing or incomplete; delete this dataset and upload again")
    try:
        execution = store.start_extract(id)
    except Exception as e:  # noqa: BLE001  the job did not start: say so, and leave the dataset retryable
        logging.exception("could not start extraction for %s", id)
        store.update(id, status="failed", error=f"Could not start the extraction: {type(e).__name__}: {e}")
        raise HTTPException(status_code=502, detail="Could not start the extraction job") from e
    store.update(id, status="queued", error=None, execution=execution)
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


# ---------------------------------------------------------------- the browser
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
    try:
        found = get_store().open_site_file(id, path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad path")
    if not found:
        raise HTTPException(status_code=404, detail="Not found")
    chunks, size, ctype = found
    headers = {"Content-Length": str(size), "Cache-Control": "private, max-age=3600"}
    return StreamingResponse(chunks, media_type=ctype, headers=headers)
