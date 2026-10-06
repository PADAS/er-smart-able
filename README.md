# smart-able

**Extract, Browse, Export, and Load SMART conservation data — toward EarthRanger.**

[SMART](https://smartconservationtools.org/) Desktop keeps a conservation
area's patrols, observations, and photos in an embedded Apache Derby database
that only SMART itself can read. smart-able opens a copy of that database
without SMART, turns it into open formats, and lets you explore it, as the
first half of moving the data into [EarthRanger](https://www.earthranger.com/).

The name reads as "SMART EBEL": the four stages.

| Stage | What it does | Status |
| --- | --- | --- |
| **E**xtract | Dumps every table of a SMART backup to Parquet, and decrypts its photo attachments. | Done |
| **B**rowse | A local web app for patrols, maps, observations, Profiles, and photos. | Done |
| **E**xport | Write the data in a standard interchange format. | Planned |
| **L**oad | Create the corresponding events, patrols, and subjects in an EarthRanger site. | Planned |

## Quick start

Works with backups from SMART Desktop 7.5.x and 8.0–8.1.x
([details](RUNBOOK.md#supported-smart-versions)). You need Java 19+ (21
recommended), the DuckDB CLI, [uv](https://docs.astral.sh/uv/) (which
installs Python 3.9+ itself if needed), and OpenSSL (details in the
[runbook](RUNBOOK.md#1-prerequisites)). New to Java? Install it with
[SDKMAN](https://sdkman.io/) ([steps](RUNBOOK.md#installing-java-with-sdkman)).
Then:

```sh
./smart-able setup                                  # check tools, install Python deps, create .env
$EDITOR .env                                        # fill in the SMART database credentials
./smart-able all "/path/to/SMART backup"            # extract + browse
./smart-able serve                                  # open http://localhost:8765/
```

The backup can be a SMART Desktop installation folder, its `data/` folder, or
a SMART system backup `.zip`.

## What you get

All output goes into `work/` (gitignored):

| Path | Contents |
| --- | --- |
| `work/parquet/` | One Parquet file per SMART table, with exact column types. Query it with DuckDB, pandas, or Polars. |
| `work/site/` | The browser: `index.html`, `data/` (JSON), and `attachments/` (decrypted photos). |
| `work/smartdb/`, `work/csv/` | The database copy and the intermediate CSV dump. |

The browser has six tabs:

- **Overview**: totals, waypoints per year, top observation categories.
- **Patrols**: searchable list. A patrol opens to its legs, members, GPS track
  map, and waypoints; each waypoint opens to its observations; each
  observation opens to its category path, data-model key, and attributes.
- **Map**: every waypoint on OpenStreetMap or satellite imagery, with time
  filters.
- **Observations**: the category tree, with text search and time filters.
- **Profiles**: entities and records from SMART's optional Profiles plugin.
- **Schema**: how the SMART tables relate.

SMART stores timestamps without a timezone. smart-able infers each
conservation area's timezone from its GPS locations and uses it throughout.

## Repository layout

```
smart-able              the command: setup, check, extract, browse, serve, all, clean
extract/
  DumpSmartDb.java        Derby → CSV (+ column types), via JDBC
  csv_to_parquet.sh       CSV → Parquet (DuckDB)
  decrypt_filestore.sh    decrypts SMART's AES-encrypted attachments
browse/
  build_browser_data.sql  Parquet → browser JSON
  build_profiles.sql      the same for Profiles (run only when present)
  infer_timezones.py      GPS → IANA timezone per conservation area
  index.html              the browser (single file, no build step)
lib/derby/              Apache Derby 10.17 jars (Apache-2.0)
pyproject.toml          project metadata and Python dependencies (managed with uv)
uv.lock                 pinned Python dependency versions
docs/
  smart-data-model.md     how SMART stores its data
RUNBOOK.md              step-by-step operation, checks, troubleshooting
```

## Data handling

A SMART backup contains ranger names, patrol routes, and photos, and
smart-able's output is a readable copy of all of it. Keep `work/` out of
version control (it is gitignored) and delete it with `./smart-able clean`
when done. `./smart-able serve` listens on localhost only. The
[runbook](RUNBOOK.md#handling-the-data) covers keeping the output on an
encrypted volume.

The SMART database credentials are SMART's fixed built-in ones; they are read
from `.env` (gitignored), not stored in the code.

## Design

The browser follows the EarthRanger design system (internal; color tokens,
typography, light and dark modes, Material icons), so the data previews the
way it will look in the system it is moving to.

## Documentation

- [RUNBOOK.md](RUNBOOK.md): prerequisites, running each stage, checking the
  output, troubleshooting.
- [docs/smart-data-model.md](docs/smart-data-model.md): SMART's tables,
  observation values, time, geometry, and attachment encryption.

## License

Apache License 2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE). Bundles
Apache Derby, also Apache-2.0.
