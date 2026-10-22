# Deploying smart-able to Cloud Run

The web service lets people with an allowed email (`@earthranger.com` by
default) sign in with Google, upload a SMART backup or Conservation Area
export, have it extracted, browse the result, and share it with colleagues.
It follows [PADAS/gundi-webhook-editor](https://github.com/PADAS/gundi-webhook-editor):
FastAPI, Firebase Authentication, OpenTofu, Workload Identity Federation,
GitHub Actions.

## How it fits together

| Piece | What | Where |
| --- | --- | --- |
| Service | `web/app.py`: sign-in, dataset list, upload URLs, share, serves the browser | Cloud Run service `smart-able`, image `web/Dockerfile` |
| Job | `web/job.py`: fetch the upload, run `./smart-able all`, publish the site | Cloud Run Job `smart-able-extract`, image `web/Dockerfile.job` (Java, DuckDB, OpenSSL, uv) |
| Load job | `web/load_job.py`: plan and run a migration into an EarthRanger site with er-smart-sync | Cloud Run Job `smart-able-load`, the same image as the extraction job, run with `/opt/load/bin/python` (its own venv, because er-smart-sync pins pydantic 1) |
| Index | one Firestore document per dataset: owner, `shared_with`, status, counts | Firestore `(default)`, collection `datasets` |
| Sites | one document per registered EarthRanger site: name, URL, owner, `shared_with`, the name of its token secret | Firestore `(default)`, collection `sites`; the token itself is in Secret Manager |
| Loads | one document per load: dataset, site, options, status, stage, findings, continuations | Firestore `(default)`, collection `loads` |
| Files | `datasets/<id>/upload/<file>` (the backup), `datasets/<id>/site/...` (data JSON and decrypted photos), `datasets/<id>/loads/<load id>/...` (a load's plan and results) | a private GCS bucket |

A dataset is owned by whoever uploaded it. The owner can share it with
other allowed addresses, re-run the extraction, or delete it; people it is
shared with can open it. The browser page is served from the checkout, so
updating the repository updates every dataset's browser; the data-format
banner tells a user when a dataset should be re-extracted.

Uploads go from the browser straight to GCS through a signed URL, because a
backup can be 3 GB and a Cloud Run request cannot carry that. The service
signs with its own identity through the IAM API, so no key file exists.

Sign-in sets a session cookie rather than the bearer header the webhook
editor uses, because the browser page loads its JSON and photos with plain
requests that cannot add a header. Scripts can still send
`Authorization: Bearer <Firebase ID token>`.

## Loading into EarthRanger

A dataset's owner can load it into an EarthRanger site from the app.

Registering a site stores its name, URL, owner and sharing in the `sites`
collection and its API token in Secret Manager as `smart-able-site-<id>`;
the document holds only the secret's name and a short hint of the token,
never the token. The token is checked against the site before it is saved.

A load has two steps. Creating it starts the job in plan mode, which
checks the site and the dataset and writes a plan (and any findings) under
`datasets/<id>/loads/<load id>/`. Nothing is written to EarthRanger. The
owner reads the plan and confirms it, which runs the job in load mode; a
plan can also be made again.

`needs_attention` means the job stopped because something needs a person: a
token the site rejects, or findings from the checks (the load page lists
them). Fix the cause, then continue the load or plan it again.

A load is long, so the job stops itself at a soft deadline and starts a
continuation that resumes from the load's ledger. Three variables set the
limits:

| Variable | Where | Default | Meaning |
| --- | --- | --- | --- |
| `LOAD_SOFT_DEADLINE_SECONDS` | load job | 79200 (22 h) | when the job stops and continues; keep it below the job's 24 h `--task-timeout` |
| `LOAD_MAX_CONTINUATIONS` | load job | 10 | continuations before the load is marked failed |
| `LOAD_STALE_AFTER_SECONDS` | service | 90000 (25 h) | how long an active load holds its dataset before the owner may continue or plan it again; keep it above the soft deadline plus startup |

Deleting a dataset deletes its loads, their plans and reports. It never
deletes anything already written to EarthRanger.

## 1. Provision

Prerequisites: `tofu`, `gcloud` authenticated with access to the project,
and a Firebase project with Google sign-in enabled (the webhook editor's
will do; add this service's domain to its authorised domains).

```sh
cd web/infra
cp terraform.tfvars.example terraform.tfvars   # set bucket_name, github_repo
tofu init
# if the project already has a (default) Firestore database (it does in cdip-dev-78ca):
tofu import google_firestore_database.default "projects/<project>/databases/(default)"
tofu plan
tofu apply
tofu output
```

This creates the Artifact Registry repository, the deploy and runtime
service accounts with their roles (including Secret Manager access limited
by an IAM condition to secrets named `smart-able-site-*`; the condition
cannot restrict creating secrets, only reading and deleting them), the WIF pool and provider for GitHub
Actions, the Firestore database (or adopts it), and the bucket with CORS
for browser uploads and a 30-day lifecycle rule on uploaded backups.

## 2. Configure the GitHub repository

Settings → Secrets and variables → Actions.

Variables:

| Variable | Value |
| --- | --- |
| `GCP_PROJECT_ID` | the project, e.g. `cdip-dev-78ca` |
| `GCP_REGION` | `us-central1` |
| `AR_REPOSITORY` | `smart-able` |
| `GCP_WIF_PROVIDER` | `tofu output wif_provider` |
| `GCP_SERVICE_ACCOUNT` | `tofu output deploy_service_account` |
| `GCP_RUNTIME_SERVICE_ACCOUNT` | `tofu output runtime_service_account` |
| `GCS_BUCKET` | `tofu output bucket` |
| `ALLOWED_EMAILS` | `@earthranger.com` (comma-separated emails or `@domain`s) |

Secrets:

| Secret | Value |
| --- | --- |
| `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID` | the Firebase web app's config |
| `SMART_DB_USER`, `SMART_DB_PASSWORD` | SMART's fixed embedded-database credentials (see `.env.example`); the job needs them |

## 3. Deploy

Deployment is release-driven: pushing a tag of the form `vX.Y.Z` runs
`.github/workflows/deploy.yml`, which builds both images, pushes them to
Artifact Registry, deploys the job with 16 GiB of memory and a 2-hour
timeout, then deploys the service. The tag becomes the version shown in
the app's header.

```sh
git tag -a v0.1.0 -m "First deployment"
git push origin v0.1.0
```

The repository's "release tags" ruleset allows only members of
`gundi-admins` to create, move, or delete such tags, so only they can
deploy. The workflow can also be run by hand from the Actions tab (Deploy
to Cloud Run → Run workflow), which deploys the chosen branch with its
short commit id as the version. Merging to `main` on its own does not
deploy.

The job's memory is for its in-memory `/tmp`: a 3 GB SMART install zip
needs the zip, its unzipped copy, the database copy, CSV, Parquet, and the
decrypted photos at once, about 10 GB. A Conservation Area export needs far
less. Raise `--memory` in the workflow if a job dies with an out-of-memory
error; lower it to save cost if only exports are uploaded.

The load job (`smart-able-load`) is deployed from the same image with a
command override, 2 GiB of memory and a 24-hour timeout.

Starting an extraction claims the dataset first (a Firestore transaction),
so while it is `queued` or `running` a second request gets 409 instead of
launching a second job. A job killed outright, by running out of memory or
by the 2-hour timeout, cannot record `failed`; its hold lapses 2.5 hours
after the claim, or after the job's start once it is running
(`EXTRACT_STALE_AFTER_SECONDS` on the service), and the owner can run the
extraction again. Other edits, such as sharing, do not extend it. Keep that
value above `--task-timeout`. The local backend enforces the same limit
itself (`EXTRACT_TIMEOUT_SECONDS`, default 7200): it kills a run that goes
past it, with every process the run started, and marks it `failed`.

## 4. Verify

1. Open the service URL, sign in with an allowed account; a disallowed
   account gets "This email is not allowed".
2. Upload a Conservation Area export (the fastest case). The dataset shows
   `uploading` → `queued` → `running` → `ready` within a few minutes; the
   log button on a failed one shows the extract output.
3. Open it: the browser loads with the conservation area's data. Share it
   with a colleague; they see it in their list and can open it, but have
   no Share or Delete buttons.

## Running locally

No GCP needed: the local backend keeps everything under `web-data/` and
runs the extraction as a subprocess, with authentication disabled.

```sh
uv sync --extra web
cd web && BACKEND=local AUTH_DISABLED=true uv run uvicorn app:app --reload --port 8080
```

Open http://localhost:8080. You are `dev@earthranger.com`; send an
`X-Dev-User: someone@earthranger.com` header (or set the `dev_user` cookie)
to be someone else, which is how sharing can be tried. That also means
anyone who can reach the port can be anyone: with `AUTH_DISABLED` the
service must only ever listen on localhost. The extract
toolchain (`./smart-able check`) must be installed, as for the command line.
`web/docker-compose.yml` runs the same thing inside the job image, which
has the toolchain.

Loading runs er-smart-sync, which needs its own virtualenv (it pins
pydantic 1; the web service needs pydantic 2). Once the release it pins
exists:

```sh
uv venv .venv-load && uv pip install --python .venv-load/bin/python -r web/requirements-load.txt
LOAD_PYTHON=$PWD/.venv-load/bin/python   # for the service's env, so start_load uses it
```

Before that release is tagged, install your checkout of
[earthranger-smart-utils](https://github.com/PADAS/earthranger-smart-utils)
instead:

```sh
uv venv .venv-load && uv pip install --python .venv-load/bin/python \
  -e /path/to/earthranger-smart-utils \
  google-cloud-firestore google-cloud-storage google-cloud-run google-cloud-secret-manager httpx
```

## Data handling

The bucket is private with public access prevention enforced; only the
runtime service account reads it, and every request to a dataset's files is
checked against its owner and `shared_with`. Uploaded backups are deleted
after 30 days by lifecycle rule; the extracted site stays until the owner
deletes the dataset. The job does write Parquet, including the credential
columns, but only to its temporary disk, which is discarded when it ends:
only the browser's data and photos (`work/site/`) are uploaded. The site's JSON
still holds ranger names and the photos are plaintext: treat the bucket as
you would a backup.

An EarthRanger site's API token is stored in Secret Manager as
`smart-able-site-<id>`, never in Firestore, and is deleted with the site.
The runtime account can read and delete only secrets with that prefix.
