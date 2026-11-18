# Support view: named support staff can see every dataset and site, read-only

## Purpose

Support staff help people who are migrating a site. Today they can see a
dataset or an EarthRanger site only if its owner shares it with them, so a
person who is stuck must first learn to share. This change lets a short,
named list of support addresses see every dataset and site, and change none
of them.

## What was decided

- Support sees everything a reader sees, including the dataset browser
  (ranger names and photos), a load's plan, findings and reports, and the
  extraction log.
- The list of support addresses is a deploy variable, not something edited
  in the app.
- Each support view of someone else's data is written to the service log.
  Owners are not shown it in the app.

## Why it is a separate permission

"Can read" in this app is more than seeing. Anyone who can read a dataset
and a site can start a load, and a load writes to EarthRanger with the site
owner's token; anyone who can read a dataset can run, re-plan or delete its
loads. Adding support to `shared_with`, or widening `can_read`, would let
support write to any customer's site. So support view is a second, weaker
permission that only read routes accept.

## Who is support

- `SUPPORT_EMAILS` on the service: whole addresses separated by spaces,
  commas or semicolons, compared without regard to case. Unset or empty
  means nobody is support, which is the default everywhere, including
  locally.
- An entry that starts with `@` is ignored and logged once as a warning at
  startup: a whole domain is never support.
- A support address must still pass `ALLOWED_EMAILS` to sign in.
  `SUPPORT_EMAILS` grants nothing on its own.
- The deploy sets it from a repository variable of the same name. Only
  people who can deploy can change it.
- The role is worked out on every request from the variable, never stored
  in the session or in Firestore, so removing an address and deploying
  ends that person's support view at once.

`auth.py` gains `support_entries()` and `is_support(email)`. The user that
`current_user` returns gains `support: bool`, and `GET /api/me` returns it.

## What support can open

`store.py` gains `can_view(doc, user)`: true when `can_read` is, or when
the user is support. `_load` and `_load_site` in `app.py` keep `can_read`
as their default and take `view=True` to accept `can_view` instead. A route
that does not ask for it stays strict, so a route added later is closed to
support unless someone opens it on purpose.

Routes that pass `view=True`:

| Route | Notes |
| --- | --- |
| `GET /api/datasets` | with `?all=1` only; without it, support gets the same list as anyone |
| `GET /api/sites` | with `?all=1` only |
| `GET /api/datasets/{id}` | support also gets `log_tail`, which only the owner gets today |
| `GET /api/datasets/{id}/loads` | |
| `GET /api/loads/{id}` | |
| `GET /api/loads/{id}/files/{name}` | |
| `GET /d/{id}/` and `GET /d/{id}/{path}` | the dataset browser and its files |

`?all=1` from someone who is not support is ignored: they get their usual
list, not an error, so the parameter reveals nothing.

Every dataset, site and load in a response gains
`access`: `"owner"`, `"shared"` or `"support"`. `mine` stays as it is. A
site seen through support view (`access: "support"`) leaves out
`token_hint`.

Someone who is neither a reader nor support still gets 404, as today.

## What support cannot do

Nothing else changes. Every route that writes keeps its present check, so
through support view alone a person cannot upload, extract, share, unshare,
delete a dataset or its backup, register, edit, share or delete a site, or
create, run, re-plan or delete a load. A support person who owns a dataset,
or has one shared with them, keeps what an owner or a reader can do with
that one.

The load dialog asks for `GET /api/sites` without `all`, so it only ever
offers sites the person may load into.

No token is exposed: no response carries one today and none is added.

## The record

When a support user opens something through support view (`access` is
`"support"`), the service logs one line at INFO:

`support_view viewer=<email> kind=<dataset|load|browser|load_file|list> id=<id> owner=<owner email>`

It logs at most once per viewer, kind and id in ten minutes per instance,
because the dataset and load pages poll. The browser logs on its index
page, not on each data file or photo. The list logs `kind=list` with no id
or owner. The line never holds a token, a file's contents or a ranger's
name.

## In the app

- **Home page.** A support user sees an "All users" switch above the
  lists. Off (the default), the page is what it is today. On, both lists
  come from `?all=1`, and each row shows its owner, as rows shared with
  you do now. The choice is remembered in the browser. Nobody else sees
  the switch.
- **A dataset opened through support view** shows a line under its title:
  "Support view: read-only. Owned by <owner>." Its tabs all open. The
  buttons an owner or reader would have (Re-extract, Share, Delete, Delete
  the backup now, Load into EarthRanger) are not drawn.
- **A load opened through support view** shows the same line; Run,
  Plan again and Delete are not drawn.
- **A site in the all-users list** shows its name, address, owner and
  sharing, with no Edit, Share or Delete.

The buttons are hidden for clarity. The protection is the server's
refusal, which the tests check.

The new text goes in the app's messages in all five languages, machine
translated like the rest.

## Telling people

One sentence, in the help page on sharing and in the guide, in all five
languages: EarthRanger support staff can view datasets and sites to help
with a migration; they cannot change them or load data.

`web/DEPLOY.md` gains the variable, who it should name, and how to read the
record in Cloud Logging. "Data handling" there says who else can now read a
dataset.

## Tests

- `is_support`: listed address, case, an address not listed, an `@domain`
  entry ignored, unset.
- As a support user who neither owns nor shares a dataset, site and load:
  every read route in the table succeeds and reports `access: "support"`;
  `log_tail` is present; `token_hint` is absent.
- As the same user, **every** write route is refused. The test builds its
  list from the app's own routes: each route whose method is not `GET` must
  be in the test's table with the refusal it expects, so a new write route
  fails the test until someone decides what support gets.
- `?all=1` as an ordinary user returns only their own and shared items.
- A user who is neither reader nor support still gets 404 on each read
  route.
- A support user who owns a dataset can still do everything an owner can.
- The record: one line on first view, none on a second view inside ten
  minutes, none for an owner viewing their own dataset.
- Page builders (Node): the switch is drawn only for support; a dataset,
  load and site with `access: "support"` draw no action buttons and draw
  the support line; the stand-in language test covers the new states.

## Not in this change

- Showing owners that support looked.
- An admin screen for the support list.
- Support acting on someone's behalf (re-extracting, re-planning). If that
  is wanted later it is a separate, logged permission.
- Any reader of a dataset can delete its loads today. That is unchanged
  here and worth its own look.
