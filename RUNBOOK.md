# smart-able runbook

How to take a SMART Desktop backup through Extract and Browse, check the
results, and clean up. For what the tool is and why, see [README.md](README.md).
For the SMART tables themselves, see
[docs/smart-data-model.md](docs/smart-data-model.md).

> **The output is sensitive.** A SMART backup contains ranger names, patrol
> routes, and photos. Everything smart-able produces goes into `work/`, which
> is gitignored. Read [Handling the data](#handling-the-data) before you start.

## 1. Prerequisites

| Tool | Version | Used for | Install (macOS / Debian-Ubuntu) |
| --- | --- | --- | --- |
| Java JDK | 19 or newer (21 recommended) | reading the Derby database | [SDKMAN](#installing-java-with-sdkman) (recommended), or `brew install openjdk@21` / `apt install openjdk-21-jdk` |
| DuckDB CLI | 1.x | CSV → Parquet, building browser data | `brew install duckdb` / [duckdb.org/docs/installation](https://duckdb.org/docs/installation/) |
| [uv](https://docs.astral.sh/uv/) | any recent | Python dependencies, timezone inference, local web server (uv downloads Python 3.9+ if you don't have one) | `brew install uv` / `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| OpenSSL | any | decrypting attachments | preinstalled on macOS / `apt install openssl` |
| unzip | any | `.zip` backups | preinstalled on macOS / `apt install unzip` |

smart-able is a bash script, so it runs on macOS and Linux. On Windows, run it
inside WSL.

### Installing Java with SDKMAN

If you haven't set up Java before, [SDKMAN](https://sdkman.io/) is the easiest
way. It installs JDKs into your home folder (no admin rights needed), lets you
keep several versions side by side, and works the same on macOS, Linux, and
WSL.

```sh
curl -s "https://get.sdkman.io" | bash        # install SDKMAN
source "$HOME/.sdkman/bin/sdkman-init.sh"     # or open a new terminal
sdk list java                                 # find the newest 21.x "Temurin" line
sdk install java 21.0.12+1.1-tem              # use the identifier from the list
java -version                                 # should report version 21
```

Pick Java 21 explicitly: a bare `sdk install java` installs SDKMAN's current
default, which may be a newer Java that smart-able hasn't been tested with.
If you already have other Java versions, `sdk default java <identifier>` makes
21 the one your terminals use.

The SMART-specific dependency, Apache Derby, is bundled in `lib/derby/`
(version 10.17.1.0). That is the version SMART 8 uses, and it also reads the
older-format databases of SMART 7.5; it is why Java 19 or newer is required.

### Supported SMART versions

| SMART Desktop | Derby it ships | Status |
| --- | --- | --- |
| 7.5.0 – 7.5.9 | 10.15.1.3 | Supported. Tested with a 7.5.6 install (database schema 7.5.4). |
| 8.0.0 – 8.1.3 | 10.17.1.0 | Supported. Schema differences are handled (see [docs/smart-data-model.md](docs/smart-data-model.md#version-differences)) but not yet tested against a real 8.x backup. |

Older versions (before 7.5) are untested. Derby 10.17 can read their
databases, but the browser expects tables such as `db_version` that very old
schemas lack.

## 2. One-time setup

```sh
./smart-able setup
```

This checks the tools above, runs `uv sync` to create `.venv/` with the
Python dependencies pinned in `uv.lock`, installs DuckDB's spatial extension
(both need internet once), and creates `.env` from `.env.example`.

Python dependencies are declared in `pyproject.toml`. To add or change one,
edit it there and run `uv lock` (or `uv add <package>`), then commit the
updated `uv.lock`; `./smart-able setup` installs exactly what the lock says.

Then open `.env` and fill in `SMART_DB_USER` and `SMART_DB_PASSWORD`. These
are SMART's fixed embedded-database credentials, the same for every SMART
install; `.env.example` says where they are defined in the SMART source.

## 3. Get a backup

`./smart-able extract` accepts any of these, and finds the database and the
attachment folder inside it:

| You have | Point smart-able at |
| --- | --- |
| A SMART Desktop installation folder (e.g. copied from a field computer) | the installation folder |
| Just its `data/` folder | `data/` |
| Just the database folder | the `smartdb/` folder (attachments will be skipped) |
| A SMART system backup zip (`SMART_<date>.bak.zip`) | the `.zip` file |
| A Conservation Area export (SMART Desktop: File → Export Conservation Area) | the `.zip` file, or the folder it unzips to |

The database is the folder that contains `service.properties` and `seg0/`;
attachments are in a folder named `filestore`.

A Conservation Area export is different: it holds one conservation area as
plain-text table dumps (`database/*.dat` and `.def`) plus its `filestore`,
and no Derby database. smart-able reads those dumps directly, so the Java and
Derby steps, and the `.env` credentials, are not needed for it. Column types
come from `extract/smart_schema.tsv` (taken from a SMART 7.5.4 database), so
a column added in a later SMART version arrives as text, with a warning (see
[Warnings](#warnings)), until that file is refreshed; the file's header says
how.

**Close SMART Desktop first** if you are reading a live installation. smart-able
copies the database before opening it and never modifies the original, but
copying a database that SMART is writing to can produce an inconsistent copy.

## 4. Run the pipeline

```sh
./smart-able all "/path/to/SMART backup"     # extract + browse
./smart-able serve                           # then open http://localhost:8765/
```

Quote the path if it has spaces. You can also run the stages one at a time:

### Extract

```sh
./smart-able extract "/path/to/SMART backup"
```

| Step | Output | What to check |
| --- | --- | --- |
| Locate | prints the database and filestore paths | Both found. "filestore: (none found)" means no photos. |
| Copy | `work/smartdb/` | — |
| Dump | `work/csv/` | `done: N rows across M tables`. M is typically around 200; it varies with SMART version and installed plugins. For a Conservation Area export this step reads the export's table dumps instead of Derby, and prints the conservation area's name. |
| Version | prints `SMART database version` | The schema version, e.g. `7.5.4` or `8.1.0`. SMART 8.1.1–8.1.3 still report `8.1.0`, because their schema didn't change. |
| Schema check | `schema matches smart_schema.tsv (7.5.4)`, or warnings | Read any warnings; see [Warnings](#warnings). |
| Parquet | `work/parquet/` | `converted M tables`. M must equal the dump's table count. |
| Decrypt | `work/site/attachments/` | `failed: 0`. |

A ~150 MB database with 1.4 GB of attachments takes about 3 minutes; most of
that is decryption.

### Browse

```sh
./smart-able browse
```

| Step | Output | What to check |
| --- | --- | --- |
| Build | `work/site/data/*.json` | "Profiles data found" or "no Profiles tables; skipping Profiles". |
| Timezones | `work/site/data/timezones.json` | One line per CA with a plausible zone. The demo CA "SMART" is in Gabon (`Africa/Libreville`). |
| Attachments | `all N attachments the database refers to are present`, or a warning | See [Warnings](#warnings). |

### Warnings

smart-able makes a few assumptions about the data; where it can check them,
it prints a `warning:` line rather than stopping. They mean:

| Warning | Meaning | What to do |
| --- | --- | --- |
| `this data is SMART schema X; smart_schema.tsv ... were written against 7.5.4` | The backup comes from a different SMART version than the one smart-able was built against. The schema differences follow as further warnings. | Check the output against [Version differences](docs/smart-data-model.md#version-differences). Differences not listed there are new: add them to the doc and, once handled, refresh `extract/smart_schema.tsv` (its header says how). |
| `the SMART schema version of this data is unknown` | No `db_version` table (very old SMART, or a damaged export). | Treat the data as unverified. |
| `new table` / `new column` | The data has tables or columns that `smart_schema.tsv` doesn't know. The browser ignores them. For a Conservation Area export, a new column was loaded as text, since its type is unknown. | As above: document, then refresh the snapshot. |
| `missing table` / `missing column` | The data lacks something the snapshot has. If the browser needs it, `browse` will fail on that table. | As above. For an export, missing *tables* are only noted, since exports omit the install-wide ones (`connect_*`, `login_log`, ...). |
| `type change` | A column's type differs from the snapshot (databases only; exports have no types). | Check whether the browser SQL still works on it. |
| `N of M attachments the database refers to are not in the backup` | The database has attachment rows whose files are missing from the filestore (or the export). The browser shows those as missing photos. | Nothing to fix in smart-able; the source install has the same gaps. |
| `line 1 of conservationarea.dat is not a conservation area uuid` | The export is not in the layout smart-able expects. | The attachments won't decrypt; check the export with SMART's own import first. |

### Serve

```sh
./smart-able serve          # port 8765
./smart-able serve 9000     # another port
```

The server listens on `localhost` only, so other machines on the network can't
reach it. Stop it with Ctrl-C.

## 5. Check the results

In the browser:

1. **Overview**: the patrol, waypoint, and observation totals look right for
   the site, and the waypoints-per-year chart covers the expected years.
2. **Map**: points fall inside the CA boundaries. Basemaps need internet; pick
   "No basemap" to work offline.
3. **Patrols**: open a recent patrol; its map shows the GPS track and its
   waypoints list observations.
4. **Profiles**: entities listed, or "This backup has no Profiles data."

For a closer look, query the Parquet directly:

```sh
duckdb -c "select count(*) from 'work/parquet/waypoint.parquet'"
duckdb -c "select * from 'work/parquet/db_version.parquet'"
```

### Things that look wrong but are normal

- **Missing photos.** Older backups often list photos in the database whose
  files are no longer in the filestore. The browser hides thumbnails that
  don't load. To measure coverage, compare `wp_attachments` rows to files
  under `work/site/attachments/`.
- **Extra conservation areas.** Most databases include SMART's demo CA
  ("Example Conservation Area", id `SMART`) and the `CCAA` pseudo-CA.
- **Odd dates.** Patrols dated 1970-01-01 are data-entry errors in SMART, not
  extraction errors.

## Handling the data

- Everything generated is under `work/` (the database copy, CSV, Parquet,
  browser data, and decrypted photos). It is gitignored; never commit it or
  copy it into the repository.
- To keep the output somewhere else, such as an encrypted volume, set
  `SMART_ABLE_WORK`:
  `SMART_ABLE_WORK=/Volumes/Secure/my-site ./smart-able all <backup>`
- The decrypted photos are plaintext copies of encrypted files. Delete them
  when you're done: `./smart-able clean` removes the whole work directory.
- `.env` holds the database credentials and is gitignored too.

## Re-running and updating

- Each stage replaces its own outputs, so re-running is safe. To process a
  different backup, run `./smart-able clean` first, or point
  `SMART_ABLE_WORK` at a new folder to keep both.
- `work/site/index.html` is a symlink to `browse/index.html`, so after editing
  the browser just reload the page. After editing the SQL in `browse/`, run
  `./smart-able browse` again.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `SMART_DB_USER / SMART_DB_PASSWORD not set` | `.env` missing or empty | Fill in `.env` (see `.env.example`). |
| `Connection authentication failure occurred. Reason: Invalid authentication` | Wrong credentials | Check the values in `.env`. |
| Derby error mentioning `XSLAN` or "incompatible format" | The database was written by a Derby newer than the bundled 10.17 (a SMART release after 8.1) | Replace the three jars in `lib/derby/` with that Derby version (`derby`, `derbyshared`, `derbytools` from Maven Central, group `org.apache.derby`) and use a JDK it supports. |
| `Java N found; Java 19 or newer is required` | Old JDK | Install JDK 21, e.g. with [SDKMAN](#installing-java-with-sdkman). |
| `no SMART Derby database ... or Conservation Area export ... under: <path>` | The path doesn't contain a database or an export | Point at the install folder, `data/`, `smartdb/`, a backup `.zip`, or a Conservation Area export `.zip`. |
| Any other Java/Derby exception during the dump | Varies | Read `work/derby.log`. If SMART was open while you copied the backup, close it and run `extract` again. |
| `FAILED: <file>` lines while decrypting | A truncated or corrupt attachment | Isolated failures are safe to ignore; many failures mean the wrong filestore. |
| `browse` fails at `INSTALL spatial` | No internet the first time | Run `./smart-able setup` once while online. |
| `Address already in use` from `serve` | Port taken | `./smart-able serve 8766` |
| Browser says "Could not load data" | `browse` hasn't run, or failed | Run `./smart-able browse` and check its output. |
| Timestamps shown without a timezone | No `.venv`, so timezone inference was skipped | Run `./smart-able setup`, then `./smart-able browse`. |
| `uv: command not found` | uv is not installed | Install it (see [Prerequisites](#1-prerequisites)) and open a new terminal. |
| Map tiles don't load | Offline, or the tile server is blocked | Choose "No basemap"; points and boundaries still draw. |
| Some photos don't open | The backup or export lacks the files; `browse` warned how many. | Nothing to fix in smart-able. The source install has the same gaps. |
