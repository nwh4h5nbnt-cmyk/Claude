# Setting up the database — Google Sheets

Click-by-click. No coding — the one script you need is written already, and you
copy and paste it in step 6.

Set aside about an hour. Do it in order; later steps depend on earlier ones.

---

## Before you start

- A Google account
- The file `output/for_airtable/cards_import_2026-08-launch.csv` from this repo
  (the name says Airtable, but it's a plain CSV and imports into Sheets fine)

---

## Step 1 — Create the spreadsheet

Make a new Google Sheet called **Loyalty**. Create three tabs, named exactly:

- `Members`
- `Cards`
- `Activation log`

Put these headers in **row 1** of each. Spelling and capitalisation matter —
the script looks columns up by name. Order doesn't matter, so you can rearrange
columns later without breaking anything.

**`Members`** — A1 across:

```
Email | Name | Level | Joined | Last activated | Consent
```

**`Cards`** — A1 across:

```
Card code | Level | Status | Member email | Activated at | Batch
```

**`Activation log`** — A1 across:

```
Time | Submitted code | Submitted email | Result | Reason
```

Freeze row 1 on each tab (**View → Freeze → 1 row**) so headers stay put.

---

## Step 2 — Import your cards

On the **Cards** tab: **File → Import → Upload**, choose
`cards_import_2026-08-launch.csv`.

Set **Import location** to *Append to current sheet* and **Separator type** to
*Detect automatically*.

You should end up with ~990 rows, all showing `unissued`. The CSV has no
`Member email` or `Activated at` values — that's correct, the script fills them
in.

Do this again after every future print run. It appends, so existing cards are
untouched.

---

## Step 3 — Build the signup form

This is the one behind the QR code on your table standees.

Go to **forms.google.com**, create a blank form called something like
*Join the Guild*. Add three questions, titled **exactly** as below:

| Question title | Type | Required |
|---|---|---|
| `Name` | Short answer | Yes |
| `Email` | Short answer | Yes |
| `Consent` | Checkboxes, one option | No |

For `Consent`, make the single checkbox option read something like *"Email me
about events, early ticket access and member offers"*.

Those exact titles matter — the script reads answers by question title. If you
want different wording on screen, change the titles at the top of `Code.gs` to
match instead.

Add your privacy policy link in the form description. You're collecting names
and emails for marketing, so the opt-in needs to be there and the policy needs
to be reachable.

**Under Settings → Presentation**, set the confirmation message to:

> **You're in.** Show this screen to bar staff to claim your LVL 1 card.

**Connect it to the spreadsheet:** Responses tab → green Sheets icon → *Select
existing spreadsheet* → your **Loyalty** sheet. This creates a new tab. Rename
that tab to exactly `Signup responses`.

Copy the form's share link — that's what your standee QR points to.

---

## Step 4 — Build the activation form

This is the one on the back of every card.

Create a second form called *Activate Card*. Two questions, titled exactly:

| Question title | Type | Required |
|---|---|---|
| `Card code` | Short answer | Yes |
| `Confirm your email` | Short answer | Yes |

Set the confirmation message to:

> **Scan received.** Show this screen to bar staff and roll the d20.

Connect it to the same spreadsheet, and rename the new tab to exactly
`Activation responses`.

> **Two things Google Forms can't do**, both minor:
>
> The card code field will be **visible** to the member rather than hidden.
> That's fine — the same code is printed in plain text on the card in their
> hand. And because the validator checks the code is real, unused and exactly
> one rank up, typing a different code in gets them nowhere.
>
> The confirmation screen is **fixed text** — it can't say "LVL 4 ACTIVATED"
> with their actual level. Staff are standing there watching the scan, so it
> rarely matters. The `webapp/` prototype in this repo shows what the dynamic
> version would look like if you decide it's worth building later.

---

## Step 5 — Get the prefill link

This is what makes the QR fill the code in automatically.

On the *Activate Card* form, click the **⋮** menu (top right) → **Get
pre-filled link**. Type `DUMMYCODE` into the Card code box, leave the email
blank, and click **Get link** → **Copy link**.

You'll get something like:

```
https://docs.google.com/forms/d/e/1FAIpQL.../viewform?usp=pp_url&entry.123456789=DUMMYCODE
```

Keep that safe — you need it in step 8.

---

## Step 6 — Paste in the script

In your spreadsheet: **Extensions → Apps Script**.

Delete whatever is in the editor. Open `google-sheets/Code.gs` from this repo,
select all, and paste it in. Click the save icon.

Now add the trigger:

1. Click the **clock icon** (Triggers) in the left sidebar
2. **+ Add Trigger**, bottom right
3. Set it up exactly like this:
   - Function to run: **onFormSubmit**
   - Event source: **From spreadsheet**
   - Event type: **On form submit**
4. **Save**

Google will ask you to authorise the script. Click through — you'll hit a
"Google hasn't verified this app" screen, which is normal for your own scripts.
Click **Advanced** → **Go to (project name)** → **Allow**.

> Pick **From spreadsheet → On form submit**, not the form's own trigger. The
> spreadsheet version is the one that can see which tab a response landed in,
> which is how the script tells your two forms apart.

---

## Step 7 — Test it before printing anything

Walk the whole journey yourself:

1. Submit the signup form with your own email. Check **Members** shows you at
   level **0**.
2. Copy any level 1 code from the Cards tab. Submit the activation form with
   that code and your email.
3. Check three things: you're now **level 1**, that card row says
   **activated** and records your email, and the **Activation log** has a row
   saying `activated`.
4. Now try to break it. Submit the same code again — should reject. Try a
   level 5 code — should reject with "cannot skip levels". Try a made-up code
   — should reject. Every one should leave Members and Cards untouched and
   write a `rejected` row to the log explaining why.

If all of that behaves, the system works. Delete your test member row, set
those test cards back to `unissued`, and clear the log before going live.

---

## Step 8 — Generate the real QR codes

Only now, once the activation form exists.

The QR images in this repo currently point at a placeholder domain and **will
not work**. Regenerate them against your real form, using the prefill link from
step 5 — replace `DUMMYCODE` with `{code}`:

```
python3 generate_cards.py \
  --url-template "https://docs.google.com/forms/d/e/1FAIpQL.../viewform?usp=pp_url&entry.123456789={code}" \
  --batch "2026-08-launch"
```

Google Forms URLs are long, which makes a dense QR. If you can, point a short
domain at the form and use `--base-url` instead — a shorter URL scans notably
faster in dim bar lighting.

**Scan one of the regenerated images with your phone before sending anything to
the printer.** It should open the form with the code already filled in.

---

## Day to day

You mostly won't touch this. When you do:

**Someone lost their card.** Find it in Cards, set Status to `void`. Find the
member, set their Level back one. Issue a replacement from the stack.

**Someone says their scan failed.** Look in the Activation log — the Reason
column says exactly why.

**Sending a campaign to high ranks.** On Members, Data → Create a filter, then
filter Level ≥ 6 and copy the emails into your email tool.

**Monthly lottery.** Copy Members into a new sheet, repeat each person's row
Level times, then pick a random row. Higher ranks get proportionally more
chances, which is the whole point.

---

## If something isn't working

**Nothing happens on form submit** — the trigger isn't set up, or you picked
the form's trigger rather than the spreadsheet's. Redo step 6.

**Every scan rejects with "No such card code"** — the codes were never
imported, or you regenerated codes after importing. The Cards tab and the
printed cards must come from the same batch.

**Script error mentioning a column or tab name** — something is spelled
differently in the sheet than at the top of `Code.gs`. Fix either side so they
match.

**Level didn't change but the log says activated** — the Level column contains
text rather than numbers. Select it and use Format → Number → Number.

**Answers arrive blank** — a form question title doesn't match the `Q_` values
at the top of `Code.gs`. Google identifies answers by question title, so those
have to agree exactly.
