# neofetch-style GitHub profile card

Live at https://github.com/kishore2494 — repo `kishore2494/kishore2494`,
which GitHub renders at the top of the profile because the repo name equals
the username.

## Why this is an SVG and not a code block

The obvious approach is one fenced code block holding both columns. It aligns
fine, but you cannot colour the two columns differently, and that is what
makes the reference screenshot look good. Tested live on GitHub:

| Approach | Result |
| --- | --- |
| ```` ```ansi ```` + escape codes | **Not interpreted.** 0 colour spans; raw `[35m` printed as literal text |
| ```` ```yaml ```` | Colours whole *lines*, so the portrait gets tinted the same blue as the panel |
| ```` ```nginx ```` | Leaves art neutral but only speckles stray `(`, `)`, `~` |
| ```` ```toml ```` / ```` ```http ```` | Everything red |
| ```` ```diff ```` / ```` ```text ```` | No colour at all |

Root cause: the art and the panel **share every line**, and syntax
highlighters tokenize per line. No fence language can ever separate them.

So the card is generated as an SVG and embedded from README.md as an image.
That gives exact per-segment colour, and the dark card looks identical in
GitHub's light and dark themes.

## Where the panel content comes from

Scraped from the two live personal sites, not invented:

| Field | Source |
| --- | --- |
| Host `Aurora AI`, Kernel/Shell roles, Locale `India` | personal-site-2 `/about` — "At a glance" |
| AI/ML, Stack, Web skill lists | personal-site-2 `/about` — "Toolkit" |
| Frontier interests | personal-site-2 `/about` — "Frontier interests" |
| `AI and Data Science graduate` | both sites, intro paragraph |
| `10+` projects, `25+` essays | personal-site-2 landing counters |
| Email, LinkedIn, Twitter, Medium | footer links on both sites |
| Repos / commits / stars / followers / joined | GitHub API, snapshot on 31 Aug 2026 |

Deliberately left out: the Fieldproxy work email and employer. Neither
personal site mentions Fieldproxy, so the card reflects the public identity
those sites present. Add them back if you want both.

`Uptime` is the **GitHub account age**, not a birthday — the reference
screenshot used a person's age there, which is not derivable from anything
available.

## Regenerating

    python3 gen.py --image portrait.png --config profile.json --out profile.svg \
        --ramp andrew --invert --percentile 38 --aspect 0.25 \
        --crop 250,92,780,575 --width 130 --art-font-size 7

Then copy `profile.svg` + `README.md` into the profile repo and push.
`--out` ending in `.md` emits a code fence instead; `--format ansi` emits
escape codes (useful in a terminal, useless on GitHub).

## Getting a likeness out of line art

The reference profile works because its portrait is a **photograph**:
continuous tone maps naturally onto a density ramp. This source is line art —
~6% ink, ~84% paper, no gradients — so it needs different handling.

What actually mattered, in order:

1. **Resolution, not ramp tuning.** The art was capped near 58 columns purely
   out of code-fence habit, where one shared character size is forced. An SVG
   has no such constraint: `--art-font-size 7` against the panel's 14 fits
   ~130 columns in the same physical width. At that resolution the strokes are
   traceable and an ordinary gradient ramp just works. This was the fix.
2. **Sample at full resolution.** `sample_blocks` originally resized with
   LANCZOS *before* taking the percentile, averaging strokes away before the
   percentile could find them. Real bug, now fixed.
3. **Percentile over mean** (`--percentile 38`). A cell a thin stroke crosses
   still averages near-white; a lower percentile lets the darkest pixels win.

**Dead end, recorded so it is not retried:** near-binary ramps (`ink`/`ink3`/
`ink4`) and blur/thicken preprocessing. The binary ramps discard all tonal
nuance and produce a blobby silhouette that is clearly worse than a gradient
ramp at adequate resolution; blur turns the face to mush. The ramps and the
`--blur`/`--thicken` flags still exist, but neither is the answer here.

**Always judge at GitHub's real display width (~846px),** not at full size. A
card that looks fine at 100% can turn to grey noise once scaled down, and vice
versa — several rounds were wasted comparing downscaled 3-up contact sheets.

## Two bugs worth remembering

1. **`--clean` must key off glyph density, not luminance.** Under `--invert`
   the ramp is reversed, so filtering on raw luminance blanks the darkest
   *ink* instead of the background — the portrait's hair vanished.
2. **`xml:space="preserve"` does not reliably inherit from the `<svg>` root.**
   Space-padded single-line layout skewed the panel by up to 190px. Each row
   is now two `<text>` elements at explicit `x`, with `xml:space` and
   `white-space:pre` set on the elements themselves.

## Tuning the portrait

| Symptom | Fix |
| --- | --- |
| Background speckled with faint dots | raise `--clean` (9 worked here) |
| Inverted (dark where it should be light) | toggle `--invert` |
| Face missing, only hair renders | raise `--width` and lower `--art-font-size`; then `--percentile` 30-40 |
| Blobby, no detail | you are at too few columns — this is a resolution problem, not a ramp problem |
| Flat-grey regions read as noise | crop them out; a flat fill becomes a field of one character |
| Art floats in the middle of a tall panel | raise `--width` — art rows scale with it (`width x --aspect`) |
| Wrong framing | `--crop X1,Y1,X2,Y2` on the source pixels |
| Too tall | lower `--aspect` |

Source portrait is the line-art headshot from
`~/Documents/p/personal-site-2/public/images/kishore.png`. Line art converts
well: strong ink/paper separation, front-facing, no background clutter. The
actual GitHub avatar does not work at all — mean luminance 8.4/255, 97% of
pixels below 40, so it has no range to trace.

## Files

- `gen.py` — generator; `--help` for all flags
- `profile.json` — panel content
- `portrait.png` — source headshot
- `profile.svg` — generated card (the published artifact)
- `README.md` — one `<img>` tag pointing at profile.svg
