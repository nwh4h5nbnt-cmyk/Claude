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
- **`google-sheets/Code.gs`** is the validator. You copy it, paste it into your
  spreadsheet's script editor, and never look at it again.

Everything else — forms, landing pages, confirmation screens — is clicked
together in Google Forms. No hosting, no server, no monthly bill.

---

## Start here

1. Play with the **prototype** in `webapp/` to see the journey end to end
   before you build anything. Open `webapp/index.html` in a browser.
2. Read **`google-sheets/SETUP.md`** and follow it. About an hour, start to
   finish.
3. Come back and regenerate the QR codes against your real form URL (setup
   step 8). **The QR images currently in this repo point at a placeholder and
   will not work** — they exist so you can see the format and check the print
   layout.
4. Send `output/for_printer/level_01_*.csv` and your level 1 artwork to a
   printer. Print levels 1–3 first; nobody reaches level 4 in week one.

---

## What's where

| Folder | What it is |
|---|---|
| `google-sheets/` | **The route you're using.** Apps Script validator, its tests, and the click-by-click setup guide. |
| `airtable/` | The same system built on Airtable instead. Kept in case you outgrow Sheets — Airtable's automation builder is friendlier, at roughly £16–20/month once your Cards table passes 1,000 rows. |
| `webapp/` | A clickable prototype of the member journey. No backend — it fakes the database in your browser so you can try to break the rules. |
| `output/` | The generated card codes and everything your printer needs. |

---

## What's in `output/`

| Folder | What it is | Who it's for |
|---|---|---|
| `master_codes.csv` | Every code ever generated | You. Never delete this — it's what stops reprints colliding with old codes. |
| `for_printer/` | One CSV per level | Your printer, alongside that level's artwork |
| `for_airtable/` | Cards table import | Airtable, in setup step 2 |
| `qr_images/` | One PNG per card, zipped per level | Your printer, if they merge from images rather than URLs. Send them the zip for the level being printed. |
| `sticker_sheets/` | A4 sheets, QRs at true 25mm size, 30 per page with cut guides | **The production files.** Print onto adhesive A4, cut, apply by hand. Every sticker carries its rank so a loose one can't end up on the wrong card. |

Current run: **675 cards** across all ten levels, from 250 at level 1 down to
25 at each of the top ranks. Those quantities come out of
`estimate_print_run.py` — see below. Generating codes is free; only printing
costs money, so having all ten levels ready costs you nothing.

---

## How many to actually print

```
python3 estimate_print_run.py --signups 250 --weeks 26
```

It simulates individual members visiting, collecting stamps and levelling up,
then counts the cards actually handed out before the window closes.

Two things shape the answer, and **time matters more than drop-off**: a rank
takes weeks of visits to clear, so almost nobody reaches the upper ranks inside
your first six months however keen they are. That's why the top of the ladder
needs so few cards.

The single biggest lever is **how fast people climb** — stamps per card, and
stamps per visit. Halving the stamps needed per card roughly triples demand for
ranks 5 and up. Signup volume barely changes the shape, only the scale: level 1
is always about 80% of signups, and level 2 is always about 45% of level 1.

Re-run it with your own numbers once you know them. Better still, re-run it
after a month of real data — by then you'll know your true signup rate and how
quickly cards are actually filling.

---

## Reprints

Never regenerate or reuse a code — only ever add new ones. The script reads
`master_codes.csv` first and guarantees new codes don't collide:

```
python3 generate_cards.py --level 1 --count 50 --batch "2026-11-reprint"
```

You don't need to give it the form address again. It reads the last batch's
URL out of `master_codes.csv` and reuses it, then prints what it picked so you
can check. Months later nobody remembers the exact prefill link, and getting it
slightly wrong would produce a stack of dead cards that look perfectly fine.

Pass `--base-url` or `--url-template` only if the address has genuinely
changed.

You get a **new CSV containing only the new codes** — the existing one is never
touched. Import that into the `Cards` tab (it appends, so nobody's progress is
affected) and send the matching `for_printer/` CSV to your printer with the
same artwork as last time.

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
- **Two separate print jobs.** The cards carry no codes at all — bulk print,
  ten designs, cheapest per unit. The stickers are a second job from
  `sticker_sheets/`, applied by hand.
- **Print the sticker sheets at 100%**, never "fit to page". Scaling shrinks
  the code below what phone cameras manage in dim light.
- **Reserve 30 × 34mm** of flat, light, unprinted space on the card back for
  the sticker to land on, clear of the stamp grid.
- **Scan three cards from every delivered batch** before accepting it.

The QR is scanned once, within a minute of the card being handed over, and is
dead weight afterwards. It doesn't need to survive the card's working life —
put it in the least precious spot on the back, away from the stamp grid.

---

## Running the tests

Only relevant if someone changes a validator:

```
node google-sheets/test_code.js          # 19 tests
node airtable/test_automation_script.js  # 13 tests
```

Both fake enough of their platform's API to run the real validator unmodified,
covering every accept and reject path — level skipping, reused cards, voided
cards, unknown emails, duplicate signups, and the guarantee that a rejected
scan changes nothing except the log.

**The rules live in three places** — `google-sheets/Code.gs`,
`airtable/automation_script.js`, and the prototype in `webapp/index.html`. They
are deliberately identical. If you change one, change all three.

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

**The confirmation screen is static.** Google Forms can't show a personalised
"LVL 4 ACTIVATED" message — its confirmation is fixed text. Staff are standing
there watching the scan, so it rarely matters. The `webapp/` prototype shows
what the dynamic version would feel like if you decide it's worth building.

**The card code is visible on the activation form.** Google Forms has no hidden
fields, so the prefilled code shows on screen. Harmless — the same code is
printed on the card in the member's hand, and typing a different one gets them
nowhere unless they happen to hold that exact unused card at exactly the right
rank.

**Stamp fraud is a social problem, not a technical one.** Unique card codes
protect the database completely, but nothing stops a forged stamp. Use a
distinctive stamp, keep it behind the bar, and rotate between two or three
designs periodically.
