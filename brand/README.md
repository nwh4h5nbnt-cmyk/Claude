# The glowing logo

Makes the t&em logo **physically emit more light** than everything around it in
a LinkedIn or Slack feed — on phones and laptops with HDR screens, which is most
of them made in the last few years.

It is not a glow filter and not an animation. The image is flat and ordinary.
The only unusual thing about it is a colour profile that says "read these pixels
as HDR", so the white in the logo gets drawn at up to 4,000 nits while the white
of the page around it sits at about 200. The letters look lit from behind. Your
eye goes there and can't help it.

The white-on-black artwork is close to ideal for this: PQ makes mid-tones read
*darker*, so the black square sinks and the white marks burn.

---

## Doing it

Save the master artwork as `brand/logo.png`. Then, from the top of the repo:

**macOS or Linux**

```
python3 -m pip install pillow
python3 brand/glow.py
```

**Windows**

```
python -m pip install pillow
python brand\glow.py
```

Three files appear in `brand/out/`, and the script checks each one really
carries its HDR tag before it says it's done. If something is missing it tells
you what to do about it rather than throwing an error at you.

If you'd rather not type a path, `./brand/glow.sh` does the same thing on macOS
and Linux — it just calls `glow.py` for you. There is no `.sh` on Windows,
which is why the Python command above is the one to reach for.

Artwork somewhere else? Point at it directly:

```
python3 brand/glow.py ~/Desktop/whatever-its-called.png
```

| File | Where it goes |
|---|---|
| `logo-hdr.jpg` | **LinkedIn, Slack, anywhere you upload.** |
| `logo-hdr-4000.png` | A page you host yourself. Full burn. |
| `logo-hdr-1000.png` | Same, turned down. Use this one if the logo sits next to text someone has to read. |

Source artwork wants to be square, at least 1000px, PNG, on black or
transparent.

---

## Why there are two formats

This is the part that catches people out. The HDR instruction can ride along in
two different places, and they survive uploads very differently:

| Carrier | Survives a platform re-encode? |
|---|---|
| The tag inside a PNG | **No.** LinkedIn converts your PNG to a JPEG and throws the tag away. The logo arrives flat. |
| A colour profile inside a JPEG | **Yes.** Profiles get copied through untouched. |

So the PNG is for pages we control, and **the JPEG is the one that goes to
LinkedIn**. Upload it as the *company page* logo — personal profile pictures get
re-encoded much harder and lose the effect.

---

## Before you ship it

Three things worth knowing, because this is a real trade-off rather than a free
win:

1. **It only exists live, on HDR hardware.** Screenshot it and the magic is
   gone. Nobody can show it to a colleague second-hand.
2. **On screens that don't do HDR it can look worse than the normal logo** —
   smeared or dirty, like something went wrong in the upload. That's a good
   chunk of anyone viewing on an older external monitor at a desk.
3. **Platforms close it.** Slack has already patched theirs. Expect this to stop
   working at some point and keep the ordinary logo to hand.

Keep `logo.png` as the master and treat everything in `out/` as disposable — you
can always regenerate it.

---

## Credit

The technique is reverse-engineered, not invented — Wiz, Port.io and Slack
shipped it first. `hdr_glow.py` and `assets/rec2020-pq.icc` are vendored
unmodified from [tatarco/hdr-glow-logo](https://github.com/tatarco/hdr-glow-logo)
(MIT — see `LICENSE-hdr-glow-logo`), copied in rather than installed so this
keeps working offline. Prior art: [dtinth/superwhite](https://github.com/dtinth/superwhite).
