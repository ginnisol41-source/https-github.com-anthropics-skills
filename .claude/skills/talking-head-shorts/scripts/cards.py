"""Generate the overlay cards (PNG with alpha) used by the talking-head shorts style.

Every card is drawn at 2x and downsampled for smooth edges. All cards share the
same visual language: rounded corners, soft drop shadow, macOS-style title bar.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SS = 2  # supersampling factor
CARD_W = 980


@lru_cache(maxsize=None)
def font_path(pattern: str) -> str:
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True, check=True)
        if out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return "DejaVuSans.ttf"


def F(pattern: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path(pattern), size * SS)


SANS_B = "Inter:bold"
SANS_SB = "Inter:semibold"
SANS = "Inter:medium"
MONO = "monospace"


def _finish(img: Image.Image, radius: int, shadow: bool = True) -> Image.Image:
    """Round the card corners, add a drop shadow, downsample."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius * SS, fill=255)
    img.putalpha(mask)
    pad = 24 * SS if shadow else 0
    canvas = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 6 * SS, pad + w, pad + h + 6 * SS), radius * SS, fill=(0, 0, 0, 110))
        canvas = Image.alpha_composite(canvas, sh.filter(ImageFilter.GaussianBlur(12 * SS)))
    canvas.alpha_composite(img, (pad, pad))
    return canvas.resize((canvas.width // SS, canvas.height // SS), Image.LANCZOS)


def _titlebar(d: ImageDraw.ImageDraw, w: int, title: str, dark: bool, badge: str | None = None, badge_color=None, icon=None):
    bh = 44 * SS
    d.rectangle((0, 0, w, bh), fill=(42, 42, 44) if dark else (246, 246, 246))
    for i, c in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx = (22 + i * 22) * SS
        d.ellipse((cx - 7 * SS, bh // 2 - 7 * SS, cx + 7 * SS, bh // 2 + 7 * SS), fill=c)
    f = F(SANS_SB if not dark else SANS, 22)
    x = 96 * SS
    if dark:
        tw = d.textlength(title, font=f)
        d.text(((w - tw) / 2, bh / 2), title, font=f, fill=(200, 200, 200), anchor="lm")
    else:
        if icon:
            d.rounded_rectangle((x, bh / 2 - 11 * SS, x + 22 * SS, bh / 2 + 11 * SS), 5 * SS, fill=icon)
            x += 32 * SS
        d.text((x, bh / 2), title, font=f, fill=(30, 30, 30), anchor="lm")
    if badge:
        fb = F(SANS_SB, 20)
        bw = d.textlength(badge, font=fb) + 22 * SS
        bx = w - bw - 14 * SS
        fill = badge_color or ((20, 20, 20) if not dark else (70, 70, 70))
        d.rounded_rectangle((bx, bh / 2 - 15 * SS, bx + bw, bh / 2 + 15 * SS), 6 * SS, fill=fill)
        d.text((bx + bw / 2, bh / 2), badge, font=fb, fill=(255, 255, 255), anchor="mm")
    return bh


# --------------------------------------------------------------------------- cards

def comment_card(user: str, text: str, width: int = 860) -> Image.Image:
    """The 'reply to comment' bubble used as the hook in the first seconds."""
    w = width * SS
    fu, ft = F(SANS_SB, 24), F(SANS, 32)
    h = 112 * SS
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    r = 26 * SS
    cx, cy = 50 * SS, h // 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(205, 160, 110))
    initial = (user.lstrip("@")[:1] or "?").upper()
    d.text((cx, cy), initial, font=F(SANS_B, 26), fill=(255, 255, 255), anchor="mm")
    d.text((92 * SS, 36 * SS), user, font=fu, fill=(110, 110, 110), anchor="lm")
    d.text((92 * SS, 76 * SS), text, font=ft, fill=(15, 15, 15), anchor="lm")
    return _finish(img, 22)


def title_card(text: str, width: int = 760, accent=(232, 120, 80)) -> Image.Image:
    """Dark terminal-like title: orange '>' prompt, uppercase mono text, block cursor, mini waveform."""
    w = width * SS
    f = F(MONO, 52)
    words, lines, cur = text.upper().split(), [], ""
    maxw = w - 120 * SS
    for wd in words:
        t = (cur + " " + wd).strip()
        if ImageDraw.Draw(Image.new("L", (1, 1))).textlength("> " + t, font=f) > maxw and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = t
    lines.append(cur)
    lh = 64 * SS
    h = 40 * SS + lh * len(lines) + 90 * SS
    img = Image.new("RGBA", (w, h), (22, 22, 24, 255))
    d = ImageDraw.Draw(img)
    y = 30 * SS
    for i, ln in enumerate(lines):
        x = 30 * SS
        if i == 0:
            d.text((x, y), ">", font=f, fill=accent)
        x += d.textlength("> ", font=f)
        d.text((x, y), ln, font=f, fill=(240, 240, 240))
        if i == len(lines) - 1:
            ex = x + d.textlength(ln, font=f) + 8 * SS
            d.rectangle((ex, y + 6 * SS, ex + 26 * SS, y + 58 * SS), fill=accent)
        y += lh
    rng = np.random.default_rng(7)
    n = 110
    amps = np.abs(rng.normal(0.25, 0.25, n)) * np.linspace(1, 0.3, n)
    base = h - 26 * SS
    bw = (w - 60 * SS) / n
    for i, a in enumerate(amps):
        bh = max(2 * SS, min(1.0, a) * 46 * SS)
        x0 = 30 * SS + i * bw
        d.rectangle((x0, base - bh, x0 + bw * 0.55, base), fill=(235, 235, 235))
    return _finish(img, 16)


def terminal_card(lines: list[str], title: str = "claude — ~/video", width: int = CARD_W, min_lines: int = 0) -> Image.Image:
    """Claude Code style terminal.

    Line syntax:  "* text" green bullet (header) | "[ ] text" todo | "[x] text" done (struck)
                  "> text" prompt line (drawn in an input box) | "$ text" tool call | anything else plain.
    """
    w = width * SS
    f, fb = F(MONO, 26), F(MONO + ":bold", 28)
    lh = 40 * SS
    n = max(len(lines), min_lines)
    bar = 44 * SS
    h = bar + 24 * SS + lh * n + 24 * SS
    img = Image.new("RGBA", (w, h), (22, 22, 24, 255))
    d = ImageDraw.Draw(img)
    _titlebar(d, w, title, dark=True)
    y = bar + 24 * SS
    for ln in lines:
        x = 26 * SS
        if ln.startswith("* "):
            d.ellipse((x, y + 14 * SS, x + 12 * SS, y + 26 * SS), fill=(72, 200, 110))
            d.text((x + 26 * SS, y + 20 * SS), ln[2:], font=fb, fill=(245, 245, 245), anchor="lm")
        elif ln.startswith("[ ] ") or ln.startswith("[x] "):
            done = ln[1] == "x"
            bx = x + 50 * SS
            d.rectangle((bx, y + 10 * SS, bx + 18 * SS, y + 28 * SS), outline=(200, 200, 200), width=2 * SS)
            if done:
                d.line((bx + 3 * SS, y + 19 * SS, bx + 8 * SS, y + 25 * SS, bx + 16 * SS, y + 12 * SS), fill=(240, 240, 240), width=3 * SS)
            tx = bx + 32 * SS
            col = (130, 130, 130) if done else (225, 225, 225)
            d.text((tx, y + 20 * SS), ln[4:], font=f, fill=col, anchor="lm")
            if done:
                tw = d.textlength(ln[4:], font=f)
                d.line((tx, y + 20 * SS, tx + tw, y + 20 * SS), fill=col, width=2 * SS)
        elif ln.startswith("> "):
            d.rounded_rectangle((x - 8 * SS, y - 2 * SS, w - 20 * SS, y + lh - 2 * SS), 8 * SS, outline=(90, 90, 92), width=2 * SS)
            d.text((x + 8 * SS, y + 18 * SS), "> " + ln[2:], font=f, fill=(225, 225, 225), anchor="lm")
        elif ln.startswith("$ "):
            d.ellipse((x, y + 14 * SS, x + 12 * SS, y + 26 * SS), fill=(240, 240, 240))
            d.text((x + 26 * SS, y + 20 * SS), ln[2:], font=f, fill=(225, 225, 225), anchor="lm")
        else:
            d.text((x + 26 * SS, y + 20 * SS), ln, font=f, fill=(170, 170, 170), anchor="lm")
        y += lh
    return _finish(img, 14)


def audio_envelope(path: str, start: float, end: float, n: int) -> np.ndarray:
    """Peak envelope (0..1) of an audio range, n buckets."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start}", "-to", f"{end}", "-i", path, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    a = np.abs(np.frombuffer(raw, dtype=np.int16).astype(np.float32)) / 32768.0
    if a.size == 0:
        return np.zeros(n)
    chunks = np.array_split(a, n)
    env = np.array([c.max() if c.size else 0 for c in chunks])
    return np.clip(env / max(env.max(), 1e-3), 0, 1)


def waveform_card(env: np.ndarray, title: str = "audio.wav", width: int = CARD_W, height: int = 210,
                  badge: str | None = None, badge_color=None, icon=None,
                  regions: list[dict] | None = None, playhead: float | None = None,
                  bottom_labels: list[dict] | None = None) -> Image.Image:
    """White waveform panel.

    regions: [{"from":0.2,"to":0.35,"label":"silenzio"}] in 0..1 card fractions, drawn as light-blue bands with a tag.
    bottom_labels: [{"at":0.1,"text":"DO"}] syllable-style labels under the waveform.
    playhead: 0..1 position of a dashed blue line.
    """
    w, h = width * SS, height * SS
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    bar = _titlebar(d, w, title, dark=False, badge=badge, badge_color=badge_color, icon=icon)
    top = bar + (46 if regions and any(r.get("label") for r in regions) else 16) * SS
    bottom = h - (46 if bottom_labels else 16) * SS
    x0, x1 = 18 * SS, w - 18 * SS
    for r in regions or []:
        a, b = x0 + r["from"] * (x1 - x0), x0 + r["to"] * (x1 - x0)
        d.rectangle((a, top - 6 * SS, b, bottom), fill=(222, 233, 250))
        if r.get("label"):
            fl = F(SANS_SB, 20)
            tw = d.textlength(r["label"], font=fl) + 16 * SS
            cx = (a + b) / 2
            d.rounded_rectangle((cx - tw / 2, bar + 8 * SS, cx + tw / 2, bar + 38 * SS), 5 * SS, fill=(255, 255, 255), outline=(20, 20, 20), width=2 * SS)
            d.text((cx, bar + 23 * SS), r["label"], font=fl, fill=(20, 20, 20), anchor="mm")
            d.line((cx, bar + 38 * SS, cx, top), fill=(20, 20, 20), width=2 * SS)
    n = len(env)
    bw = (x1 - x0) / n
    for i, a in enumerate(env):
        bh = max(2 * SS, a * (bottom - top))
        xa = x0 + i * bw
        d.rectangle((xa, bottom - bh, xa + bw * 0.6, bottom), fill=(25, 25, 25))
    d.line((x0, bottom, x1, bottom), fill=(170, 170, 170), width=1 * SS)
    if playhead is not None:
        px = x0 + playhead * (x1 - x0)
        for yy in range(int(top - 6 * SS), int(bottom), 10 * SS):
            d.line((px, yy, px, yy + 5 * SS), fill=(40, 100, 230), width=3 * SS)
    for lb in bottom_labels or []:
        fl = F(SANS_B, 26)
        d.text((x0 + lb["at"] * (x1 - x0), bottom + 24 * SS), lb["text"], font=fl, fill=tuple(lb.get("color", (20, 20, 20))), anchor="mm")
    return _finish(img, 12)


def label_chip(text: str, dark: bool = False) -> Image.Image:
    """Small callout chip, e.g. 'API: Claude usa Auphonic senza aprire il sito'."""
    f = F(SANS_SB, 26)
    tw = ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f)
    w, h = int(tw + 36 * SS), 48 * SS
    img = Image.new("RGBA", (w, h), (35, 95, 225, 255) if not dark else (20, 20, 20, 255))
    ImageDraw.Draw(img).text((w / 2, h / 2), text, font=f, fill=(255, 255, 255), anchor="mm")
    return _finish(img, 8, shadow=False)


def image_card(path: str, width: int = CARD_W) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    ratio = width * SS / im.width
    im = im.resize((width * SS, int(im.height * ratio)), Image.LANCZOS)
    return _finish(im, 14)


def circle_mask(size: int, ring: int = 6) -> Image.Image:
    """Grayscale mask for the circular face cam (white = visible)."""
    m = Image.new("L", (size * SS, size * SS), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size * SS - 1, size * SS - 1), fill=255)
    return m.resize((size, size), Image.LANCZOS)


def circle_ring(size: int, ring: int = 6) -> Image.Image:
    img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((0, 0, size * SS - 1, size * SS - 1), outline=(255, 255, 255, 255), width=ring * SS)
    return img.resize((size, size), Image.LANCZOS)


# --------------------------------------------------------------------------- "stack" / "pip" layouts

def window_bar(width: int, title: str = "LIVE", live: bool = True, height: int = 44) -> Image.Image:
    """macOS-style title bar placed above a live face feed or a screen capture."""
    w, h = width * SS, height * SS
    img = Image.new("RGBA", (w, h), (34, 34, 38, 255))
    d = ImageDraw.Draw(img)
    for i, c in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx = (22 + i * 22) * SS
        d.ellipse((cx - 7 * SS, h // 2 - 7 * SS, cx + 7 * SS, h // 2 + 7 * SS), fill=c)
    f = F(SANS_SB, 22)
    tw = d.textlength(title, font=f)
    x = (w - tw) / 2
    if live:
        d.ellipse((x - 22 * SS, h / 2 - 6 * SS, x - 10 * SS, h / 2 + 6 * SS), fill=(240, 50, 60))
    d.text((x, h / 2), title, font=f, fill=(235, 235, 235), anchor="lm")
    return img.resize((width, height), Image.LANCZOS)


def dark_background(w: int = 1080, h: int = 1920) -> Image.Image:
    """Deep navy gradient with a soft glow behind the centre (where the big icon sits)."""
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(-1, 1, w)[None, :]
    top, bot = np.array([16, 20, 32]), np.array([8, 10, 16])
    base = top[None, None, :] * (1 - y[..., None]) + bot[None, None, :] * y[..., None]
    glow = np.exp(-((x ** 2) / 0.5 + ((y - 0.55) ** 2) / 0.05))[..., None] * np.array([22, 28, 48])
    arr = np.clip(base + glow, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def app_icon(spec: dict, size: int = 290) -> Image.Image:
    """Rounded-square app icon. spec: {"image": path} for the real logo, or {"label": "Grok", "bg": [r,g,b], "fg": [r,g,b]}."""
    s = size * SS
    r = int(s * 0.23)
    bg = tuple(spec.get("bg", (22, 22, 24)))
    img = Image.new("RGBA", (s, s), bg + (255,))
    if spec.get("image"):
        logo = Image.open(spec["image"]).convert("RGBA")
        if spec.get("full_bleed"):
            logo = logo.resize((s, s), Image.LANCZOS)
            img.alpha_composite(logo)
        else:
            inner = int(s * spec.get("scale", 0.62))
            logo.thumbnail((inner, inner), Image.LANCZOS)
            img.alpha_composite(logo, ((s - logo.width) // 2, (s - logo.height) // 2))
    else:
        label = spec.get("short") or spec.get("label", "?")[:1].upper()
        d = ImageDraw.Draw(img)
        fs = int(size * (0.5 if len(label) <= 2 else 0.26))
        fnt = F("DejaVu Sans:bold", fs) if any(ord(ch) > 0x2000 for ch in label) else F(SANS_B, fs)
        d.text((s / 2, s / 2), label, font=fnt, fill=tuple(spec.get("fg", (255, 255, 255))), anchor="mm")
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), r, fill=255)
    img.putalpha(mask)
    # subtle border like iOS icons on dark backgrounds
    ImageDraw.Draw(img).rounded_rectangle((0, 0, s - 1, s - 1), r, outline=(255, 255, 255, 40), width=2 * SS)
    pad = 30 * SS
    out = Image.new("RGBA", (s + 2 * pad, s + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 10 * SS, pad + s, pad + s + 10 * SS), r, fill=(0, 0, 0, 150))
    out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(14 * SS)))
    out.alpha_composite(img, (pad, pad))
    return out.resize((out.width // SS, out.height // SS), Image.LANCZOS)


def icon_tray(specs: list[dict], icon: int = 96, gap: int = 14) -> Image.Image:
    """Dock-like pill that collects the icons already mentioned."""
    n = len(specs)
    pad = 14
    w = n * icon + (n - 1) * gap + 2 * pad
    h = icon + 2 * pad
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), 20 * SS, fill=(40, 42, 50, 235), outline=(255, 255, 255, 60), width=2 * SS)
    img = img.resize((w, h), Image.LANCZOS)
    for i, sp in enumerate(specs):
        ic = app_icon(sp, icon)
        p = (ic.width - icon) // 2
        ic = ic.crop((p, p, p + icon, p + icon))
        img.alpha_composite(ic, (pad + i * (icon + gap), pad))
    return img
