# Esports bar loyalty scheme

A ten-rank, RPG-styled loyalty programme that runs on physical cards and a
spreadsheet. Members collect stamps, level up, and roll a d20 for a bonus prize
each time they do.

This repo holds the machinery: the card codes, the files your printer needs,
and the validator that keeps the database honest.

---

## The idea in one paragraph

Every physical card carries a unique random code, printed as a QR on the back.
The code is what makes the card a credential rather than a piece of cardboard.
When a member scans it, the system checks the code is real, unused, and exactly
one rank above where they currently are — then promotes them and burns the code
so it can never be used again. Staff never type anything. Their only job is
checking a card is fully stamped before handing over the next one.

---

## You do not need to write code

Two pieces of software exist here and neither asks you to program:

- **`generate_cards.py`** makes the codes and QR images. It has already been
  run — its output is sitting in `output/`. You only run it again for reprints,
  and it's one command that someone can run for you.
- **`airtable/automation_script.js`** is the validator. You copy it, paste it
  into Airtable, and never look at it again.

Everything else — forms, landing pages, confirmation screens, emails — is
clicked together in Airtable. No hosting, no server, no monthly bill until your
Cards table outgrows the free tier.

---

## Start here

1. Read **`airtable/SETUP.md`** and follow it. About an hour, start to finish.
2. Come back and regenerate the QR codes against your real form URL (setup
   step 7). **The QR images currently in this repo point at a placeholder and
   will not work** — they exist so you can see the format and check the print
   layout.
3. Send `output/for_printer/level_01_*.csv` and your level 1 artwork to a
   printer. Print levels 1–3 first; nobody reaches level 4 in week one.

---

## What's in `output/`

| Folder | What it is | Who it's for |
|---|---|---|
| `master_codes.csv` | Every code ever generated | You. Never delete this — it's what stops reprints colliding with old codes. |
| `for_printer/` | One CSV per level | Your printer, alongside that level's artwork |
| `for_airtable/` | Cards table import | Airtable, in setup step 2 |
| `qr_images/` | One PNG per card, zipped per level | Your printer, if they merge from images rather than URLs. Send them the zip for the level being printed. |
| `proof_sheets/` | A4 sheets, QRs at true 20mm size | Checking a batch scans before you accept delivery. Also printable onto adhesive A4 and cut up, if you go the sticker route instead of variable-data printing. |

Current run: **990 cards** across all ten levels, tapering from 300 at level 1
to 20 at level 10. Generating codes is free; only printing costs money, so
having all ten levels ready costs you nothing.

---

## Reprints

Never regenerate or reuse a code — only ever add new ones. The script reads
`master_codes.csv` first and guarantees new codes don't collide:

```
python3 generate_cards.py --level 1 --count 300 \
  --base-url "https://your-real-url/go" \
  --batch "2026-11-reprint"
```

Then import the new `for_airtable/` CSV into Airtable, and send the new
`for_printer/` CSV to your printer with the same artwork as last time.

Levels are independent — reprinting level 1 doesn't affect anything else.

**Knowing when to reorder:** the database can't see your physical stock, so
slip a bright red card into each stack about three-quarters of the way down.
When staff reach it, that's the reorder signal.

---

## Printing notes

- **Keep the QR dark-on-light.** Inverted QR codes fail on a lot of phone
  scanners. If your card art is dark, reserve a light panel for the code.
- **20mm square minimum**, with a clear quiet zone no artwork intrudes into.
- **Print the code in plain text underneath the QR.** It's the fallback when
  the QR won't scan and the lookup key when someone contacts you about a
  problem. The alphabet deliberately excludes `I`, `L`, `O`, `U`, `0` and `1`
  so nothing gets misread.
- **One print job per level.** Ten jobs, each with one artwork file and one
  CSV. There's then no way for the wrong codes to land on the wrong design.
- **Scan three cards from every delivered batch** before accepting it.

The QR is scanned once, within a minute of the card being handed over, and is
dead weight afterwards. It doesn't need to survive the card's working life —
put it in the least precious spot on the back, away from the stamp grid.

---

## Running the tests

Only relevant if someone changes the validator:

```
node airtable/test_automation_script.js
```

13 tests covering every accept and reject path — level skipping, reused cards,
voided cards, unknown emails, and the guarantee that a rejected scan changes
nothing except the log.

---

## Known limits

**No "issued but not scanned" state.** Staff don't touch the system when they
hand a card over, so the database can't tell a card in the stack from one in
someone's pocket. Nothing breaks — the code is still single-use and still
sequence-checked whenever it does get scanned — but you can't audit physical
stock from the database. Count the stack instead.

**Stamps are not tracked.** The database only knows rank. That's deliberate:
tracking individual stamps would mean a scan every visit, and rank is all the
CRM segmentation actually needs.

**The confirmation screen is static.** Airtable forms can't show a personalised
"LVL 4 ACTIVATED" message. Staff are standing there watching the scan, so it
rarely matters. Fixing it properly means a small custom web app, which is the
sensible upgrade once the scheme has proven itself.

**Stamp fraud is a social problem, not a technical one.** Unique card codes
protect the database completely, but nothing stops a forged stamp. Use a
distinctive stamp, keep it behind the bar, and rotate between two or three
designs periodically.
