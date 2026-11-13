# UI refresh: a dataset-centred app on the EarthRanger design system

Date: 2026-11-13. Status: approved in conversation; implementation plan to follow.

## Goal

Restructure the hosted app around the dataset, and give it and the dataset
viewer one look, the EarthRanger design system's. The API does not change.

Today the app is three stacked panels (upload, sites, datasets) on one page,
with the load page swapped in by script, styled by a hand-written stylesheet
with its own colours. The viewer at `/d/<id>/` is a separate page that already
follows the design system. Moving between the two feels like changing
products, the dataset table overflows, and loads and rangers have no home of
their own.

After this work: a home page that is the dataset list; a page per dataset
with Overview, Loads and Rangers tabs; the load page in the same frame; sites
under the account menu; one header on both pages; the design system's tokens,
type, status colours and dark mode on both.

## Decisions taken in brainstorming

1. **Dataset-centred navigation**, not a sectioned admin app and not a tidied
   single page: the dataset is the unit the operator thinks in.
2. **The header says EarthRanger.** The 2026 EarthRanger-by-Ai2 lockup with
   the product name **SMART migration**; "smart-able" survives only in the
   page title and the version string.
3. **Roboto only, self-hosted.** PP Telegraf is licensed and its files live in
   a Drive folder this work cannot fetch; headings use Roboto Medium at the
   design system's `heading-ui` sizes, which it allows for product UI. Adding
   PP Telegraf later is a font file and one `@font-face`.
4. **Keep the vanilla app**: the same FastAPI service, API, single stylesheet
   and single script, with a small router and one render function per page.
   No framework, no build step.
5. **Dark mode** is included, following the design system's first-class dark
   values, with a theme switch in the account menu.

## Design reference

`/Users/chrisdo/allenai/design/earthranger/DESIGN.md` and the generated
`tokens.css` beside it. The rules this work follows from it:

- Semantic tokens only (`UI/Text/Primary Text`, `UI/CTA Primary`, ...), never
  a primitive hex in a stylesheet.
- `UI/CTA Primary` green for calls to action, links and active states; teal
  for navigation, headers, labels and tabs; status colours only for status.
- Dark mode inverts: deep teal surfaces, text flips, status colours move to
  the lighter steps. Both pages honour the OS preference and `data-theme`.
- Fonts self-hosted, subset, regular and bold only, `font-display: optional`,
  with the native fallback stack. No third-party font CDN.
- Material Design icons, outlined, coloured with `UI/Icons`. No emoji.
- `UI/Text/Primary Text Reversed` on any teal or green fill.

## 1. The shell

### Header

A band in `UI/CTA Secondary` (teal T100 in light mode; the design system's
dark value in dark mode), 48px tall on desktop. Left to right:

- The white horizontal **short** EarthRanger-by-Ai2 lockup
  (`EarthRanger-Logo-2026_Ai2-white-H-short.svg`, the variant for rendered
  heights under 56px), a link to the home page.
- "SMART migration" in `heading-ui-md` scaled to the band, then the version
  string in `body-xs`.
- At the right: **Help**, which opens the existing help drawer, and the
  **account menu**, whose trigger is the signed-in email. The menu holds
  *EarthRanger sites*, *Theme* (System, Light, Dark), *Sign out*, and the
  version.

The sign-in page shows the band without Help or the account menu.

### Routes

A hash router over these routes, each a history entry, so Back and Forward
move between them and any page can be reloaded or shared:

| Route | Page |
|---|---|
| `#/` | Datasets, the home page |
| `#/datasets/<id>` | A dataset, Overview tab |
| `#/datasets/<id>/loads` and `#/datasets/<id>/rangers` | Its other tabs |
| `#/datasets/<id>/loads/<load>` | A load page |
| `#/sites` | Sites |

The old `#load/<id>` form redirects to `#/datasets/<dataset>/loads/<id>`
(the load's dataset comes from the load). An unknown route shows the home
page. The history-entry rules from PR 30 carry over: a deleted load replaces
its entry, a load that turns out to be gone pops the entry it pushed, a
reload keeps where a page was opened from.

Each page is a render function that owns one container; the polling timers,
open-state preservation and scroll preservation move with their pages and
are cleared when a page is left.

### Page frame

The page sits on `UI/Background/Secondary Background`; panels sit on
`Elevated Component` with a `Divider Lines` border and 10px radius; banded
sub-surfaces (table headers) on `Elevated Component 0`. Content is at most
1100px wide with 16px gutters and works at phone width with no horizontal
page scroll (lists scroll inside their panel). Dataset and load pages carry a
breadcrumb under the header: "Datasets › R5 Lawin › 051600 → smart-migrations".

### Controls

- **Primary** button: `CTA Primary` fill, reversed text; one per view.
- **Secondary** button: outline in `Field Outline`, teal text.
- **Destructive**: `Status/Error` text, outline; confirms before acting.
- **Ghost**: text only, for in-row actions and the help "?".
- Inputs: `Field Outline` border, `Form Labels` labels above, 8px radius.
- Pills: text plus colour, never colour alone (see status colours).
- Focus: a 2px ring in `CTA Primary` on every control.
- Dialogs: the existing modal, with the frame restyled and focus trapped.

### Empty states

Every list has one sentence and the action that fills it: "No datasets yet.
Upload a backup or export to begin." "No sites yet. Add the EarthRanger site
you will load into." "No loads yet." with the Load button. "No rangers listed
yet: a load that reaches patrol setup fills this; the viewer's Rangers tab
lists the people in the dataset meanwhile."

## 2. The dataset list

The home page. Top right: **Upload a backup or export**, a primary button
that opens a dialog with the name and file fields and the upload progress bar
(the current upload flow, moved into a dialog); on completion the dialog
closes and the new dataset appears at the top of the list, extracting.

Below, one card per dataset, newest first:

- Line 1: the name (the card's link), the source file name and size.
- Line 2: the status pill; the conservation areas by name, SMART id in small
  text; a short error if extraction failed.
- Right: patrols and waypoints counts, the owner ("you" or the email), and a
  small "shared" marker when shared with anyone.

A card is one click to its dataset page. Share, re-extract and delete are on
the dataset page, not the card. The list polls every five seconds while any
dataset is queued or running, as now, re-rendering cards in place.

## 3. The dataset page

Breadcrumb, then a **title block**: the name; beneath it the source file and
size, the upload date, the owner and the shared-with list. Actions at the
right: **Share** (owner), **Re-extract** (owner; the current conditions),
**Delete** (owner; confirms with "and all its extracted data, bundles and
load records; nothing in EarthRanger is removed"). While an extraction is
queued or running the actions are disabled except the log.

Then **tabs**, teal text with the active tab underlined in `CTA Primary`:

**Overview.** The extraction status with its started/finished times and a
collapsible log tail (open while running). Then one row per conservation
area: name, SMART id, SMART version, patrol and waypoint counts, and at the
right **Browse**, which opens the viewer for that area in the same tab, and
**Load into EarthRanger** when the area has a migration bundle (the current
load dialog, with the area preselected). An area without a bundle shows
"re-extract to enable loading" as now.

**Loads.** One row per load, most recent first: conservation area → site,
the status pill, the progress text ("554 of 2,761 patrols") when there is
any, started date, started by. Each row opens the load page. **Load into
EarthRanger** at the top right when any area has a bundle. Polls while a load
is held, as the list does today.

**Rangers.** The rangers list as the load page shows it today, with the same
columns, CSV download and help link, taken from the most recent load that
reached patrol setup (`rangers`, `rangers_total`). A line above says which
load it came from and when. The empty state points at the viewer's Rangers
tab.

A dataset still extracting opens on Overview with Loads and Rangers
disabled.

## 4. The load page

Breadcrumb, then a **title block**: "051600 → smart-migrations" as the
heading with the status pill beside it (and the "?" to the statuses help);
beneath it the site host, event category, language, date window if set,
configurable model if set, who started it and when. Actions at the right,
as the page offers them today: **Confirm and load** / **Continue**
(primary), **Plan again**, **Delete this load**; the "stops at N blocking"
and "the job stopped without reporting" notes sit under the actions.

Body, in order: the stage table with its heartbeat line; findings, blocking
first, with their copy buttons and help links; the plan, as collapsible
groups; the Rangers section; the progress bar and import summary; the log,
open while the load is active. All behaviour from PRs 19 to 33 is kept:
four-second polling while active, open-state and scroll preservation, the
memo on the rangers table, the per-execution wording on the import row.

## 5. Sites

`#/sites`, reached from the account menu. **Add a site** at the top right
opens a dialog with name, host and token; the token check runs on submit and
its error shows in the dialog. Below, one row per site: name and host, the
token hint and the user it works as, owner, shared with, and for the owner
**Share** and **Remove**. Remove confirms with: "Loads that reference this
site stay readable but cannot be continued; register the site again to load
into it." The load dialog's site picker ends with "Add a site…", which opens
the same dialog and selects the new site on return.

## 6. Sign-in

The band without Help or the account menu. One centred panel: the dark
lockup, "SMART migration" in `heading-ui-lg`, one sentence ("Upload a SMART
conservation-area backup, browse it, and load it into an EarthRanger site."),
the allowed-domain hint, and **Sign in with Google** as the primary button.
Errors under the button.

## 7. The viewer's header

The viewer stays its own single file, served by the app at `/d/<id>/` and
standalone from a local extraction. Its header becomes the same band: the
lockup, "SMART migration", the dataset's name, the conservation-area
selector, with the tabs on the band's second line as now. When the page's
own path is `/d/<id>/`, a **Back to dataset** link at the right returns to
`/#/datasets/<id>`; standalone, the link is absent. The acorn mark gives way
to the lockup; the quirks page, built from the viewer, follows.

Nothing inside the viewer's tabs changes.

## 8. Theming and type

### Tokens

`tokens.css` from the design repository is copied unchanged to
`web/static/er-tokens.css`, with the source path, the design system version
and the copy date in a comment at the top. The app's stylesheet references
only its variables; a test asserts the stylesheet contains no raw colour
value (`#hex`, `rgb(`, named colours) outside the tokens file. The viewer
inlines the same semantic values for its own tokens, with a comment naming
`er-tokens.css` as the source, so both are updated together.

### Status colours

| Status | Token |
|---|---|
| running, continuing, extracting | `Status/Running` on `Status Bg/Draft Bg` |
| done, ready, success | `Status/Success` on `Status Bg/Synced Bg` |
| needs attention, warning findings | `Status/Warning` on `Status Bg/Warning Bg` |
| failed, blocking findings, errors | `Status/Error-Destructive` on `Status Bg/Error Bg` |
| planned | `Status/Ready` |
| queued, planning, uploading, pending | `Status/Disabled` on `Status Bg/Pending Sync Bg` |
| interrupted | `Status/Error-Destructive` text, pending background |

Findings keep their left border, coloured from the same tokens by severity.

### Light and dark

Both pages follow `prefers-color-scheme` by default and honour
`data-theme="light"` or `"dark"` on the root, as `er-tokens.css` does. The
account menu's Theme setting writes `data-theme` and remembers the choice in
`localStorage`; the viewer reads the same key so a choice carries across.

### Type

Roboto in three weights, regular (400), medium (500) and bold (700), Latin
subset, self-hosted under `web/static/fonts/` with `font-display: optional`
and the fallback stack `Roboto, system-ui, "Helvetica Neue", Arial,
sans-serif`. The design system's rule is "regular and bold only", meant to
stop the full weight range being shipped; medium is added because the
`heading-ui` styles are Roboto Medium and a synthesised weight would not
match. Three subset files are about 60 KB together. Body at `body-sm`
(14px/21px) for the app's density,
`body-md` on the sign-in page; buttons in `button-xs`. Identifiers in the
monospace fallback stack (`"Roboto Mono", ui-monospace, Menlo, monospace`)
without shipping a mono font. The viewer, served by the app, loads the same
font files from `/static/fonts/`; standalone it uses the fallback stack.

### Icons

Material Symbols Outlined, as now, coloured with `UI/Icons` unless on a
filled control.

## Error handling

The API is unchanged, so the failure modes are the page's:

| Situation | Behaviour |
|---|---|
| A route names a dataset or load the user cannot read | the page shows "Not found or not shared with you" with a link home; the entry is replaced so Back does not return to it |
| A fetch fails while polling | the page keeps its last render and retries on the next tick; a small "could not refresh" note appears after two failures |
| The upload dialog is closed mid-upload | the upload continues; the dataset list shows it |
| The tokens file fails to load | the stylesheet's fallbacks are the light values, declared once on `:root` before the tokens file |
| Fonts fail to load | the fallback stack renders; `font-display: optional` means no layout shift |

## Testing

- The Python suite is unchanged in scope: the API does not change.
- Node rendering tests with a minimal DOM shim (the approach used to check
  the viewer's Rangers join): the router resolves each route and redirects
  the old load form; each page's render function produces the expected
  headings, rows and actions from fixture data, including the empty states;
  the status pill maps every status to a token class.
- A stylesheet test: no raw colour outside `er-tokens.css`; every font
  reference carries the fallback stack.
- `node --check` on both scripts, as now.
- A manual pass on the deployed app: desktop and phone width, light and
  dark, sign-in, upload, a dataset's three tabs, a load page while a load
  runs, sites, the viewer's Back to dataset link, and the viewer standalone.

## Out of scope

- Any API change.
- Changes inside the viewer's tabs.
- PP Telegraf, until its files and licence are in the repository.
- A loads list across datasets.
