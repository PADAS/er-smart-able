# One sidebar for the app and the data browser

## Purpose

Getting from a dataset back to the list of datasets is clumsy, and it is
different in each place. The dataset page has only a breadcrumb line. The
browse pages have a single "Back to dataset" link at the top right. The
two are separate documents with separate navigation, so the data of a
dataset and the migration of that dataset feel like two applications.

A left sidebar, as EcoScope has, replaces the top band, the breadcrumb
line and the dataset's tabs. It is the same on every page, including the
browse pages.

## What exists today

- **The app** (`web/templates/index.html`, `web/static/app.js`,
  `web/static/pages.js`, `web/static/app.css`): one document, routed by
  the location hash. A top band holds the logo (a link home), the app
  name, the language select, the help button and the account menu (theme,
  sign out, version). Under it is a breadcrumb line (`#crumbs`). Pages:
  home (the datasets, with the sites as a section below them; `#/sites`
  opens home at that section), a dataset with four tabs (`#/datasets/{id}`,
  `/loads`, `/rangers`, `/backup`), and a load
  (`#/datasets/{id}/loads/{load}`).
- **The data browser** (`browse/index.html`): one self-contained
  document, served at `/d/{id}/` and also usable from a local folder
  (`file://`), where it has no server. It has its own top band and its
  own collapsible list of eight views down the left (`#sidenav`, state
  remembered under `localStorage.sidenav`): Overview, Patrols, Rangers,
  Map, Observations, Data model, Profiles, Schema, with a conservation
  area filter above them. Its view is in its own location hash. It is in
  English only. Served by the app, it shows a link back to the dataset
  and the dataset's name (`hostedHeader`).
- Both read the theme from `localStorage.theme`. Requests from both are
  authenticated by the session cookie.

## What was decided

With the user, in conversation and from mockups:

- A left sidebar on every page (option 1 of three; see Approaches).
- Inside a dataset the sidebar shows only that dataset (arrangement B of
  two): a link back to the datasets, then the dataset's own entries in
  two groups, **Data** and **Migration**. The user chose it because it
  separates browsing the data from the migration.
- The dataset's Overview stays its landing page. The browser's own
  "Overview" is renamed "Summary".
- "Rangers" under Migration is renamed "Match rangers".
- Sites becomes a page of its own.
- The top band, the breadcrumb line and the dataset's tabs go away.
- The sidebar is a light surface, as EcoScope's is: the page's light
  background with the colour logo (`web/static/img/er-lockup-h.svg`) and
  a pale highlight on the current entry. In the dark theme it takes the
  dark surface and the white logo. It is not the brand teal of today's
  band.
- The browser stays a separate self-contained document. Each document
  draws the sidebar.

## The sidebar

Outside a dataset (home, sites):

```
[logo] SMART migration
[collapse]
  Datasets
  Sites
  ...
  ─────────
  Theme
  Language
  Help
  account
```

Inside a dataset (its pages, a load's page, and every browser view):

```
[logo] SMART migration
[collapse]
  ‹ Datasets
  EXAMPLE AREA 2026            the dataset's name, not a link
  Overview
  DATA   [conservation area]   the filter, in the browser only
  Summary
  Patrols
  Rangers
  Map
  Observations
  Data model
  Profiles
  Schema
  MIGRATION
  Loads
  Match rangers
  Backup
  ─────────
  Theme
  Language
  Help
  account
```

Rules:

| Matter | Rule |
|---|---|
| Current page | Its entry is marked, with `aria-current="page"`. A load's page marks Loads |
| Where entries lead | Overview, Loads, Match rangers, Backup: the app's routes, unchanged. The eight Data entries: `/d/{id}/` at that view. From the browser, Migration entries and Overview are links to `/#/datasets/{id}...`; from the app, Data entries are links to `/d/{id}/#...`. Between the two documents a click is a page load |
| A dataset that is not ready | The Data entries are shown, disabled (the browser answers 409 until the dataset is ready) |
| Entries a user may not open | Disabled, by the rule the tabs use today (`tabAllowed`) |
| Collapse | One control folds the sidebar to icons. Both documents read and write the same remembered state (`localStorage.sidenav`, as the browser does now), so the sidebar does not change width between them. On a narrow screen the open sidebar lies over the page, as the browser's does now |
| Bottom group | Theme (system, light, dark), Language, Help, and the account (the address, sign out, the version). In the app these do what the band's controls do today |
| The machine-translation note | Stays at the top of the page's content |
| Signed out | No sidebar entries except Theme and Language; the sign-in panel as today |
| Support staff | The switch for everyone's datasets and sites is shown on the home page and on the sites page, to support staff only. It is one stored choice (`localStorage.allUsers`), as today, and both pages follow it (my call) |

The browser's entries when it is opened from a local folder: the Data
group and the collapse control only. No link to the datasets, no
Migration group, no Language, Help or account: there is no server.

## Pages that change

- **Home** lists the datasets only.
- **Sites** (`#/sites`) is a page with the sites section that is on home
  today. The Sites entry opens it.
- **A dataset's page** loses its tabs; the sidebar's entries open the
  same four bodies at the same addresses. The page head (name, source
  line, share, extract again, delete) stays on Overview, Loads, Match
  rangers and Backup as today.
- **Overview's links into the browser** (one for each conservation area)
  stay.
- **The browser** loses its top band and its "Back to dataset" link. Its
  first view is named Summary. The address of that view does not change
  (`overview` in its hash and in `TABS`), so links made before still
  open.
- **The browser's "SMART database {version}"** line, which is in its band
  today, moves to the Summary view (my call).
- **`quirks.html`**, the browser's page of notes on SMART data, does not
  get the sidebar. It keeps a plain band of its own with a link back to
  the browser. `browse/build_quirks.py` takes fonts, tokens and the logo
  from the browser's band today and has to keep building once that band
  is gone (my call).
- **Addresses do not change**, in either document.

## Language

The app's sidebar text is in the five languages, as all its text is.

The browser's pages stay in English. Its sidebar, when the app serves
it, is in the reader's language: the browser loads the app's
`/static/i18n.js` and locale file for the sidebar's text only, and falls
back to the English text written in the document if that fails or it is
opened from a folder. The eight view names are sidebar text and are
translated. The Language control in the browser changes the sidebar's
language and the stored choice, the same choice the app reads.

A reader in another language is told the data pages are in English: the
Data group's heading carries the note the Browse links carry today
(`dataset.browseInEnglish`), in both documents, when the language is not
English. The machine-translation note is not shown in the browser, where
only the sidebar is translated (my call).

New and changed message keys go in all five locale files and follow
`docs/translation-glossary.md`.

## Approaches

1. **One sidebar everywhere** (chosen). The datasets and the sites are
   always one click away, and the browser reads as part of the dataset.
   The largest change, and two documents have to agree.
2. **Keep the top band; add Datasets and Sites links to it and a
   breadcrumb line to the browser.** Small, and it could ship in a day.
   The dataset's tabs and the browser's views stay two separate things.
3. **A sidebar only inside a dataset.** Fixes the seam between the
   dataset page and the browser, and leaves two styles of navigation in
   one app.

Within approach 1, two arrangements for a dataset:

- **A. The browser's views nested under a "Browse" entry.** Closest to
  today. Three levels deep, and "Rangers" twice.
- **B. The sidebar switches to the dataset, in two groups** (chosen).
  Two levels and no name twice. Sites is one click further away from
  inside a dataset.

How the two documents share the sidebar (my call, told to the user):
each draws it. Moving the browser into the app would make the switch
between Data and Migration instant, but it is a much larger piece of work
and ends the browser's use from a local folder.

## Not in this work

- Translating the browser's pages.
- Moving the browser into the app, or the app's pages into the browser.
- Any change to what a page shows, apart from where its navigation is.
- A list of recent datasets in the sidebar.

## Must not happen

- A page from which the list of datasets cannot be reached in one click.
- The browser failing to open from a local folder, or asking a server
  for anything there.
- An address that worked before and no longer opens its page.
- The sidebar naming a dataset, an owner or an address to someone who
  may not see it. It shows only what the page's own requests return.

## Left to the builder

- The markup and the styles, within the EarthRanger design system as the tokens
  in `web/static/er-tokens.css` carry it; the icons, from the Material Symbols set
  both documents already load.
- How the two documents keep the sidebar the same. One source for the
  entries and their order is preferred over two copies; a test that
  compares the two is the least that is acceptable.
- What Help does in the browser: the app's help is a drawer in the app's
  document. Opening the app at its help in a new tab is acceptable.
- Whether the app name sits beside the logo or under it, and what the
  folded sidebar shows for the dataset's name and the group headings.
- Focus order and keyboard use of the fold control and the account menu,
  to the standard the band's controls meet today.

## Tests

- Routes: every address that opens a page today still opens it; `#/sites`
  opens the sites page.
- The sidebar for each state: signed out; home; sites; a dataset on each
  of its four pages; a load; a dataset that is not ready (Data disabled);
  a user without access to a tab (that entry disabled); the current
  entry marked.
- The entries and their order are the same in the app and in the
  browser.
- The browser from a folder: only the Data group and the fold control;
  no request to a server.
- The browser served by the app: the Migration entries and Overview link
  to the app's addresses for that dataset; the sidebar text follows the
  stored language; a failed locale request leaves English.
- The fold state set in one document is read by the other.
- Every new message key is in the five locale files (the existing check).

By hand, before release, in light and dark and at phone width: home, a
dataset, a load, the browser, and the browser opened from a folder.

## Also to update

- The help pages that name the tabs, the breadcrumb or "Back to dataset"
  (`web/help/` in five languages). They have no screenshots today; one
  that is added must come from a conservation area with no real data.
- `docs/decisions.md`: the decision and the two rejected approaches.
