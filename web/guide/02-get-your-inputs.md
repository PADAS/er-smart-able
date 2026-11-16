# Get your inputs

You need two things before you open the app: a file from SMART, and access to the EarthRanger site the data is going to.

## From SMART: a backup or an export

The app accepts any one of these, as a single `.zip` file:

- **A Conservation Area export.** This is the smallest and the quickest to extract, and holds one conservation area.
- **A SMART system backup.** SMART names it `SMART_<date>.bak.zip`. It can hold several conservation areas; you choose which to load later.
- **A zipped SMART Desktop install folder.** Zip the whole folder SMART Desktop is installed in. Use this when you cannot run SMART to make an export or a backup.

Upload the `.zip` as it is. Do not unzip it, and do not upload a file from inside it.

These steps are not yet verified against SMART Desktop.
{: .unverified }

To make a Conservation Area export:

1. Open SMART Desktop and sign in to the conservation area as an administrator.
2. Choose **File → Export Conservation Area**.
3. Save the export. It is a `.zip` file.

To make a system backup, use SMART Desktop's backup command while signed in as an administrator, and keep the `SMART_<date>.bak.zip` file it writes.

The person who runs SMART at the site is usually the one to make the file. A backup holds ranger names and patrol locations, so ask them to send it by a private channel, not a public link.

## From EarthRanger: the site and a token

The app writes to EarthRanger as one EarthRanger user, through that user's API token. You need:

- **The site's host**, such as `example.pamdas.org`. Give the host only, without `https://` or a path.
- **An API token** for a user on that site. Ask the site's EarthRanger administrator for one.

The user behind the token must be able to manage patrol types, subjects, subject groups, patrol configuration and the patrol fields, and to create events. A superuser is the simple choice. With a narrower user, the load tells you each permission that is missing.

The app checks the token against the site before it saves it, and shows only its last characters afterwards. [Sites and tokens](../help/02-sites.md) says where the token is kept and who can use it.

It is worth loading into a test or staging site first, if the customer has one.

## Next

With the file and the token in hand: [Your first migration](03-your-first-migration.md).
