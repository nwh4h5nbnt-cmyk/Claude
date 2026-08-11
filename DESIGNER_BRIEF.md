# Card artwork brief — how the unique codes work

**Short version: it's a data merge.** The same mechanism as personalised
invitations or numbered event tickets. You are not designing 675 cards — you
are designing **ten**, each with one small placeholder that gets filled from a
spreadsheet at output time.

---

## What you're actually delivering

Per rank, two print-ready files:

- **Front** — the rank artwork. No variable content at all.
- **Back** — the stamp grid, plus a reserved zone where the code goes.

That's twenty files total. The code placeholder is the only thing that differs
card to card, and nobody places it by hand.

---

## Two ways to get the codes onto the cards

Agree which one with the printer before you build the files, because it changes
what you hand over.

### Route A — the printer merges (variable data printing)

You deliver the twenty flat artwork files with the code zone left **empty but
clearly marked**, plus the plain CSV for each rank. The printer's RIP drops
each code in as it prints.

Ask them for **"variable data printing"** or **"VDP"**. Every trade digital
printer does it. Expect a setup fee.

**You hand over:** artwork PDFs + `output/for_printer/level_NN_*.csv`

### Route B — you merge, printer prints a normal job

You run the merge yourself in InDesign and export one flat multi-page PDF. The
printer receives an ordinary job with no VDP surcharge, and you keep complete
control over placement.

**You hand over:** one merged PDF per rank.

This is usually cheaper and always more predictable. Details below.

---

## Running the merge in InDesign

Everything you need is in `output/for_designer/`. Each rank has a CSV and a
folder of QR images sitting beside it — the paths in the CSV are relative, so
as long as those two stay together it just works.

1. Open your card **back** file.
2. Draw a **graphic frame**, exactly 20 × 20 mm, where the QR goes.
3. Draw a **text frame** directly beneath it for the readable code.
4. `Window → Utilities → Data Merge`.
5. Panel menu → **Select Data Source** → pick
   `level_01_..._indesign.csv`.
6. Drag the **`@qr`** field onto the graphic frame. The `@` prefix is how
   InDesign knows those values are images rather than text — it's already in
   the file, don't rename the column.
7. Drag **`card_code`** into the text frame.
8. Panel menu → **Create Merged Document**.
9. Export the result as PDF/X-1a or PDF/X-4, whichever your printer asks for.

Repeat per rank. Ten runs, and ranks 4–10 aren't needed yet.

---

## The code zone — hard requirements

These are the ones that cause reprints if they're wrong.

| | Spec |
|---|---|
| **QR size** | 20 × 20 mm minimum at finished size. Bigger is fine. |
| **Quiet zone** | At least 2 mm clear on all four sides. No artwork, no rules, no texture intruding. |
| **Contrast** | Dark modules on a light ground. Near-black on near-white is safest. |
| **Background** | Flat colour only. No gradient, no photograph, no paper texture behind the code. |
| **Readable code** | Directly beneath the QR. 7 pt minimum, generous letter-spacing so characters separate cleanly. |
| **Position** | On the back, outside the stamp grid, with a visible divider or frame so it reads as intentional. |

### On inverting the QR

**Don't.** Light modules on a dark ground fail on a meaningful share of phone
scanners, and you only discover it after printing.

The rank artwork will almost certainly want to be dark and moody. The code
doesn't get to be. Give it a light panel and make that panel a deliberate part
of the design — a parchment strip, an inset plate, a torn label. Something that
looks chosen rather than tolerated.

### One thing that buys you freedom

The QR is scanned **once**, within about a minute of the card being handed
over, and is dead weight for the rest of the card's life. It does not need to
survive weeks of stamping, beer, or wallet abrasion.

So put it in the least precious real estate on the back. It doesn't deserve
prime position, and treating it as disposable furniture rather than a hero
element will make the card look better.

The readable code underneath is the part worth protecting — it stays useful for
support lookups long after the QR is spent.

---

## Character set

Codes are six characters drawn from `23456789ABCDEFGHJKMNPQRSTVWXYZ`, always
starting with a letter.

`I`, `L`, `O`, `U`, `0` and `1` are deliberately excluded so nothing gets
misread when someone reads a code down the phone. **Pick a face where the
remaining characters stay distinct** — particularly `5`/`S`, `8`/`B` and
`2`/`Z`. A monospaced or clearly-drawn geometric face is safest; an ornate
display face is not.

---

## Things that go wrong

**Grey boxes where QRs should be** — the CSV and its image folder have been
separated. They must stay side by side.

**Blurry or cropped QRs** — the graphic frame's fitting is scaling the image.
Set frame fitting so content fits the frame exactly. The supplied PNGs are
around 420 dpi at 20 mm, so there is plenty of resolution; anything soft means
it's being resampled.

**Broken paths after editing the CSV** — opening it in Excel and re-saving can
rewrite the path column. If you need to edit it, use a plain text editor, or
ask for a regenerated file.

**The wrong codes on the wrong rank** — this is the expensive one. Run each
rank as a completely separate job with only that rank's CSV and only that
rank's artwork open. Then there is nothing to misalign.

---

## Before the full run

Print a proof and **scan three cards from it with a cheap Android phone in dim
light.** Bar lighting, not studio lighting.

Check that each one opens a form with the code already filled in, and that the
code on screen matches the code printed on that card. Two minutes, and it
catches every failure listed above.
