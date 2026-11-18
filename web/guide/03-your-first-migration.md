# Your first migration

Have your SMART file and your EarthRanger token ready; [Get your inputs](02-get-your-inputs.md) says what they are. The steps below follow the order the app works in, which the app's own [Overview](../help/01-overview.md) also lists.

## 1. Sign in

Open [the app](https://smart-able-977100970772.us-central1.run.app/) and sign in with your EarthRanger Google account.

## 2. Upload the SMART file

1. On the **Datasets** page, press **Upload a backup or export**.
2. Give the dataset a name you will recognise, such as the conservation area and the date, and choose your `.zip` file.
3. Press **Upload**. A large backup takes a while to send; leave the dialog open until it closes.

The new dataset appears in the list as **uploading**, then **queued**, then **running**, then **ready**. That takes a few minutes, and the page refreshes itself. If it ends as **failed**, open the dataset: the Overview shows the error and the end of the log. [Statuses](../help/04-statuses.md) explains each status.

## 3. Browse what was extracted

Open the dataset. Its Overview lists each conservation area in the file, with its patrol and waypoint counts. Press **Browse** to look through the patrols, the map, the observations and the data model.

Check that this is the conservation area you expected and that the counts look right. Nothing has been written to EarthRanger yet.

## 4. Add a site

1. Open the menu under your email address and choose **EarthRanger sites**.
2. Press **Add a site**.
3. Enter a name, the site address, and the token.

The app checks the token with the site before it saves it. A wrong host or a dead token is refused on the spot. See [Sites and tokens](../help/02-sites.md).

## 5. Plan the load

1. Go back to the dataset and press **Load into EarthRanger** beside the conservation area.
2. Choose the site. Leave the other choices as they are unless you know you need them; [Loading a dataset](../help/03-loading.md) explains each one.
3. For a first run, set **What to load** to **The data model only**. It is quick, it shows up everything an administrator has to do on the site, and you can add the patrols with a second load afterwards.
4. Press **Make the plan**.

A plan talks to the site but writes nothing. When it is ready, the load page shows what the run would create or update, and any findings.

## 6. Read the plan, then confirm

Read the findings. **Blocking** findings are things a person must do on the EarthRanger site, such as creating a patrol team; each one says what to do. **Warnings** are for your information and never stop a run.

Press **Confirm and load**. If there are blocking findings, the button says where the run will stop. That is normal: the run writes everything before that point, and confirming is how you make progress.

## 7. If the load stops

The status becomes **needs attention** and the findings say what is needed. Nothing written so far is undone.

1. Do what the finding says, or ask the site's administrator to. [When a load stops](../help/05-stops.md) has an entry for every finding.
2. Press **Continue**. The run starts again, skips what is already there, and goes on.

## 8. Load the patrols

When the data model load is **done**, start a second load of the same conservation area into the same site, with **What to load** set to **The data model and patrols**. Leave the dates empty to load every patrol, or set them to bring across a few months first.

A long load keeps running on its own. The load page shows its progress and the time left; you can close the page and come back.

## 9. Check the result in EarthRanger

Open the EarthRanger site and look for:

- the event types, under the event category the load page names;
- the rangers, as subjects in the roster group;
- a few patrols you recognise from step 3, with their tracks and reports.

The load page's **Rangers** section lists every ranger the load created, for whoever gives them user accounts. [Loading a dataset](../help/03-loading.md#rangers-accounts) says how to link an account to a ranger.
