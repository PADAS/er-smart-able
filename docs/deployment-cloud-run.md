# Deploying smart-able as a web application

Notes from 2026-10-06 on running the browser as a Cloud Run service, in
the pattern of [PADAS/gundi-webhook-editor](https://github.com/PADAS/gundi-webhook-editor).
Decided and built on 2026-10-06: see [web/DEPLOY.md](../web/DEPLOY.md). The
answers to the open questions below: datasets are owned by their uploader
and shared by email, as in the webhook editor; the allowlist is
`@earthranger.com`; upload-and-extract (phase two) is in from the start;
photos are streamed through the service; the Parquet is not produced in the
cloud. Retention is a 30-day lifecycle rule on uploads. The rest of this
note is the assessment as it stood.

## What exists today

smart-able is an offline pipeline plus a static site. `./smart-able
extract` needs Java 21, the DuckDB CLI, OpenSSL, and uv, takes minutes, and
writes `work/parquet/` and `work/site/`. The site is one HTML file that
fetches JSON and photos from relative paths; `./smart-able serve` is
Python's `http.server` on localhost. Everything under `work/` is sensitive
(ranger names, patrol routes, photos), and `work/smartdb` and `work/csv`
still hold SMART password hashes and Connect logins; only the Parquet and
the site are redacted.

## The pattern to copy

gundi-webhook-editor, read from GitHub on 2026-10-06:

- FastAPI app, `python:3.12-slim` image, uvicorn on `$PORT`.
- Firebase Authentication with an email or domain allowlist
  (`ALLOWED_EMAILS`), verified server-side in `auth.py`; `AUTH_DISABLED`
  for local work; Firebase emulators via `docker compose`.
- Infrastructure in OpenTofu under `infra/`: Artifact Registry, a deploy
  service account, a runtime service account, Workload Identity Federation
  for keyless GitHub Actions, Firestore.
- `.github/workflows/deploy.yml` on push to `main`: build, push to
  Artifact Registry, `deploy-cloudrun` with `--allow-unauthenticated` (the
  app does its own auth) and env vars from repository secrets.
- `DEPLOY.md` walks through provisioning and the GitHub variables.

`auth.py` and `deploy.yml` transfer almost verbatim. What differs is the
data.

## Phase one: serve pre-built sites behind auth

Keep extraction offline, where the tools and the backups already are.
After `./smart-able all`, upload `work/site/` to a GCS bucket under a
dataset prefix (one per backup, e.g. `region5-2026-10/`). The Cloud Run
service:

- requires a signed-in, allowlisted user for every route, as the webhook
  editor does;
- lists the datasets in the bucket on a landing page;
- serves a dataset at `/sites/<id>/`, streaming `index.html`, `data/*.json`
  and `attachments/**` from GCS. Photos are about 1.4 GB per CA, so stream
  rather than buffer, and consider signed URLs for the image requests;
- never touches the Parquet, which keeps the credential question closed.

The browser needs no change for this: its fetches are relative, so a
dataset prefix works, and the data-format banner still applies. The one
addition is an `upload` command in `smart-able` (`gsutil rsync` of
`work/site/` to the prefix) and a short DEPLOY.md.

Cost is near zero at minimum instances of zero. Nothing of the extract
toolchain goes in the image.

## Phase two: upload a backup and extract in the cloud

Only if people without the toolchain need to run extractions. A SMART
install zip is 2.9 GB and extract takes minutes with Java, DuckDB and
OpenSSL, so it belongs in a Cloud Run Job, not the request path:

- the service accepts an upload straight to GCS (resumable, signed URL),
  then triggers a Job with the object path;
- the Job image carries Java 21, the DuckDB CLI, OpenSSL and uv, runs
  `./smart-able all` against the object, and writes `work/site/` back to
  the dataset prefix;
- the service shows job status and the new dataset when done.

Separate piece of work; phase one does not depend on it.

## Open questions

1. **Tenancy.** Are datasets visible to everyone on the allowlist, or
   scoped per user or per organisation? This decides the bucket layout
   and whether the landing page needs an ownership model (Firestore, as
   the webhook editor uses, would do).
2. **Parquet access.** Should analysts be able to download the Parquet
   from the app? If so, where it lives and who can fetch it; the
   credential columns are already out of it by default.
3. **Photos.** Proxy through the service (simple, costs egress twice) or
   signed GCS URLs minted per page load (cheaper, more moving parts).
4. **Project and domain.** The webhook editor lives in `cdip-dev-78ca`,
   `us-central1`. Same project, or a separate one for data this sensitive?
5. **Retention.** Backups contain personal data. How long do datasets
   stay in the bucket, and who deletes them?
6. **Phase two at all.** Who would use upload-and-run, and is a managed
   laptop with the toolchain the simpler answer for now?

## Next steps

- Decide questions 1 and 4; they shape everything else.
- Phase one is roughly: `app.py` (auth, listing, streaming from GCS),
  `Dockerfile`, `infra/` copied from the webhook editor minus Firestore
  plus a bucket, `deploy.yml`, `DEPLOY.md`, and `./smart-able upload`.
