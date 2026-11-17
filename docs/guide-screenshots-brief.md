# Brief: SMART Desktop screenshots for "Get your inputs"

For the Claude session on the Windows PC that has SMART Desktop installed.
Delete this file when the screenshots have landed.

## What this is for

`https://padas.github.io/er-smart-able/` is a public getting-started guide
for moving a conservation area's SMART data into EarthRanger. Its page
"Get your inputs" (`web/guide/02-get-your-inputs.md`) tells the reader how
to get a file out of SMART Desktop. Readers have asked for more detail.

Two problems with that page today:

1. Its SMART steps were written without SMART Desktop to hand. They sit
   under a note, "These steps are not yet verified against SMART Desktop."
   Only the menu path File → Export Conservation Area and the backup's file
   name (`SMART_<date>.bak.zip`) come from a real source.
2. It has no pictures.

Your job is to walk the three procedures below in SMART Desktop, record
what the steps really are, and capture a screenshot of each step.

## The rule that matters most: the site is public

Nothing in a screenshot may identify a real conservation area or person.

- Use a conservation area with no real data: a sample or demo area, or a
  new empty one named something like "Example Conservation Area".
- If a real area is all there is, stop and ask Chris before capturing.
- Check every image for: ranger or employee names, the signed-in user's
  name, real area names, the Windows account name in a file path or a
  save dialog, other windows, the taskbar, notifications.
- Capture the SMART window or the dialog only, never the whole desktop.
- Save files somewhere with a neutral path, such as `C:\SMART-exports\`,
  so the save dialog shows no personal folder.

## What to walk through and capture

For each procedure: do it for real, to the point where the file exists.

**A. Conservation Area export**
1. SMART Desktop's sign-in screen, with the area chosen (which role is
   needed? the page says "administrator"; confirm).
2. The menu open at the export command (the page says
   File → Export Conservation Area; confirm the exact wording).
3. Every dialog that follows, with the choices a reader should make.
4. The finished file in File Explorer, showing its name and that it is a
   `.zip`.

**B. System backup**
1. Where the backup command is (the page does not know; find it).
2. Every dialog that follows.
3. The finished file in File Explorer. Confirm its name pattern
   (`SMART_<date>.bak.zip`?) and where SMART saves it by default.

**C. Zipping the install folder** (for someone who cannot run SMART)
1. Where SMART Desktop is installed by default on Windows.
2. That folder in File Explorer, and the right-click that zips it.
   Confirm which folder holds the database (the tool needs the folder that
   contains `data/`).

## Also record, in words

- The exact SMART Desktop version (Help → About). The tool is proven on
  7.5.x and only expected to work on 8.0–8.1.x, so the version matters.
- The exact text of every menu item, button and dialog title you used.
- Anything the current page gets wrong or leaves out.
- Roughly how long each procedure took and how big each file is.
- Whether SMART Desktop's own language can be switched, and how. The
  guide is to be translated into French, Spanish, Portuguese and Swahili
  later. Capture in English now; do not capture other languages yet.
- Keep the export and backup files you made. If they hold no real data,
  tell Chris: a file from a modern SMART version is a useful test input.

## How to capture

- PNG. One step per image. No arrows or annotations; the page's text does
  the pointing.
- The same window size for every SMART shot, about 1280 px wide, at 100%
  display scaling if the PC allows, in SMART's default theme.
- Crop dialogs to the dialog. Keep the mouse pointer out of the way,
  except where an open menu needs the highlighted item.
- Names: `smart-export-1-signin.png`, `smart-export-2-menu.png`,
  `smart-backup-1-menu.png`, `smart-installzip-1-folder.png`, and so on:
  procedure, step number, a word.

If you cannot drive the screen yourself, ask Chris to press
Win+Shift+S (or Alt+PrtScn for the active window) at each step and save
the files; you name, check and file them.

## What to hand back

Work on the branch `docs/guide-screenshots` of
`https://github.com/PADAS/er-smart-able` (it already has the build support
for images).

1. Put the images in `web/guide/img/`.
2. Edit `web/guide/02-get-your-inputs.md`: correct the steps to what you
   saw, and place each image under its step as
   `![what the picture shows](img/smart-export-2-menu.png)`. The words in
   the brackets are required (the build fails without them) and should say
   what a person who cannot see the picture needs to know.
3. Keep the "not yet verified" note only on anything you could not
   confirm. Remove it from what you did confirm.
4. Keep the page's voice: plain, second person, short numbered steps.
   Do not touch the EarthRanger half of the page, or any other page.
5. Check the build: `pip install markdown`, then
   `python scripts/build_pages.py` and open `_site/get-your-inputs.html`.
   `python -m pytest tests/test_pages_site.py` should pass; one test
   expects the note's exact sentence to be on the page, so if you remove
   the note entirely, say so and leave that test failing for the Mac
   session to update.
6. Commit, push the branch, and put your written notes (version, exact
   wording, corrections, anything uncertain) in the commit message or a
   pull request description. Do not merge.
