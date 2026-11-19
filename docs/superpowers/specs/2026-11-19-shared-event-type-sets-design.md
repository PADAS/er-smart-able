# Several conservation areas on one site

Ticket: GUNDI-5946. Companion: GUNDI-5949 (keeping edits made on the site),
which changes the same push code and is not part of this spec.

## Purpose

A country's SMART deployment is many conservation areas with one data
model per region. LAWIN has about 168 areas and 18 regional species lists,
and all of them go to one EarthRanger site. Loading area after area into
one site goes wrong today in one of two ways, depending on whether the
load uses a configurable model.

Measured on two areas of one region (both carry a configurable model with
the same name and the same content):

| Load | What the two areas write | Result |
| --- | --- | --- |
| Without a configurable model | The same 24 choice lists with the same options; the same event types, bar one | Shared. The second load moves every event type into its own event category. Two areas whose lists differ would deactivate each other's options (from the code; not measured, for want of a second region's data) |
| With a configurable model | 18 event types and 22 choice lists each, equal in content, under different names | Nothing is shared. Each area's copy of the model has its own uuid, and the uuid is part of every event type value and choice list name |

At 168 areas the second row is about 3,000 event types and 3,700 choice
lists on one site, and no query spans two areas.

## What was decided

- Areas that use a configurable model of the same name share one set of
  event types and choice lists. A region with its own model gets its own
  set, and so its own species list.
- A load adds to a shared set. It does not take away what another area
  put there.
- A site already loaded keeps the event types it has. Nothing is renamed
  or migrated.

## Terms

**Set**: the event types and choice lists that one data model (or one
configurable model) becomes on a site. Every value in a set starts with
the set's **prefix**.

**Set name**: the text that identifies a set. Two loads with the same set
name on one site write the same set.

## The set name and the prefix

| Load | Set name | Prefix |
| --- | --- | --- |
| No configurable model | none | `smart-ca-import`, as today: one set for the site |
| Configurable model | the model's name as SMART stores it, unless the operator changes it | `smart-ca-import_<key>` |

`<key>` is a version 5 UUID of the normalised set name under a fixed
namespace that smart-able owns. Normalising is: Unicode NFKC, case folded,
runs of white space made one space, ends trimmed. The key takes the place
the model's own uuid has today, so the form of every value (event type
values, choice list names, their length limits) is unchanged; only the
uuid differs.

The model's name does not depend on the language of the load.

The load form shows the set name when a configurable model is chosen, with
the model's name filled in, and the operator can change it: to keep two
models with the same name apart, or to put two models with different names
together. A name the operator gives is at most 60 characters; left blank,
it is the model's name, whole. It is stored with the load's options and
shown on the load page.

### A site loaded before this change

Before the datamodel stage writes anything, the job looks on the site for
event types whose value starts with the old prefix for this area's model
(`smart-ca-import_<the model's own uuid>`). If there are any, the load
uses that prefix, as it did before, and says so in the plan and on the
load page. The set name does not apply to that load.

So an area loaded before this change stays in its own set, and its
imported events stay valid. An area loaded for the first time after it
joins the shared set. Merging an old set into a shared one is not part of
this work.

## A load adds; it does not take away

These rules apply to pushes from files (smart-able's loads). The live sync
from SMART Connect, whose sets belong to one area each, behaves as today.

**Choices**

- An option on the site that this area's model does not have is left as
  it is. Today it is deactivated.
- An option that is active on the site stays active, even where this
  area's model has it inactive.
- An option that is inactive on the site becomes active if this area's
  model has it active.
- A new option is created as this area's model has it.
- Display text and order are written from this area's model for the
  options it has, as today.

**Event types**

- An event type that is active on the site stays active. One that is
  inactive becomes active if this area's model has it active. A type the
  site has active and this area's model has retired is not written at all:
  the retired version's name and fields must not replace the active one's.
- An event type the site has that this area's model lacks is left alone,
  as today.
- An existing event type keeps its event category. Today the push moves
  it to the category of the current load.
- Display name and schema are written from this area's model where they
  differ, as today. GUNDI-5949 adds the choice to keep the site's.

**When two areas' models of one name differ.** The set on the site ends
up with the union of their options, and each differing event type's
schema is the last load's. The plan says so before anything is written: a
warning that names the event types this load would change and the number
of options it would add, shown only when the set is already on the site.
It does not stop a load.

## The event category

The load keeps its event category option. It decides where event types
that this load creates go.

- When the set is already on the site, new event types join the category
  the set's event types are in (the one most of them are in), and the
  option is not used. The plan and the load page name that category.
- When the set is new and the load has a set name, the default category
  is `smart-<set name>` made safe by the existing rule (2 to 30 characters
  of letters, digits, `_` and `-`). Without a set name the default stays
  `smart-<conservation area id>`.

## Where the work is

| Repository | What changes |
| --- | --- |
| `PADAS/earthranger-smart-utils` | `push_datamodel_files` takes `additive: bool = False`. When true: `upsert_choices` keeps orphans and never deactivates; the event type update never deactivates and never changes the category of an existing type. The CLI's `datamodel --from-file` gains `--additive`. Default behaviour is unchanged. A release. |
| `PADAS/er-smart-able` | The set name option (API, load form, load page, five languages). The key and prefix. The check for an old prefix on the site. The category rule. The plan's warning. Every push is additive. Help page for loads, `docs/decisions.md`. The load image's pin of the library. |

The library is released first; the app then pins it.

The model's own uuid still selects the configurable model's file in the
export. Only the key passed to the library, and the prefix the preflight
and the import use, come from the set name.

## What stays as it is

- The import ledger and the identifiers of imported patrols and events,
  which are per site and conservation area.
- Patrol types, ranger subjects, teams and the universal patrol fields,
  which are already site-wide.
- A load without a configurable model: one set for the site, now additive.
- An option or event type removed from SMART stays active on the site. An
  administrator deactivates it there.

## Not in this work

- Moving a site's old per-area sets into a shared set.
- One national set across regions whose models have different names. The
  operator can ask for it by giving the loads one set name.
- Keeping an administrator's edits to an event type through a later load
  (GUNDI-5949).

## Tests

Library, against the fake site the push tests already use:

- An additive push of a second model whose list lacks an option of the
  first leaves that option active, and adds the second's own.
- An additive push does not deactivate an active option or event type,
  and activates an inactive one the model has active.
- An additive push leaves an existing event type in its category and puts
  a new one in the category given.
- A push that is not additive behaves as before (the existing tests,
  unchanged).

App:

- Two models with different uuids and one name give one prefix; names
  that differ only in case or spacing give one prefix; different names
  give different prefixes.
- A site that has event types under the model's own uuid keeps that
  prefix, and the plan says so.
- Two areas loaded into one fake site with one set name: the site has one
  set of event types, not two; every choice value the first area's events
  carry is still active; the first area's event types are still in their
  category.
- The plan of the second area carries the warning when its model differs
  and does not when it is the same.
- A set name over 60 characters is refused, and so is one sent without a
  configurable model; a blank one becomes the model's name.

By hand, before release: plan the two local Region 5 areas into one test
site with their configurable models and confirm 18 event types and 22
choice lists after both, where today there are 36 and 44.

## Acceptance (from the ticket)

- After a load of area B, each choice option that area A uses stays
  active.
- After a load of area B, the events of area A still open with all their
  values in the web form.
- Two areas with the same data model share one set of event types.
- The load page says which event category the event types go to when the
  site already has them.
- A test loads two areas with different lists into one site and fails on
  today's behaviour.
