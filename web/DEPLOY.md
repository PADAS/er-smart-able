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
| Loads | one document per load: dataset, site, options, status, stage, per-stage rows with metrics, findings, progress, continuations | Firestore `(default)`, collection `loads` |
| Files | `datasets/<id>/upload/<file>` (the backup), `datasets/<id>/site/...` (data JSON and decrypted photos), `datasets/<id>/loads/<load id>/...` (a load's plan and results) | a private GCS bucket |

Static assets (`web/static/`) ship in the service image and are served by
the service itself: `app.css` and `er-tokens.css` (the `--er-ui-*` design
tokens, taken from the EarthRanger design repository's `tokens.css`),
`pages.js`, `app.js`, the self-hosted Roboto in `fonts/` and the lockups in
`img/`. Nothing is loaded from a CDN or Google Fonts at run time; to refresh
the font run `python scripts/fetch_fonts.py`. The dataset viewer
(`browse/index.html`) is self-contained and keeps its own copy of the token values; keep the two in step.

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

Anyone who can read a dataset (its owner or someone it is shared with) can
load it from the app into an EarthRanger site they can read (one they
registered or one shared with them).

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
| `LOAD_NETWORK_TIMEOUT_SECONDS` | load job | 600 | longest wait for any one request to EarthRanger; a request that exceeds it fails its patrol, which the next run retries |
| `LOAD_WORKERS` | load job | 1 | patrols imported at a time; for experiments only, since EarthRanger creates a site's events one at a time and more workers are slower |
| `LOAD_QUIET_AFTER_SECONDS` | service | 3600 (1 h) | how long after a held load last wrote its record it still blocks a re-extract of its dataset; a load whose job was killed stops blocking after this, well before its slot lapses |
| `LOAD_STALE_AFTER_SECONDS` | service | 90000 (25 h) | how long an active load holds its slot (that conservation area into that site) before anyone who can read the dataset and the site may continue or plan it again; keep it above the soft deadline plus startup |

Deleting a dataset deletes its loads, their plans and reports. It never
deletes anything already written to EarthRanger.

A load reads the conservation area's tracks one patrol at a time, so its
memory does not grow with them (`docs/load-performance.md`). That holds for a
dataset extracted with this version or later, whose bundle is version 2
(`tracks.jsonl` and `tracks.index.json`). A dataset extracted earlier has a
version 1 bundle (`tracks.json`), which still loads but is read whole: it
needs about 5.5 times that file in the load job's memory, counting the copy on
`/tmp`. If such a load dies with "The configured memory limit was reached",
re-extract the dataset (its backup must still be stored) and load again. The
job still copies the export to its in-memory `/tmp`, so a large area needs
that much memory and no more; the load job's `--memory` stays where it is
until that copy is gone.

## Support view

The addresses in `SUPPORT_EMAILS` are the support staff. Signed in, each
may also see what they neither own nor were given: the home page has an
"All users" switch that lists every dataset and site, and they can open any
dataset's page, its browser, and its loads with their plans, findings,
reports and logs. Such a page says "Support view: read-only".

That is all it grants. Sharing lets a person start, run and delete loads,
which write to EarthRanger with the site owner's token; support view lets
them do none of it. Every route that writes keeps the check it had, and
`tests/test_web_support.py` tries each one as a support user and fails if a
new one is added without deciding what support gets. A support person
still has an owner's or a reader's rights on what they own or were shared.
No part of a site's token is shown through support view.

An address must also pass `ALLOWED_EMAILS` to sign in, and the sign-in
provider must have verified it (Google does). The role is worked out on
every request from the variable and stored nowhere, so removing an address
ends that person's support view when the change is deployed.

Each view of someone else's data is written to the service's log, at most
once per person and item in ten minutes by each running instance (so a few
lines for one view are normal, and a restart starts the count again):

```
support_view viewer=<email> kind=<dataset|load|load_file|browser|list> id=<id> owner=<owner's email>
```

To read the record, search the `smart-able` service's logs in Cloud
Logging for `support_view`. Owners are not shown it in the app; the help
and the guide tell them support staff can view.

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
by an IAM condition to secrets named `smart-able-site-*`, plus a custom
role that only creates secrets, because creation is checked against the
project and a name condition would deny it), the WIF pool and provider for GitHub
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
| `SUPPORT_EMAILS` | the support staff, who may view every dataset, site and load but change none (see "Support view"): whole addresses separated by spaces, for example `ana@earthranger.com ben@earthranger.com`. An `@domain` entry is ignored. Unset, nobody is support. Keep it to the people who help users migrate. |
| `ALLOWED_EMAILS` | who may sign in and be shared with: whole addresses and `@domain` suffixes, separated by spaces, commas or semicolons, for example `@earthranger.com @partner.org`. Unset, the deploy uses `@earthranger.com`; an empty value allows any Google account. |

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
command override, 8 GiB of memory, 2 CPUs (Cloud Run requires two above
4 GiB) and a 24-hour timeout.

Its memory is for the conservation area's tracks. The job copies the export
to its in-memory `/tmp` and then reads `bundle/tracks.json` whole, which
takes about 4.4 times the file's size: an 800 MiB track file needs about
4.5 GiB in all, and 8 GiB carries a track file of about 1.4 GiB. A load
whose job dies with "The configured memory limit was reached" within a
minute of starting has a track file too big for the limit; raise `--memory`
in the workflow (and `--cpu` with it: 4 CPUs above 8 GiB).

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

## The getting-started site

`https://padas.github.io/er-smart-able/` is the guide for support people
migrating a site with the hosted app. It is built from `web/guide/*.md`
(the guide) and `web/help/*.md` (the app's help drawer, from the same
files) by `scripts/build_pages.py`, with the page shell and stylesheet in
`web/site/` and the app's tokens, font and lockup.

To build it locally and look:

```sh
python scripts/build_pages.py        # writes _site/ (git-ignored)
open _site/index.html
```

A screenshot goes in `web/guide/img/` and is written `![what it shows](img/name.png)`;
the build copies it, and fails on a missing file or empty alt text.

Alternatives, of which the reader follows one, are tabs: mark each heading
`### Name {: .tab }`, one section after another. A tab that stands alone fails
the build.

A link in a page to another page's `.md` becomes that page; a link to any
other repository file goes to it on GitHub; a link to a file that does not
exist fails the build.

### Languages

The site is in English, French, Spanish, Portuguese and Swahili. English is
the source; its pages keep their addresses, and each other language is a
folder (`fr/`, `es/`, `pt/`, `sw/`) with the same page names.

- `web/static/locales/languages.json` lists the languages, in the order the
  header's switcher offers them.
- `web/site/locales/<code>.json` holds the words of the page shell
  (navigation, previous and next, the footer, the notes) in one language.
- A translated page sits beside its English page in a folder named for the
  language: `web/guide/<code>/` and `web/help/<code>/`, with the same file
  name. A page with no translation is built from the English page and says
  so.
- `docs/translation-glossary.md` lists the terms the translations use and
  where each came from. Read it before changing a translation.

The four translations were written by machine. Until a fluent speaker has
read a language through, every page in it carries a note saying so.

**To correct a translation,** edit the page under `web/guide/<code>/` or
`web/help/<code>/`. Keep its steps, tabs, pictures, set-apart notes, links
and the names in code exactly as the English page has them; if one is
lost, the build fails and says which. A translated page links to another
page by its real path (`03-your-first-migration.md`,
`../../help/<code>/02-sites.md`) and to a picture as `../img/name.png`.

**To mark a language reviewed,** set `"reviewed": true` for it in
`web/static/locales/languages.json` and add the reviewer's name to the
glossary. The note goes from that language's pages and from the app.

#### The app's own words

The app itself (not the site) reads its messages from
`web/static/locales/<code>.json`, through `T`, `t` and `tn` in
`web/static/i18n.js`. `en.json` is the source and the fallback: a message a
language lacks shows in English. The reader picks a language in the header;
it is remembered in the browser (`localStorage.lang`). A language marked
`"reviewed": false` in `languages.json` shows the "machine translated" note
under the header; setting it to `true` removes the note.

- **To correct a message,** edit it in `web/static/locales/<code>.json`. Keep
  every `{{placeholder}}` exactly as the English message has it, and the
  `_one`/`_other` forms of a count. Read `docs/translation-glossary.md` first.
- **To add a phrase,** add it to `en.json` first, then to `fr.json`,
  `es.json`, `pt.json` and `sw.json`. Run
  `node --test "tests/js/*.test.js"`: the tests name each message a language
  is missing, an unknown key, a changed placeholder, and an English message
  nothing uses. Text in `pages.js` is made with `T`, never typed in.
  `tests/js/pseudo.test.js` renders every screen with every message
  replaced and fails on any word left over, so a screen with a new state
  needs a fixture there.
- **A server error** carries a `code`; the browser shows `errors.<code>`. A
  new error in `web/` is raised as an `ApiError` with a code, and the code
  gets a message in every language. A code the browser does not know is
  shown as the server worded it, in English.
- **The help drawer** asks `/api/help?lang=`, which serves the translated
  pages of `web/help/<code>/`, or the English page where there is none.
- **A load's findings** are stored in English, most of them worded by
  `er-smart-sync`. `web/findings.py` also stores which message each one is
  (`key`) and the names and counts in its sentence (`params`); the browser
  shows `findingText.<key>` in the reader's language, with the stored
  English under it ("Original text"). A finding it does not recognise has
  no key and is shown in English. To add one: its key in `web/findings.py`
  (`FINDING_KEYS` and the rule that assigns it), the English title and fix
  under `findingText`, then every language; the tests name what is missing.
  In English the page shows the stored text, unchanged.

What stays in English on purpose: the dataset browser, the live log, the
quirks reference (it is marked `lang="en"` in the help), a finding's detail
lines and copyable values and the findings listed in
`docs/translation-glossary.md` ("Findings that still show in English"), text a
job stored
on a dataset or load (its `error`, the log tail), the EarthRanger admin menu
names, and the column headers of the CSV downloads.

**When an English page changes,** change its four translations in the same
pull request. The build catches a missing step, not a changed sentence.

**To add a language,** add it to `languages.json` and add its
`web/site/locales/<code>.json`. Its pages show in English until they are
translated.

`.github/workflows/pages.yml` publishes it on every merge to `main` that
touches its sources, and can be run by hand from the Actions tab. Once, a
repository admin sets Settings → Pages → Source to **GitHub Actions**.

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
checked against its owner and `shared_with`; the support staff ("Support
view", above) may also read them, and each such read is logged. Uploaded backups are deleted
by lifecycle rule after `upload_retention_days` (30 by default; see below), or
sooner by the dataset's owner from the dataset page; the extracted site stays
until the owner deletes the dataset. The dataset page shows the date the
backup goes. That date comes from `UPLOAD_RETENTION_DAYS` on the service,
which the deploy sets from the repository variable of the same name (30 if
unset): if you change the rule's `upload_retention_days` in
`web/infra/terraform.tfvars`, set the repository variable to the same number,
or the page will show the wrong date. Locally there is no rule and the
variable is unset, so the page says the backup is kept until deleted. The rule
matches names ending in `.zip` or `.bak` by case, so a new upload is stored
with its extension in lower case; an older upload stored as `.ZIP` is never
deleted by the rule, and its page says so. The job does write Parquet, including the credential
columns, but only to its temporary disk, which is discarded when it ends:
only the browser's data and photos (`work/site/`) are uploaded. The site's JSON
still holds ranger names and the photos are plaintext: treat the bucket as
you would a backup.

An EarthRanger site's API token is stored in Secret Manager as
`smart-able-site-<id>`, never in Firestore, and is deleted with the site.
The runtime account can create secrets (a custom role holding only that permission) but read, add versions to, and delete only secrets with that prefix.
