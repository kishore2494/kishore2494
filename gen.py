#!/usr/bin/env python3
"""
Build a neofetch-style GitHub profile README: ASCII-art portrait on the left,
key/value info panel on the right, both inside one fenced code block.

  python3 gen.py --image me.jpg --config profile.json --out README.md

Everything is tunable from the CLI; run with --help.
"""
import argparse, json, re, sys
from pathlib import Path

try:
    import numpy as np
    from PIL import (Image, ImageDraw, ImageEnhance, ImageFilter,
                       ImageFont, ImageOps)
except ImportError:
    sys.exit("Needs Pillow and numpy:  python3 -m pip install --user pillow numpy")

# Dark -> light. Reversed for light-background themes via --invert.
RAMPS = {
    "blocks":   " .:-=+*#%@",
    "detailed": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "dense":    " ░▒▓█",
    "andrew":   " .,;'`\"^:!><~+_-?)(|/\\tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@",
    # Near-binary traces, for line art: a gradient ramp spends most of its
    # range describing the solid hair while the thin facial strokes -- the
    # part that actually carries likeness -- get faint mid-density glyphs.
    "ink":      " @",
    "ink3":     " *@",
    "ink4":     " -*@",
}


# Wide, unhinted bold faces trace best into character cells; condensed ones
# (Impact, Arial Narrow) merge their stems at this resolution.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Tahoma Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def render_text_image(text, px_height=200, tracking=0.22):
    """Draw `text` as a bitmap, one glyph at a time so letters stay separated."""
    font = None
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                font = ImageFont.truetype(candidate, px_height)
                break
            except OSError:
                continue
    if font is None:
        sys.exit("No bold TrueType font found; pass --image instead of --text.")

    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    gap = int(px_height * tracking)
    glyphs, total_w = [], 0
    for ch in text:
        box = probe.textbbox((0, 0), ch, font=font)
        glyphs.append((ch, box))
        total_w += (box[2] - box[0]) + gap
    total_w -= gap

    # One shared baseline, so letters don't jitter vertically.
    full = probe.textbbox((0, 0), text, font=font)
    pad = px_height // 6
    img = Image.new("L", (total_w + 2 * pad, full[3] - full[1] + 2 * pad), 0)
    draw = ImageDraw.Draw(img)
    x = pad
    for ch, box in glyphs:
        draw.text((x - box[0], pad - full[1]), ch, fill=255, font=font)
        x += (box[2] - box[0]) + gap
    return img


def sample_blocks(img, cols, rows, percentile):
    """Downsample to a character grid by per-cell percentile, not by averaging.

    Averaging destroys line art: this portrait is only ~6% ink, so a cell a
    stroke passes through still averages near-white and reads as blank. Taking
    a low percentile lets the darkest pixels in a cell win, so a one-pixel
    eyebrow survives being squashed into a single character.

    Critically this runs on the FULL-RESOLUTION pixels. Resizing first (even
    to a multiple of the grid) averages the strokes away before the percentile
    can find them, which is exactly the bug that made the face render blank
    while the solid-black hair came through fine.
    """
    a = np.asarray(img, dtype=np.float32)
    h, w = a.shape
    bh, bw = -(-h // rows), -(-w // cols)      # ceil, so blocks cover the image
    a = np.pad(a, ((0, rows * bh - h), (0, cols * bw - w)), mode="edge")
    a = a.reshape(rows, bh, cols, bw)
    return np.percentile(a, percentile, axis=(1, 3)).reshape(-1).tolist()


def make_art(path, width, ramp, invert, contrast, gamma, aspect, crop_circle,
             threshold=0, clean=0, crop_box=None, percentile=50,
             blur=0.0, thicken=0):
    img = path if isinstance(path, Image.Image) else Image.open(path)
    is_text = isinstance(path, Image.Image)
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (0, 0, 0))
        img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1])
        img = bg
    img = img.convert("L")

    # Square-crop portraits so the face fills the frame; text is already framed.
    if not is_text:
        if crop_box:
            img = img.crop(crop_box)
        w, h = img.size
        side = min(w, h)
        img = img.crop(((w - side) // 2, (h - side) // 2,
                        (w - side) // 2 + side, (h - side) // 2 + side))
        # Line art has no tonal range at all -- just ink and paper -- so a density
    # ramp has nothing to describe and the thin strokes fall through the grid.
    # Thickening then blurring turns each stroke into a soft gradient the ramp
    # CAN represent, which is what gives a drawing a photographic ASCII look.
    if thicken > 1:
        img = img.filter(ImageFilter.MinFilter(thicken | 1))   # must be odd
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(blur))

    img = ImageOps.autocontrast(img, cutoff=2)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)

    # Characters are ~2x taller than wide, so squash the vertical resolution.
    if is_text:
        rows = max(1, int(width * img.height / img.width * aspect * 2))
    else:
        rows = max(1, int(width * img.height / img.width * aspect * 2))

    px = sample_blocks(img, width, rows, 50 if is_text else percentile)
    if is_text and threshold > 0:
        # A hard edge suits big letters; at small sizes the antialiased
        # gradient carries the counters (the holes in O, R, E) far better.
        px = [255 if v > threshold else 0 for v in px]
    if gamma != 1.0:
        px = [int(255 * ((p / 255) ** gamma)) for p in px]

    chars = ramp if not invert else ramp[::-1]
    n = len(chars) - 1
    cx, cy, r = (width - 1) / 2, (rows - 1) / 2, min(width, rows) / 2

    lines = []
    for y in range(rows):
        row = []
        for x in range(width):
            if crop_circle:
                dx = (x - cx) / max(cx, 1)
                dy = (y - cy) / max(cy, 1)
                if dx * dx + dy * dy > 1.0:
                    row.append(" ")
                    continue
            level = int(px[y * width + x] / 255 * n)
            # Noise in a plain background lands on the faintest ramp levels and
            # speckles the frame. Key this off how dense the CHOSEN glyph is --
            # under --invert the ramp is reversed, so raw luminance would blank
            # the darkest ink instead of the background.
            density = (n - level) if invert else level
            row.append(" " if density < clean else chars[level])
        lines.append("".join(row).rstrip())

    # Antialiasing leaves near-empty speckle rows at the top and bottom of
    # rendered text. Trim any edge row made only of the faintest ramp chars.
    faint = set(chars[:max(1, len(chars) // 6)]) | {" "}  # chars[0] = lightest
    while lines and set(lines[0]) <= faint:
        lines.pop(0)
    while lines and set(lines[-1]) <= faint:
        lines.pop()
    return lines


ESC = "\x1b"
ANSI = {"title": f"{ESC}[35m", "key": f"{ESC}[36m", "num": f"{ESC}[32m",
        "val": f"{ESC}[37m", "dim": f"{ESC}[90m", "art": "", "off": f"{ESC}[0m"}

# GitHub's dark palette, so the card looks identical in either site theme.
SVG_FILL = {"title": "#d2a8ff", "key": "#79c0ff", "num": "#7ee787",
            "val": "#c9d1d9", "dim": "#484f58", "art": "#8b949e"}


def _visible_len(text):
    """Length as rendered, ignoring ANSI escape sequences."""
    return len(re.sub(r"\x1b\[[0-9;]*m", "", text))


def make_panel(cfg, dot_width):
    """Build panel rows as lists of (role, text) segments.

    Segments rather than finished strings because the SVG renderer needs to
    colour the panel independently of the art -- and the two share a line, so
    no code-fence highlighter can ever do that.
    """
    widest = max((len(f"- {k}:") + len(str(v)) + 2
                  for sec in cfg.get("sections", [])
                  for k, v in sec.get("items", [])), default=0)
    if widest > dot_width:
        print(f"  note: widening panel to {widest} cols to fit longest value")
        dot_width = widest

    rows = [[("title", cfg.get("header", ""))]]
    for section in cfg.get("sections", []):
        title = section.get("title", "")
        if title:
            bar = "-" * max(3, dot_width - len(title) - 4)
            rows.append([("title", f"- {title} {bar}--")])
        for key, value in section.get("items", []):
            value = str(value)
            pad = max(1, dot_width - len(f"- {key}:") - len(value))
            role = "num" if re.fullmatch(r"[\d,.\s+%-]+", value) else "val"
            rows.append([("key", f"- {key}:"), ("dim", " " + "." * pad + " "),
                         (role, value)])
        rows.append([])
    while rows and not rows[-1]:
        rows.pop()
    return rows


def row_text(row):
    return "".join(t for _, t in row)


def compose(art, rows):
    """Interleave the art column and the panel rows, each vertically centred.

    Returns (lines, art_w). Art is padded to art_w but the inter-column gap is
    left to the renderers: the SVG one positions the panel at an explicit x
    rather than padding with spaces, which browsers are free to collapse.
    """
    art_w = max((len(l) for l in art), default=0)
    art_top = max(0, (len(rows) - len(art)) // 2)
    row_top = max(0, (len(art) - len(rows)) // 2)
    total = max(len(art) + art_top, len(rows) + row_top)
    out = []
    for i in range(total):
        a = art[i - art_top] if art_top <= i < art_top + len(art) else ""
        r = rows[i - row_top] if row_top <= i < row_top + len(rows) else []
        out.append((a.ljust(art_w), r))
    return out, art_w


def render_fence(lines, lang, gap):
    pad = " " * gap
    body = "\n".join((a + pad + row_text(r)).rstrip() for a, r in lines)
    return f"```{lang}\n{body}\n```\n"


def render_ansi(lines, gap):
    pad = " " * gap
    body = []
    for a, r in lines:
        seg = "".join(f"{ANSI[role]}{t}{ANSI['off']}" if ANSI[role] else t
                      for role, t in r)
        body.append((a + pad + seg).rstrip())
    return "```ansi\n" + "\n".join(body) + "\n```\n"


def xml_escape(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_svg(art, rows, gap, font_size=14, art_font_size=None, pad=20):
    """Emit the card as SVG -- the only way to colour art and panel apart.

    The art is laid out as its own block at its own (usually smaller) glyph
    size. That decoupling is the point: at the panel's 14px an art column that
    fits beside the text caps out around 58 characters, which is too coarse to
    resolve a face. At 7px the same physical width holds ~120 characters, and
    the likeness comes from that resolution, not from ramp tuning.

    Each row is a <text> at an explicit x. Space-padded layout is unreliable --
    browsers collapse runs of spaces unless xml:space is honoured on the
    element itself, which skewed the panel by up to 190px when the attribute
    sat on the root instead.
    """
    afs = art_font_size or font_size
    cw, lh = font_size * 0.60, font_size * 1.36
    acw, alh = afs * 0.60, afs * 1.36
    keep = 'xml:space="preserve" style="white-space:pre"'

    art_w = max((len(l) for l in art), default=0)
    art_px = art_w * acw
    panel_x = round(pad + art_px + gap * cw, 2)
    panel_cols = max((len(row_text(r)) for r in rows), default=0)
    w = round(panel_x + panel_cols * cw + pad)

    art_h, panel_h = len(art) * alh, len(rows) * lh
    h = round(max(art_h, panel_h) + 2 * pad)
    art_y0 = pad + max(0, (panel_h - art_h) / 2)      # centre the shorter block
    panel_y0 = pad + max(0, (art_h - panel_h) / 2)

    body = []
    for i, line in enumerate(art):
        if not line.strip():
            continue
        y = round(art_y0 + alh * (i + 0.85), 2)
        body.append(f'<text {keep} x="{pad}" y="{y}" font-size="{afs}" '
                    f'fill="{SVG_FILL["art"]}">{xml_escape(line.rstrip())}</text>')
    for i, row in enumerate(rows):
        if not row:
            continue
        y = round(panel_y0 + lh * (i + 0.85), 2)
        spans = "".join(f'<tspan fill="{SVG_FILL[r]}">{xml_escape(t)}</tspan>'
                        for r, t in row)
        body.append(f'<text {keep} x="{panel_x}" y="{y}">{spans}</text>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"
     viewBox="0 0 {w} {h}"
     font-family="SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace"
     font-size="{font_size}">
  <rect width="{w}" height="{h}" rx="8" fill="#0d1117"/>
{chr(10).join("  " + b for b in body)}
</svg>
"""


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", help="portrait to convert (jpg/png)")
    src.add_argument("--text", help="render this word as the left column instead")
    p.add_argument("--config", required=True, help="JSON file with the info panel")
    p.add_argument("--out", default="profile.svg",
                   help="output path; extension picks the format unless --format")
    p.add_argument("--format", choices=["svg", "md", "ansi"],
                   help="svg = full colour control (recommended); md = code fence")
    p.add_argument("--width", type=int, default=42, help="art width in characters")
    p.add_argument("--ramp", default="andrew", choices=sorted(RAMPS))
    p.add_argument("--invert", action="store_true",
                   help="dense chars for DARK pixels (dark ink on a light backdrop)")
    p.add_argument("--contrast", type=float, default=1.4)
    p.add_argument("--gamma", type=float, default=1.0)
    p.add_argument("--aspect", type=float, default=0.52,
                   help="rows per column; lower = shorter art")
    p.add_argument("--thicken", type=int, default=0, metavar="N",
                   help="dilate dark strokes by an N-pixel min filter before "
                        "sampling; use on line art so features survive")
    p.add_argument("--blur", type=float, default=0.0, metavar="R",
                   help="Gaussian blur radius (source pixels) before sampling; "
                        "gives line art the tonal range a density ramp needs")
    p.add_argument("--percentile", type=float, default=50, metavar="P",
                   help="per-cell sampling percentile; LOW (10-25) preserves "
                        "thin strokes in line art, 50 = plain averaging")
    p.add_argument("--clean", type=int, default=0, metavar="N",
                   help="blank the N faintest ramp levels (kills background speckle)")
    p.add_argument("--crop", metavar="X1,Y1,X2,Y2",
                   help="crop the source to this pixel box before converting")
    p.add_argument("--circle", action="store_true", help="mask the art to a circle")
    p.add_argument("--text-threshold", type=int, default=0, metavar="N",
                   help="--text only: binarize at N (0 = keep antialiasing)")
    p.add_argument("--tracking", type=float, default=0.22,
                   help="letter spacing for --text, as a fraction of glyph height")
    p.add_argument("--gap", type=int, default=4, help="columns between art and panel")
    p.add_argument("--dot-width", type=int, default=44,
                   help="panel width used for the dot leaders")
    p.add_argument("--lang", default="yaml", help="--format md: code-fence language")
    p.add_argument("--font-size", type=int, default=14, help="--format svg only")
    p.add_argument("--art-font-size", type=int, default=None, metavar="N",
                   help="--format svg: glyph size for the art column alone "
                        "(smaller = more characters = more detail)")
    args = p.parse_args()

    fmt = args.format or ("md" if args.out.endswith(".md") else
                          "ansi" if args.out.endswith(".ansi") else "svg")

    cfg = json.loads(Path(args.config).read_text())
    source = (render_text_image(args.text, tracking=args.tracking)
              if args.text else args.image)
    art = make_art(source, args.width, RAMPS[args.ramp], args.invert,
                   args.contrast, args.gamma, args.aspect,
                   args.circle and not args.text, args.text_threshold,
                   args.clean,
                   tuple(int(v) for v in args.crop.split(",")) if args.crop else None,
                   args.percentile, args.blur, args.thicken)
    rows = make_panel(cfg, args.dot_width)
    lines, art_w = compose(art, rows)

    out = {"svg": lambda: render_svg(art, rows, args.gap, args.font_size,
                                     args.art_font_size),
           "md": lambda: render_fence(lines, args.lang, args.gap),
           "ansi": lambda: render_ansi(lines, args.gap)}[fmt]()
    Path(args.out).write_text(out)

    cols = max((len(a) + args.gap + len(row_text(r)) for a, r in lines), default=0)
    print(f"wrote {args.out}  [{fmt}] {len(lines)} lines, {cols} cols, "
          f"art {max((len(l) for l in art), default=0)}x{len(art)}")
    if fmt != "svg" and cols > 100:
        print("  note: >100 cols may wrap; lower --width or --dot-width")


if __name__ == "__main__":
    main()
