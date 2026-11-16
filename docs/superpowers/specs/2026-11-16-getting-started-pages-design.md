# Getting-started site on GitHub Pages: design

## Intent

Support people at EarthRanger will be asked to move a site's SMART data into
EarthRanger with the hosted app. Nobody has done one yet. The app's help
drawer explains each step once someone is signed in; nothing explains what
comes before and around it. This site is where a support person starts: it
tells them what the tool does, what to collect, and how to do a first
migration, then hands over to the detailed help.

Decided with Chris (the owner): the reader, the page list, the build
approach, text only for the first version, and the app's address.
Everything else here is the author's call and is marked as such.

## Goals

- A public site at `https://padas.github.io/er-smart-able/`.
- Three new pages, in this order:
  1. **Before you start**: what the tool migrates and what it does not; who
     can sign in; the app's address,
     `https://smart-able-977100970772.us-central1.run.app/`.
  2. **Get your inputs**: how to get a SMART system backup or a
     Conservation Area export out of SMART, and what EarthRanger API token
     the target site needs (which user, which permissions).
  3. **Your first migration**: sign in, upload, wait for extraction,
     browse, register a site, make a plan, read it, confirm it, check the
     result. Each step names what is on screen and links to the reference
     page that covers it in depth.
- A **Reference** section: the five in-app help pages (`web/help/*.md`),
  from the same files the app serves, unchanged.
- The site looks like the app: the `--er-ui-*` tokens, self-hosted Roboto,
  the EarthRanger lockup, light and dark themes following the system.
- It is readable on a phone with no sideways page scroll.
- It publishes itself on every merge to `main` that changes its sources.

## Non-goals

- The command line, deployment, and the engineering notes in `docs/`. The
  site links to the repository for those.
- Screenshots. The first version is text only. The site is public, so
  screenshots wait for a dataset the owner chooses as safe to show.
- Search, versioned docs, translations.
- The quirks reference (`docs/smart-data-quirks.md`), which the app's help
  drawer includes. It is long and for a different question; the site links
  to it on GitHub. (Author's call.)

## Anti-goals

- Two copies of the help text. The Reference pages must come from
  `web/help/*.md`; nothing is pasted into the guide.
- Anything on the public site that names a real conservation area's
  rangers, a customer's EarthRanger host, or a token.
- A change to what the app serves. The app's help drawer and `/api/help`
  behave exactly as before.

## Approaches

1. **A build script in this repository, published by GitHub Actions.**
   Chosen. One set of words for the app and the site, the app's own look,
   no new dependency. No search, which eight pages do not need.
2. **Jekyll, built by GitHub.** Least setup, but a generic look, and the
   in-app help would be copied or `web/help/` restructured to suit Jekyll.
3. **MkDocs Material.** Best if the site grew large; adds a dependency and
   a second look to maintain.

Chris picked the first: readers move between the site and the app's help
drawer, and one set of words in one style matters more than search.

## Design

### Sources

- `web/guide/01-before-you-start.md`, `02-get-your-inputs.md`,
  `03-your-first-migration.md`: new. Same conventions as `web/help/`: the
  first `#` heading is the page title; filename order is page order.
- `web/help/*.md`: unchanged.

### Build

`scripts/build_pages.py [--out _site]` writes a static site:

- `index.html` is the first guide page. Each other source file becomes
  `<slug>.html`, where the slug is the filename without its number prefix.
- Markdown is rendered with the renderer the app uses
  (`web/help_pages.py` and `browse/build_quirks.py`'s `convert`), so a
  page reads the same in both places.
- Links are rewritten for a multi-page site, which differs from the
  drawer's single page:
  - a relative link to another guide or help file becomes that page's
    `.html`, keeping any `#anchor`;
  - a link to any other file in the repository becomes its GitHub URL;
  - an in-page `#anchor` stays;
  - the help pages refer to each other by title in italics today (for
    example *Sites and tokens*), not by link; they stay as they are.
- Every page has the same shell: a header band with the lockup and
  "SMART migration · Getting started", a left navigation with two groups
  ("Get started", "Reference") marking the current page, the content, and
  previous/next links at the foot. Under 700px the navigation collapses
  to a list above the content. (Layout details are the builder's.)
- Assets are copied from `web/static/`: `er-tokens.css`, the Roboto files
  and `fonts/roboto.css`, the lockups. One new stylesheet for the site's
  layout lives beside the script's template; it uses only `--er-ui-*`
  tokens. Nothing loads from a CDN.
- The theme follows the system (`prefers-color-scheme`), set by an inline
  script in the head as `web/templates/index.html` does. No theme switch.
- All internal links are relative, so the site works under
  `/er-smart-able/` and when `_site/index.html` is opened from disk.
- The build fails, with the file and link named, on a relative link whose
  target does not exist.

### Publish

`.github/workflows/pages.yml`: on a push to `main` that touches
`web/guide/**`, `web/help/**`, `scripts/build_pages.py`, the site's
template or stylesheet, `web/static/**`, or the workflow itself, and by
hand (`workflow_dispatch`). It installs the Markdown dependency, runs the
build, and deploys `_site/` with `actions/upload-pages-artifact` and
`actions/deploy-pages`. Permissions: `pages: write`, `id-token: write`,
`contents: read`.

One manual step, once, by a repository admin: Settings → Pages → Source:
GitHub Actions. The README and `web/DEPLOY.md` say so.

`_site/` is git-ignored.

### Content

The three guide pages are written from what the repository already
establishes; nothing is invented:

- **What migrates**: from `web/help/03-loading.md` and the README's
  "What you get": the data model as event types, patrol types and fields,
  rangers and the roster, patrols with their tracks, observations and
  attachments. What does not: what the loading help says is skipped or
  left to a person, plus what the README, `RUNBOOK.md` and `docs/` establish.
  In particular the guide says that Profiles data can be browsed but is
  not loaded. A public "before you start" page that stays silent reads as
  "it migrates", so the page names the gaps it can source. (Author's
  call.)
- **Supported SMART versions and inputs**: from the README (SMART Desktop
  7.5.x and 8.0–8.1.x; a system backup zip, a zipped install folder, or a
  Conservation Area export from File → Export Conservation Area). The
  guide says to upload a `.zip` only. A system backup is named
  `SMART_<date>.bak.zip` and is a zip. The upload form also accepts a bare
  `.bak`, but the extraction has no handling for one, so the guide does
  not offer it. (Author's call, from reading the code; whether the form
  should stop accepting `.bak` is a separate fix, outside this work.)
- **SMART 8.x**: the README lists 8.0–8.1.x, and `RUNBOOK.md` says 8.x is
  not yet tested against a real 8.x backup. The guide says both: 7.5.x is
  proven, 8.0–8.1.x is expected to work and not yet proven. (Author's
  call.)
- **The token**: from `web/help/02-sites.md` (which user, the permissions,
  host only without `https://`).
- **Sign-in**: "Sign in with your EarthRanger Google account. If you see
  'This email is not allowed', ask the EarthRanger engineering team to add
  your address." The contact wording is the author's call; Chris did not
  name a person or channel.
- Style: plain, second person, short steps; the same voice as `web/help/`.

Steps for getting a backup out of SMART beyond what the README states are
written as far as the repository supports, and carry a visible note on
the page: "These steps are not yet verified against SMART Desktop."
(Chris's decision.) The note is one reusable callout style, removed when
he has checked the steps.

The repository does not say where an EarthRanger API token is created.
The page states what the token must be (from `web/help/02-sites.md`) and
tells the reader to ask the target site's EarthRanger administrator for
one; it gives no click path. (Author's call: Chris was asked and did not
supply the steps. They are added when he does.)

### Tests

- The build writes one page per source file and `index.html`; each page
  has its title, the navigation with the current page marked, and
  previous/next links.
- A link between two source files resolves to the other page; a link to a
  repository file resolves to GitHub; a broken relative link fails the
  build.
- The Reference pages' body HTML equals what `help_pages` renders for the
  app, apart from link rewriting.
- No page references a CDN or Google Fonts, and every stylesheet colour
  comes from a `--er-ui-*` token.
- The app's help tests still pass unchanged.

## Left to the builder

- The template's markup and the site stylesheet.
- How the script shares code with `web/help_pages.py` (import it, or lift
  a small function), provided the app's behaviour does not change.
- The exact wording of the three guide pages, within the content above.
