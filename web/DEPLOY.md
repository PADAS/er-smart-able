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
| Index | one Firestore document per dataset: owner, `shared_with`, status, counts | Firestore `(default)`, collection `datasets` |
| Files | `datasets/<id>/upload/<file>` (the backup), `datasets/<id>/site/...` (data JSON and decrypted photos) | a private GCS bucket |

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
service accounts with their roles, the WIF pool and provider for GitHub
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

Push to `main` (or run the workflow by hand). `.github/workflows/deploy.yml`
builds both images, pushes them to Artifact Registry, deploys the job with
16 GiB of memory and a 2-hour timeout, then deploys the service.

The job's memory is for its in-memory `/tmp`: a 3 GB SMART install zip
needs the zip, its unzipped copy, the database copy, CSV, Parquet, and the
decrypted photos at once, about 10 GB. A Conservation Area export needs far
less. Raise `--memory` in the workflow if a job dies with an out-of-memory
error; lower it to save cost if only exports are uploaded.

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
to be someone else, which is how sharing can be tried. The extract
toolchain (`./smart-able check`) must be installed, as for the command line.
`web/docker-compose.yml` runs the same thing inside the job image, which
has the toolchain.

## Data handling

The bucket is private with public access prevention enforced; only the
runtime service account reads it, and every request to a dataset's files is
checked against its owner and `shared_with`. Uploaded backups are deleted
after 30 days by lifecycle rule; the extracted site stays until the owner
deletes the dataset. The Parquet is not produced in the cloud at all, so the
credential columns never leave the job's temporary disk. The site's JSON
still holds ranger names and the photos are plaintext: treat the bucket as
you would a backup.
