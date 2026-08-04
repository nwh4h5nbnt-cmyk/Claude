# Setting up the database

Click-by-click. No coding — the one script you need is written already, and you
copy and paste it in step 5.

Set aside about an hour. Do it in order; later steps depend on earlier ones.

---

## Before you start

- A free Airtable account
- The file `output/for_airtable/cards_import_*.csv` from this repo

---

## Step 1 — Create the base and its three tables

Make a new base called **Loyalty**. Then build three tables. For each field
below, click **+** at the right of the table, name it, and pick the field type
listed.

Airtable gives every new table three sample fields called Name, Notes and
Assignee — delete Notes and Assignee, and rename Name as instructed.

### Table 1: `Members`

| Field | Type | Notes |
|---|---|---|
| Email | Single line text | Rename the default Name field to this. It's the first column. |
| Name | Single line text | |
| Level | Number, integer | **Set the default value to 0.** Important — new signups start unranked. |
| Joined | Created time | Fills itself in |
| Last activated | Date | Include a time |
| Consent | Checkbox | Marketing opt-in |

### Table 2: `Cards`

| Field | Type | Notes |
|---|---|---|
| Card code | Single line text | Rename the default Name field to this |
| Level | Number, integer | |
| Status | Single select | Add exactly three options: `unissued`, `activated`, `void` — lowercase |
| Member | Link to another record | Link it to **Members** |
| Activated at | Date | Include a time |
| Batch | Single line text | Which print run it came from |

The three Status options must be spelled exactly as above, in lowercase. The
script matches on them.

### Table 3: `Activation log`

| Field | Type | Notes |
|---|---|---|
| Submitted code | Single line text | Rename the default Name field to this |
| Submitted email | Single line text | |
| Result | Single select | Two options: `activated`, `rejected` — lowercase |
| Reason | Single line text | The script explains itself here |
| Time | Created time | |

---

## Step 2 — Import your cards

In the **Cards** table, click the **+** next to your view names → **Import
data** → **CSV file**, and choose `cards_import_2026-08-launch.csv`.

Match the columns to the fields you made. You should end up with ~990 rows, all
showing `unissued`.

Do this again after every future print run — it appends, so existing cards are
untouched.

---

## Step 3 — Build the signup form

This is the one behind the QR code on your table standees.

In the **Members** table, click **+** next to the view names → **Form**. Show
only these fields:

- **Name** — required
- **Email** — required
- **Consent** — relabel it something like *"Email me about events, early
  ticket access and member offers"*

Hide the Level field. It fills in as 0 automatically because of the default you
set in step 1.

Under the form's **Submit** settings, set the message to something like:

> **You're in.** Show this screen to bar staff to claim your LVL 1 card.

Add a link to your privacy policy in the form description. You're collecting
names and emails for marketing, so you need the opt-in ticked and the policy
reachable.

Copy the form's share link — that's what the standee QR points to.

---

## Step 4 — Build the activation form

This is the one on the back of every card.

In the **Activation log** table, click **+** → **Form**. Show only:

- **Submitted code**
- **Submitted email** — required, labelled *"Confirm your email"*

Set the submit message to:

> **Scan received.** Show this screen to bar staff and roll the d20.

Copy this form's share link. It looks like `https://airtable.com/shrXXXXXXXX`.

> **A note on that message:** Airtable's confirmation screen is fixed text — it
> can't say "LVL 4 ACTIVATED" with the member's actual level. In practice this
> doesn't matter, because staff have just handed over the card and are watching
> the person scan it. If you later want the dynamic, animated level-up screen,
> that's the custom-web-app upgrade, not something Airtable forms will do.

---

## Step 5 — The automation

In the top bar click **Automations** → **Create automation**.

**Trigger:** *When record created* → table **Activation log**.

**Action:** *Run script*.

In the script step you'll see an **Input variables** panel on the left. Add
three, exactly like this:

| Name | Value |
|---|---|
| `code` | the **Submitted code** field from the trigger record |
| `email` | the **Submitted email** field from the trigger record |
| `logRecordId` | the **Record ID** from the trigger record |

The names must match exactly — lowercase, no spaces.

Then open `automation_script.js` from this repo, select all of it, and paste it
into the code panel, replacing whatever is there.

Click **Test** — it'll run against a real log row. Then **turn the automation
on** with the toggle at the top right. It does nothing until you do.

### Optional: email the result

Add a second action, *Send email*, using the script step's `result` output.
Useful if you want members to get a "you're now LVL 4" confirmation. Skip it at
launch if you'd rather keep things simple.

---

## Step 6 — Test it before printing anything

Walk the whole journey yourself:

1. Submit the signup form with your own email. Check **Members** shows you at
   level 0.
2. Pick any level 1 code from the Cards table. Open the activation form,
   paste it in, submit with your email.
3. Check: you're now **level 1**, that card says **activated** and links to
   you, and the log line says `activated`.
4. Now try to break it. Submit the same code again — should reject. Try a
   level 5 code — should reject with "cannot skip levels". Try a made-up
   code — should reject.

If all four behave, the system works. Delete your test member and reset those
test cards to `unissued` before going live.

---

## Step 7 — Generate the real QR codes

Only now, once the activation form exists and you have its link.

The QR images in this repo currently point at a placeholder domain and **will
not work**. Regenerate them against your real form:

```
python3 generate_cards.py \
  --url-template "https://airtable.com/shrXXXXXXXX?prefill_Submitted+code={code}&hide_Submitted+code=true" \
  --batch "2026-08-launch"
```

Replace `shrXXXXXXXX` with your actual form ID from step 4.

Better still, if you have a short domain: point `lvlup.yourbar.com/go` at the
form and use `--base-url "https://lvlup.yourbar.com/go"` instead. A shorter URL
makes a less dense QR, which scans faster in bar lighting.

Either way, **scan one of the regenerated QR images with your phone before
sending anything to the printer.** It should open the form with the code
already filled in.

---

## Day to day

You mostly won't touch this. When you do:

**Someone lost their card.** Find it in Cards, set Status to `void`. Find the
member, set their Level back one. Issue a replacement from the stack.

**Someone says their scan failed.** Look in the Activation log — the Reason
column says exactly why.

**Sending a campaign to high ranks.** In Members, filter Level ≥ 6, export,
paste into your email tool.

**Monthly lottery.** Export Members. In a spreadsheet, give each person a
number of entries equal to their Level, then draw a random row. Higher ranks
get proportionally more chances, which is the whole point.

---

## If something isn't working

**Every scan rejects with "No such card code"** — the codes were never imported,
or you regenerated codes after importing. The Cards table and the printed cards
must come from the same batch.

**The automation never runs** — check the toggle is on. New automations are off
by default.

**Script errors about a field** — a field name in Airtable doesn't match the
names at the top of `automation_script.js`. Either rename the field or edit
those lines to match.

**Level didn't change but the log says activated** — the Level field is text
rather than a number. It has to be Number.
