# Sites and tokens

A site is an EarthRanger host, such as `example.pamdas.org`, and an API token for an EarthRanger user there. Loads write to the site as that user.

**Registering a site.** Enter a name, the host and the token. smart-able calls the site's `/user/me` with the token before saving anything, so a wrong host or a dead token is refused on the spot. The site card shows the last characters of the token and the user it works as.

**Where the token is kept.** In Google Secret Manager, under a secret named after the site. It is never stored in the database, never written to a log, and never returned by the API. If the token is rotated or revoked, remove the site and register it again; loads that referenced the old site stay readable but cannot be continued.

**Which user to use.** The import needs a user that can manage patrol types, subjects, subject groups, patrol configuration and the universal patrol fields, and can create events in the category the data model is pushed under. A superuser is the simple choice. The finding *the operator lacks permissions* names each missing permission when a narrower user is used.

**Sharing a site.** Sharing lets that person start loads into the site with your token. Only you can share or remove a site. Someone with access to a dataset but not to the site cannot load into it.

**The URL.** Give the host only, without `https://` or a path. Ports, IP addresses and credentials in the URL are refused.
