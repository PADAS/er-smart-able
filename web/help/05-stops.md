# When a load stops

A run stops where the site needs something the API cannot do, or where the site is not ready for the patrols. Each finding on the load page names what to do; the entries here give the same instruction with more room. Values the finding shows with a copy button are exact: EarthRanger matches them by name.

After fixing the site, press **Continue**. The run repeats the early stages, which is quick, and goes on.

## Patrol setup

### Create a patrol team {#finding-team}

SMART patrols name a team; EarthRanger's API cannot create teams. In Django admin, open **Patrol configuration › Teams** and add a team whose *display* is exactly the team name shown. The finding lists the SMART members of the team, for your reference; the import resolves the team by its name only. One entry per missing team; create them all, then Continue.

### Put the rangers in the roster subject group {#finding-roster_group}

No roster group was given when the load was created, so the ranger subjects were created but not put in the group rangers are picked from. Either plan the load again with a roster group named, which lets the run add them, or in Django admin open **Patrol configuration › member subject groups**, choose or create the group, and add the subjects.

### Add the subjects to the subject group {#finding-permission_subject_group}

The roster group exists but the site user cannot change subject-group membership. Either grant the user that permission and Continue, or add the subjects to the group yourself in **Django admin › Subject groups**. The group name is shown with a copy button.

### Enable the patrol_schemas feature {#finding-enable_patrol_schemas}

The site has the `patrol_schemas` preview feature off, so it has no patrol legs, universal patrol fields, teams or rosters to import into. In Django admin, open **Preview features › patrol_schemas** and enable it for this tenant. Ask EarthRanger Core if the page is not available. Then Continue; the universal patrol fields are written on the next pass.

### Grant permission: patrol types {#finding-permission_patrol_types}

The site user cannot create or change patrol types. In Django admin, open **Users › the user** and add `activity | patrol type | Can add/change patrol type`. Then Continue.

### Grant permission: universal patrol fields {#finding-permission_segment_schema}

The site user cannot write the universal patrol fields (the segment schema). Add `activity | segment type | Can change segment type`; today that needs a superuser. Then Continue.

### Grant permission: subjects {#finding-permission_subjects}

The site user cannot view, add or change subjects, so the ranger subjects could not be created or matched. Add `observations | subject | Can view/add/change subject`. Then Continue.

### Grant permission: patrol configuration {#finding-permission_patrol_config}

The site user cannot read the patrol configuration, which teams and rosters are checked against. Add `activity | patrol | Can view patrol`. Then Continue.

### Pick an icon for each patrol type {#finding-patrol_type_icons}

A warning, not a stop. The API cannot set a patrol type's icon, so the new types show EarthRanger's default patrol icon until you choose one in **EarthRanger admin › Patrol types**.

### Name the stations SMART left unnamed {#finding-station_names}

A warning, not a stop. Some stations have no name in any SMART language, so they were created with a placeholder such as `Unnamed station 1a2b3c4d`. Name them in SMART and re-export, or rename the choice in **Django admin › Choices** (field `patrol_station`); a later run puts the placeholder back until SMART has a name.

## Preflight

### The bundle's timezone was inferred {#finding-timezone}

A warning. SMART did not record the conservation area's timezone, so the extraction inferred it from where the waypoints are. Patrol and observation times are converted with that zone. If it is wrong, set `SMART_ABLE_TIMEZONE` for the extraction and extract the dataset again; the quirks page explains how timezones are handled.

### Labels are missing in the chosen language {#finding-language}

A warning. Some data-model elements have no label in the language the load was created with, so they fall back to the bundle's default language or any language that has one. The dataset's Data Model tab shows how well each language is covered; plan the load again with the best-covered one if the labels matter.

### Leg days with no time information {#finding-time_coverage}

A warning, nothing to do. Some leg days have no track, no start or end time and no timed waypoint, so their segments cover the whole day. Each such segment is recorded with `time_source: date_only`.

### A preflight check could not run {#finding-check_failed}

One of the checks raised an error before it could report, usually a connectivity or permission problem with the site. The message names the check and the error. Fix the cause, then Continue; preflight runs again from the start.

### The patrol_schemas feature is off {#finding-feature_flag}

The same condition as *Enable the patrol_schemas feature* above, seen from preflight. Enable the feature, then Continue.

### The site user lacks permissions {#finding-permissions}

The finding lists each permission the import needs and the user does not have. Grant them in **Django admin › Users › the user**, app `activity`. Creating events in a category needs that category's create permission, usually granted through a permission set. Then Continue.

### Patrol types are missing or inactive {#finding-patrol_types}

Patrol setup creates the types the legs need, so on a run this normally means a type was deactivated afterwards. Activate it in **EarthRanger admin › Patrol types**, or Continue to let patrol setup recreate it. In a plan this is expected: the plan writes nothing, and the finding is marked as something the run will create.

### Universal patrol fields are missing or deprecated {#finding-segment_schema}

Patrol setup writes these fields. If an admin deprecated one on purpose, restore it in the patrol form builder; otherwise Continue. In a plan this is expected.

### Options the patrols use are missing or inactive {#finding-choices}

A warning. Some dropdown options the patrols use are not on the site or were switched off, so those fields would be stored without a matching entry. Patrol setup creates them; an option an admin switched off can be re-activated in **Django admin › Choices**.

### Patrol members cannot be put on a segment {#finding-subjects}

The ranger subjects for these members do not exist, or are not in a group listed under **Patrol configuration › members**. Patrol setup creates them and, with a roster group named, adds them to it. Otherwise add them to such a group in **Django admin › Subject groups**. In a plan this is expected.

### Patrol members are retired {#finding-inactive_members}

A warning, nothing to do. EarthRanger accepts only active members on a segment, so the import reactivates these subjects for the run and retires them again when it finishes. The ledger records it.

### Patrol teams are missing or inactive {#finding-teams}

The same condition as *Create a patrol team* above: each team named must exist, active, with that exact display name, under **Patrol configuration › Teams**. One entry per team with a copy button.

### Event types {#finding-event_types}

Observed SMART categories need an active event type on the site. The message says which case applies:

- **No active event type**: the data model has not been pushed under the event category this load uses. In a plan this is expected and marked as something the run will create. On a run, check the event category: if an earlier push used a different identifier, plan the load again with that one.
- **Match more than one event type**: the site has several data model pushes, under different categories, with the same type names. Plan the load again with the event category of the push to import against.
- **Map to an inactive event type**: a warning. The category is a SMART parent or was retired; its events import against the inactive type, which EarthRanger does not offer for new reports. Activate the type in **EarthRanger admin › Event types** if rangers should keep using it.
- **Exist only as configurable model variants**: those categories have one event type per form, and the import cannot yet tell which variant an observation belongs to. Those patrols cannot be imported yet; this needs a variant mapping, which is a follow-up in er-smart-sync.

### No collection event type {#finding-collection_type}

A warning. Some waypoints hold several observations, and the site has no active `incident_collection` event type to group them under, so their events import ungrouped. Add or activate that type in **EarthRanger admin › Event types** to group them.

### Legs on the 1970 placeholder or spanning more than a year {#finding-leg_span}

A warning, nothing to do. SMART stores some leg dates as a placeholder; the import keeps only the leg days that have a track or a waypoint. To correct the dates, fix the leg in SMART and re-export.

### The extraction recorded warnings {#finding-bundle_warnings}

A warning. smart-able noted things about the data when it wrote the bundle. They are listed in the bundle's manifest and explained in *SMART data quirks*.

## Import

### Patrols failed to import {#finding-patrols_failed}

Each failed patrol is listed with its error. Most errors name something missing on the site: a team, a subject, an event type. Fix those, then Continue; only the failed patrols are retried. A `500` on a patrol id that is already on the site is EarthRanger refusing a duplicate; the retry reads the existing patrol and goes on.

### The site's token no longer works {#finding-site_token_rejected}

The site refused the token, so nothing was written. Remove the site, register it again with a working token, and start a new load.
