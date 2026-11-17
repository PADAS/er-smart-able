# Language support in the docs and the app: design

## Intent

The people who use smart-able are no longer only EarthRanger Support. People
at the sites will run migrations themselves, and SMART users, managers and
deployment technicians will follow the SMART steps on the getting-started
site. Many of them work in French, Spanish, Portuguese or Swahili. Today
every word in the docs and the app is English.

This work makes the getting-started site and the hosted app readable in
five languages, so a site person can follow the steps and act on what the
app tells them without reading English.

Decided with Chris (the owner): the five languages; that site people will
use the app; that translations are written by Claude and published without
review so the app can be used at once, with fluent people reviewing and
correcting them later; that a visible "machine translated" note is shown;
and the design below, as presented in conversation. Details not discussed
are the author's call and are marked.

## Goals

- The getting-started site (three guide pages, five help pages) in English,
  French, Spanish, Portuguese and Swahili.
- The app's screens, its error messages, its findings and its help drawer
  in the same five languages.
- A reader chooses a language once; before that, the browser's language
  decides.
- A fluent reviewer can correct any translation by editing a plain file in
  a pull request, and can mark a language as reviewed in one line.
- English is the source. Anything not translated shows in English; nothing
  shows a blank or a key name.

## Non-goals

- The dataset browser (`browse/index.html`). It stays English; it is a
  later project.
- The live log of an extraction or a load. It stays English.
- The quirks reference (`docs/smart-data-quirks.md`). It stays English.
- Translated screenshots. The pictures show SMART in English.
- Who at a site may sign in to the hosted app, and how. That is a separate
  decision; this work changes no access rule.
- Languages beyond the five, and right-to-left layout.
- A language saved to a user's account. The choice lives in the browser.
- A change to `er-smart-sync`, which words some findings.

## Anti-goals

- A translation that changes what a step tells the reader to do. File
  names, menu paths, button names, hosts and code are carried over, not
  reworded.
- Two words for one thing. A term EarthRanger or SMART already translates
  uses their translation.
- A translated page or message that is missing something its English
  source has: a step, a tab, a picture, a warning, a placeholder.
- Any change to what is stored. Load documents, findings and API responses
  keep their English text; language is applied when text is shown.
- The existing handling rules weakened: no translated file may name a real
  conservation area's rangers, a customer's EarthRanger host (only
  `example.pamdas.org`), or a token.

## Shared rules

### Languages

| Code | Name shown in the switcher |
|---|---|
| `en` | English |
| `fr` | Français |
| `es` | Español |
| `pt` | Português |
| `sw` | Kiswahili |

One registry file, `web/static/locales/languages.json`, lists them in this
order, each with `code`, `name` and `reviewed` (true or false). The site
build and the app both read it. `en` is `reviewed: true`; the other four
start `false`.

### The "machine translated" note

While a language is `reviewed: false`, every page of the site and every
screen of the app in that language shows a short note, in that language:
the translation was made by machine and has not yet been reviewed by a
fluent speaker, and the English version is the reference. On the site the
note links to the same page in English. When a reviewer sets
`reviewed: true`, the note goes. (Where the note sits on the page is the
builder's; it must be visible without opening a menu.)

### Terms

A glossary, `docs/translation-glossary.md`, has one row per term and one
column per language, with where each translation came from. Sources, in
order:

1. **EarthRanger's web app**, for EarthRanger's words (patrol, patrol type,
   event, event type, subject, subject group, and so on): the `es`, `fr`,
   `pt` and `sw` folders of `das-web-react/public/locales/`.
2. **SMART Desktop 7.5.6's translation files**, for SMART's interface words
   and menu names (Conservation Area, Export Conservation Area, Backup
   System, Login, Browse, and so on). Only interface text is read from the
   SMART install; no data from it is copied.
3. Where neither has the term, the author's translation, marked in the
   glossary as "not from a product", for the reviewer's attention.

The glossary is written first, and the translations follow it. It is the
first thing a reviewer reads.

### What is never translated

File names and patterns (`SMART_<date>.bak.zip`), hosts, code, status
values as the API returns them (`needs_attention`), permission names as
EarthRanger's admin shows them in English, and names that come from a
site's data (teams, stations, patrol ids).

### Who writes and who corrects

Claude writes all four translations. They are published unreviewed, with
the note. A reviewer corrects a file in a pull request and sets `reviewed`
when a language has been read through. (Chris's decision.)

## Part 1: the docs site

### Sources

- English sources stay where they are: `web/guide/*.md`, `web/help/*.md`.
- A translation sits in a folder named for its language, with the same
  file name: `web/guide/fr/02-get-your-inputs.md`,
  `web/help/sw/04-statuses.md`.
- Pictures stay in `web/guide/img/`, one set for all languages. A
  translated page refers to them as `../img/name.png`, with alt text in its
  own language.
- The words of the page shell (the header's subtitle, the two navigation
  group names, "Previous", "Next", the footer, the note) are in
  `web/site/locales/<lang>.json`.

### Output

- English keeps its addresses: `index.html`, `get-your-inputs.html`, and so
  on. No existing link breaks.
- Each other language is a folder with the same page names:
  `fr/index.html`, `fr/get-your-inputs.html`.
- Stylesheets, fonts, lockups and pictures are published once and shared.
  Every link stays relative, so the site still works under any path and
  from disk.
- Each page sets `<html lang>` and lists the other languages' versions of
  itself with `<link rel="alternate" hreflang>`.

### A page with no translation

It is built from the English source, in that language's folder and shell,
with a line at the top in that language saying the page is not yet
translated, and its body marked `lang="en"`. So every page exists in every
language, and the navigation never leads out of the reader's language by
surprise.

### Choosing a language

- A switcher in the header lists the five languages by their own names and
  links to the same page in each. It is plain links; it works without a
  script.
- Choosing a language remembers it in that browser.
- On an English page, a reader with a remembered choice of another language
  is taken to that language's version of the page. A reader with no
  remembered choice is taken to the first of their browser's languages that
  the site has; if none, they stay on English. Choosing "English" in the
  switcher is itself a remembered choice, so it sticks.
- If the browser's storage is unavailable, the page still renders and the
  switcher still works; only the remembering is lost.

### The SMART steps

A translated step names each SMART menu and button as SMART shows it in
that language, followed by the English name in brackets, because the
picture beside the step shows English. Where SMART's translation files have
no entry for a name, the step gives the English name only.

### The build refuses

In addition to today's checks, the build fails, naming the file, when a
translated page:

- has no English page of the same name;
- links to a page that does not exist;
- has a different number of tabs, pictures, numbered steps or set-apart
  notes than its English page;
- lacks a file name, host or code span that its English page has.

It also fails when a language in the registry has no shell words file, or a
shell words file lacks a key the English one has.

### Publishing

The Pages workflow also runs when `web/site/**` or the registry changes.
Nothing else about publishing changes.

## Part 2: the app's screens and messages

### Message files

- `web/static/locales/<lang>.json`, one per language, in the shape
  EarthRanger's web app uses: nested keys, `{{name}}` placeholders, and
  `_one` / `_other` suffixes for plurals. (Author's call: the people who
  review EarthRanger's translations know this shape.)
- A message holds text only, never HTML. Where a sentence has a bold word
  or a link inside it, the code builds the markup and the message supplies
  the parts. Every translated string is escaped where it is put into the
  page, exactly as data is today.

### In the code

- A small function, `t(key, values)`, replaces each English phrase in
  `web/static/pages.js`, `web/static/app.js` and
  `web/templates/index.html`. No new library.
- A key missing in the chosen language shows the English message. A key
  missing in English is a failed test, not something a user can see.
- Plurals use the browser's plural rules for the language. Numbers, dates
  and durations are formatted for the language; the fixed `en-US`
  formatting goes.
- `pages.js` stays a set of pure builders that Node can test. How it is
  given its messages is the builder's.

### Choosing a language

The same rule as the site: the browser's language on a first visit, a
switcher in the header, the choice remembered in that browser, and the
page still working when storage is unavailable. The app and the site are
on different addresses, so each remembers its own choice. The sign-in page
is translated too, since it is the first thing a site person sees.

### Server messages

- Every error the server returns keeps its English `detail` and gains a
  `code` (a stable name such as `dataset_not_found`) and, where the message
  carries a name or a number, `values`.
- The app shows the message for the code in the reader's language, and the
  server's English `detail` when it has no message for that code. A client
  that reads only `detail` sees no change.

### Help drawer

`/api/help` takes the language and returns the translated help pages from
Part 1, page by page, with the English page where a translation is
missing. The quirks reference is served in English.

### Status words

A status is shown with a translated label. The value in the API, in the
help pages' tables and in the log stays as it is, so a reader can match
what they see to what Support asks them about.

## Part 3: findings

A finding is stored on the load in English, with a `code`. Some are worded
by this repository (`web/findings.py`), some by `er-smart-sync`.

- The message files gain a title and a fix for each known finding code.
- The findings this repository words also store the names and counts their
  sentences use, as a new `params` field beside the English text.
- The app shows a finding translated when it has a message for the code
  and the finding carries every placeholder the message needs. Otherwise
  it shows the stored English: an unknown code, a load made before this
  change, or a finding from `er-smart-sync` whose wording carries a value
  the app cannot recover.
- The copyable values (a team name, a permission name) and the detail
  lines stay exactly as stored.
- A list of the finding codes that still show in English is kept in the
  glossary file, so the gap is known and not discovered by a site person.

## Order of work

Each part is planned, built and merged on its own.

1. **The docs site.** Glossary, registry, build changes, the eight pages in
   four languages.
2. **App screens and server messages**, with the help drawer.
3. **Findings.**

Part 2 carries the most risk. `web/static/app.js` has no browser tests, and
every screen is touched. Part 2 is not done until each screen has been
viewed in a browser in each language.

## Tests

- **Registry and files:** every language in the registry has a shell words
  file and an app message file; every key in the English file exists in
  each other file, with the same placeholders and a plural form wherever
  English has one.
- **Keys in code:** every key the code asks for exists in the English file.
- **Site build:** each language's folder has every page; a page with no
  translation is built from English with its line and `lang="en"`; the
  switcher on each page links to the same page in each language; the note
  shows for an unreviewed language and not for a reviewed one; each of the
  build's new refusals.
- **Site content:** each translated page has the same tabs, pictures,
  steps, notes and code spans as its English page; no page in any language
  names a host other than `example.pamdas.org`.
- **App:** `t` falls back to English for a missing key; plurals and numbers
  follow the language; a server error with a known code shows the
  translated message and one with an unknown code shows `detail`; a finding
  with a known code and its params shows translated, and one without shows
  the stored English; no message is put into the page unescaped.
- **Unchanged:** the app's existing Python and Node tests pass. Where a
  test asserts English words on a screen, it keeps asserting them for
  English.

## Risks

- **Unreviewed translations of steps that export ranger data and write to
  a live EarthRanger site.** Accepted by Chris so the app can be used at
  once. Reduced by the glossary, by carrying names and code over unchanged,
  by the structural checks, and by the visible note. Swahili is the
  language the author is least sure of.
- **SMART's menu names in each language.** They are read from the 7.5.6
  translation files, not seen on screen in each language. A later SMART
  version may word them differently.
- **Text that stays English inside a translated screen:** the log, the
  dataset browser, the quirks reference, and some findings. Each is listed
  above so it is a known limit.

## Left to the builder

- The markup and style of the switcher and the note.
- The key names in the message files.
- How `pages.js` receives its messages, and how the app loads them before
  its first render.
- The exact wording of every translation, within the glossary.
