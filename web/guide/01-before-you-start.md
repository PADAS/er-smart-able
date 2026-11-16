# Before you start

This guide is for someone who has been asked to move a site's SMART data into EarthRanger. It takes you from a SMART backup to a finished first migration, using the hosted SMART migration app. You do not need the command line.

## What the app does

You give it a backup or export from SMART. It reads the SMART database, shows you what is in it, and writes the conservation area into an EarthRanger site: first as a plan you can read, then for real when you confirm.

## What it migrates

- **The data model**: one EarthRanger event type per SMART category, with its fields and dropdown choices.
- **Patrol setup**: patrol types, the patrol fields, and the station choices.
- **Rangers**: one EarthRanger subject per SMART employee who patrolled or is still employed, in a roster group you choose.
- **Patrols**: each patrol with its legs, members, GPS track, observations and photos.

You can load the data model on its own first, or limit the patrols to a range of dates. See [Loading a dataset](../help/03-loading.md).

## What it does not migrate

- **Profiles data.** If the conservation area uses SMART's Profiles plugin, you can look at that data in the app, but it is not loaded into EarthRanger.
- **Patrol teams, patrol type icons and permissions.** The EarthRanger API cannot create these. The load stops and tells an EarthRanger administrator exactly what to create; then you continue.
- **User accounts for rangers.** The load creates the rangers as subjects. Giving a ranger a login, linked to that subject, is a step for an administrator afterwards.
- **A patrol with no start date**, when you load a range of dates.

Nothing the app does removes data from SMART, and deleting a dataset or a load in the app removes nothing from EarthRanger.

## Which SMART versions

- **SMART Desktop 7.5.x**: supported and tested.
- **SMART Desktop 8.0 to 8.1.x**: expected to work, but not yet proven against a real backup. If you have one, tell the EarthRanger engineering team how it goes.

## Where the app is, and who can sign in

The app is at [https://smart-able-977100970772.us-central1.run.app/](https://smart-able-977100970772.us-central1.run.app/).

Sign in with your EarthRanger Google account. If you see "This email is not allowed", ask the EarthRanger engineering team to add your address.

What you upload belongs to you. Nobody else sees a dataset or a site until you share it with them.

## How long it takes

Extraction takes a few minutes. A plan takes a few minutes more. The load itself depends on how fast the EarthRanger site writes: about 0.8 seconds per observation, so a conservation area with 70,000 observations takes about a day. It runs on its own; you do not need to keep the page open.

## Next

Collect the two things you need: [Get your inputs](02-get-your-inputs.md).
