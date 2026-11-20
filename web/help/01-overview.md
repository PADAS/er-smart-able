# Overview

smart-able takes a SMART conservation-area backup or export, extracts it so you can browse it here, and loads it into an EarthRanger site. The steps, in order:

1. **Upload** a SMART system backup zip, a zipped SMART Desktop install folder, or a Conservation Area export. The dataset belongs to you; share it with colleagues afterwards from its dataset page.
2. **Extract** runs as a background job for a few minutes. It reads the database, writes a browsable site for each conservation area, and publishes a migration bundle for each one. The dataset list refreshes itself while the job runs.
3. **Browse** the extracted data from the dataset page (**Browse** on its Overview, or the views under **Data** in the sidebar): patrols, waypoints, observations, the data model, and the quirks the extraction found.
4. **Register a site**: an EarthRanger host and an API token. The token is checked before it is saved. See *Sites and tokens*.
5. **Load** a conservation area into a site from the dataset page, on its Overview, or under **Loads** in the sidebar. A load first produces a plan of everything it would write; you confirm the plan, and the run writes it. Where the site needs something only a person can do, the run stops and tells you what. See *Loading a dataset* and *When a load stops*.

Everything you upload, extract and load is shared only with the people you share it with. EarthRanger support staff can also view datasets and sites, to help with a migration; they cannot change them or load data. Deleting a dataset deletes its extracted data, bundles and load records; it never removes anything from EarthRanger.

The uploaded backup itself is stored for a limited time (30 days on the hosted app) and then deleted automatically. The dataset page shows the date, and the dataset's owner can delete the backup sooner. The extracted data is not affected: it stays until the dataset is deleted. To extract again after the backup has gone, upload it again.
