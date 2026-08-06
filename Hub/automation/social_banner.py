"""Daily Instagram Story/Reel banner generator.

Picks the next product in rotation and composes a 1080x1920 marketing
banner. Every banner is visually unique because (1) the composition itself
rotates through distinct layout structures - not just a recolored copy of
the same template, (2) the background is built from that product's own
photo, (3) the accent color theme rotates through a fixed palette, and
(4) decorative placement is seeded per-product. Pure Pillow — no external
services.
"""
from __future__ import annotations

import json
import math
import random
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

CANVAS_SIZE = (1080, 1920)
CARD_BOX = (90, 240, 990, 1140)  # left, top, right, bottom
GOLD = (255, 200, 40)
WHITE = (255, 255, 255)
MUTED = (176, 180, 196)

# Rotating color themes - picked deterministically per product so the same
# product always renders the same way, but consecutive banners differ.
THEMES = [
    {"name": "Coral Pulse", "accent": (255, 90, 54), "accent2": (255, 45, 133)},
    {"name": "Emerald Gold", "accent": (16, 185, 129), "accent2": (245, 200, 66)},
    {"name": "Electric Violet", "accent": (56, 132, 255), "accent2": (168, 85, 247)},
    {"name": "Sunset Blaze", "accent": (255, 61, 61), "accent2": (255, 159, 28)},
    {"name": "Teal Lime", "accent": (20, 184, 166), "accent2": (163, 230, 53)},
]

WATERMARK_WORDS = ["NEW", "HOT", "TRENDING", "MUST-HAVE", "VIRAL", "FEATURED"]

# Distinct compositions, not just recolors of one template - picked
# deterministically per product, same rule as THEMES.
LAYOUTS = ["card_stack", "full_bleed", "split_diagonal"]


def _first_existing(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


_WIN_FONTS = Path(r"C:\Windows\Fonts")
_LINUX_FONTS = Path("/usr/share/fonts/truetype/dejavu")

FONT_BOLD = _first_existing(_WIN_FONTS / "segoeuib.ttf", _LINUX_FONTS / "DejaVuSans-Bold.ttf")
FONT_BLACK = _first_existing(_WIN_FONTS / "arialbd.ttf", _LINUX_FONTS / "DejaVuSans-Bold.ttf")
FONT_REGULAR = _first_existing(_WIN_FONTS / "segoeui.ttf", _LINUX_FONTS / "DejaVuSans.ttf")

STATE_FILE = Path(__file__).resolve().parent.parent.parent / "media" / "social_banners" / ".rotation_state.json"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "media" / "social_banners"


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font_path: Path, max_width: int, start_size: int, min_size: int = 28) -> ImageFont.FreeTypeFont:
    size = start_size
    while size > min_size:
        font = _font(font_path, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return _font(font_path, min_size)


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 2) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) == max_lines - 1:
                break
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    consumed = " ".join(lines)
    if len(consumed) < len(text) and lines:
        last = lines[-1]
        while draw.textlength(last + "...", font=font) > max_width and len(last) > 1:
            last = last[:-1].rstrip()
        lines[-1] = last + "..." if last != lines[-1] else lines[-1]
    return lines


# ── Gradients & texture ─────────────────────────────────────────────────────

def _vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    base = Image.new("RGB", (1, h), color=0)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        base.putpixel((0, y), (r, g, b))
    return base.resize((w, h))


def _vertical_alpha_gradient(size: tuple[int, int], top_alpha: int, bottom_alpha: int, color: tuple[int, int, int] = (0, 0, 0)) -> Image.Image:
    w, h = size
    alpha_col = Image.new("L", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        alpha_col.putpixel((0, y), int(top_alpha + (bottom_alpha - top_alpha) * t))
    alpha = alpha_col.resize((w, h))
    solid = Image.new("RGBA", size, color + (0,))
    solid.putalpha(alpha)
    return solid


def _horizontal_gradient(size: tuple[int, int], left: tuple[int, int, int], right: tuple[int, int, int]) -> Image.Image:
    w, h = max(1, size[0]), max(1, size[1])
    base = Image.new("RGB", (w, 1), color=0)
    for x in range(w):
        t = x / max(1, w - 1)
        r = int(left[0] + (right[0] - left[0]) * t)
        g = int(left[1] + (right[1] - left[1]) * t)
        b = int(left[2] + (right[2] - left[2]) * t)
        base.putpixel((x, 0), (r, g, b))
    return base.resize((w, h))


def _photo_background(canvas_size: tuple[int, int], product_image_path: Path | None, theme: dict) -> Image.Image:
    """Blurred, darkened, tinted crop of the product's own photo - used as
    a backdrop behind a card, not as the hero image itself."""
    if product_image_path and product_image_path.exists():
        try:
            with Image.open(product_image_path) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                bg = ImageOps.fit(im, canvas_size, method=Image.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(52))
            bg = Image.blend(bg, Image.new("RGB", canvas_size, (0, 0, 0)), 0.60)
            tint_layer = Image.new("RGB", canvas_size, theme["accent2"])
            bg = Image.blend(bg, tint_layer, 0.20)
            return bg.convert("RGBA")
        except Exception:
            pass
    dark = tuple(max(0, c // 8) for c in theme["accent2"])
    return _vertical_gradient(canvas_size, (10, 12, 26), dark).convert("RGBA")


def _crisp_fit(size: tuple[int, int], product_image_path: Path | None, fallback_top: tuple[int, int, int], fallback_bottom: tuple[int, int, int]) -> Image.Image:
    """Sharp (unblurred) crop of the product photo filling `size` exactly -
    used when the photo itself is the hero, not a backdrop."""
    if product_image_path and product_image_path.exists():
        try:
            with Image.open(product_image_path) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                return ImageOps.fit(im, size, method=Image.LANCZOS).convert("RGBA")
        except Exception:
            pass
    return _vertical_gradient(size, fallback_top, fallback_bottom).convert("RGBA")


def _glow_blob(canvas_size: tuple[int, int], center: tuple[int, int], radius: int, color: tuple[int, int, int], peak_alpha: int = 130) -> Image.Image:
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color + (peak_alpha,))
    return layer.filter(ImageFilter.GaussianBlur(radius // 2))


def _dot_grid(canvas: Image.Image, spacing: int = 46, alpha: int = 12) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for y in range(0, canvas.size[1], spacing):
        for x in range(0, canvas.size[0], spacing):
            d.ellipse((x, y, x + 3, y + 3), fill=(255, 255, 255, alpha))
    canvas.alpha_composite(layer)


def _watermark_word(canvas: Image.Image, word: str, color: tuple[int, int, int], angle: float, center_y: int = 1320, alpha: int = 24) -> None:
    font = _font(FONT_BLACK, 240)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = d.textlength(word, font=font)
    cx, cy = canvas.size[0] / 2, center_y
    d.text((cx - w / 2, cy - 120), word, font=font, fill=color + (alpha,))
    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=False, center=(cx, cy))
    canvas.alpha_composite(layer)


def _gradient_text(canvas: Image.Image, xy: tuple[int, int], text: str, font: ImageFont.FreeTypeFont, color1: tuple[int, int, int], color2: tuple[int, int, int]) -> float:
    """Paint `text` filled with a horizontal gradient; returns rendered width."""
    probe = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(probe)
    pd.text(xy, text, font=font, fill=(255, 255, 255, 255))
    bbox = pd.textbbox(xy, text, font=font)
    x0, y0, x1, y1 = bbox
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    grad = _horizontal_gradient((w, h), color1, color2).convert("RGBA")
    mask = probe.crop((x0, y0, x0 + w, y0 + h)).split()[3]
    canvas.paste(grad, (x0, y0), mask)
    return x1 - xy[0]


# ── Stars & badges ───────────────────────────────────────────────────────────

def _star_points(center: tuple[float, float], outer_r: float, inner_r: float, n: int = 5, rotation: float = -90) -> list[tuple[float, float]]:
    cx, cy = center
    points = []
    step = 360 / (n * 2)
    for i in range(n * 2):
        angle = math.radians(rotation + i * step)
        r = outer_r if i % 2 == 0 else inner_r
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def _draw_star(draw: ImageDraw.ImageDraw, center: tuple[float, float], outer_r: float, inner_r: float, fill, n: int = 5, rotation: float = -90) -> None:
    draw.polygon(_star_points(center, outer_r, inner_r, n, rotation), fill=fill)


def _rating_row(canvas: Image.Image, xy: tuple[int, int], rating: float, size: int = 17) -> int:
    draw = ImageDraw.Draw(canvas)
    x, y = xy
    gap = size * 2 + 10
    filled = round(rating)
    for i in range(5):
        cx = x + i * gap + size
        cy = y + size
        fill = GOLD + (255,) if i < filled else (255, 255, 255, 90)
        _draw_star(draw, (cx, cy), size, size * 0.42, fill=fill)
    label_font = _font(FONT_REGULAR, 28)
    label = f"{rating:.1f}"
    draw.text((x + 5 * gap + 10, y + size - 16), label, font=label_font, fill=MUTED)
    return size * 2


def _discount_badge(canvas: Image.Image, center: tuple[int, int], percent: int, accent: tuple[int, int, int], accent2: tuple[int, int, int], rotation: float = -90) -> None:
    cx, cy = center
    r_outer, r_inner = 96, 70

    glow = _glow_blob(canvas.size, center, 130, accent2, peak_alpha=110)
    canvas.alpha_composite(glow)

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(layer)
    _draw_star(bd, center, r_outer, r_inner, fill=accent2 + (255,), n=14, rotation=rotation)
    bd.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), fill=accent + (255,))
    bd.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), outline=WHITE + (230,), width=3)

    font_big = _font(FONT_BLACK, 40)
    font_small = _font(FONT_BOLD, 20)
    pct_text = f"-{percent}%"
    w = bd.textlength(pct_text, font=font_big)
    bd.text((cx - w / 2, cy - 30), pct_text, font=font_big, fill=WHITE)
    off_text = "OFF"
    w2 = bd.textlength(off_text, font=font_small)
    bd.text((cx - w2 / 2, cy + 14), off_text, font=font_small, fill=WHITE)
    canvas.alpha_composite(layer)


def _sparkle(canvas: Image.Image, center: tuple[int, int], size: int, color=(255, 255, 255), alpha: int = 220) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    d.polygon([(cx, cy - size), (cx + size * 0.28, cy - size * 0.28), (cx + size, cy), (cx + size * 0.28, cy + size * 0.28), (cx, cy + size), (cx - size * 0.28, cy + size * 0.28), (cx - size, cy), (cx - size * 0.28, cy - size * 0.28)], fill=color + (alpha,))
    canvas.alpha_composite(layer)


# ── Card & product image ─────────────────────────────────────────────────────

def _card_with_halo(canvas: Image.Image, box: tuple[int, int, int, int], accent: tuple[int, int, int], accent2: tuple[int, int, int], radius: int = 36) -> None:
    left, top, right, bottom = box

    halo1 = _glow_blob(canvas.size, (left + 60, top + 40), 260, accent, peak_alpha=100)
    halo2 = _glow_blob(canvas.size, (right - 60, bottom - 60), 260, accent2, peak_alpha=100)
    canvas.alpha_composite(halo1)
    canvas.alpha_composite(halo2)

    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.rounded_rectangle((left, top + 18, right, bottom + 18), radius=radius, fill=(0, 0, 0, 150))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(26))
    canvas.alpha_composite(shadow_layer)

    card_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_layer)
    cd.rounded_rectangle(box, radius=radius, fill=(255, 255, 255, 255))
    canvas.alpha_composite(card_layer)


def _paste_product_image(canvas: Image.Image, product_image_path: Path, box: tuple[int, int, int, int], padding: int = 48) -> None:
    left, top, right, bottom = box
    inner = (left + padding, top + padding, right - padding, bottom - padding)
    inner_w, inner_h = inner[2] - inner[0], inner[3] - inner[1]

    with Image.open(product_image_path) as im:
        im = ImageOps.exif_transpose(im).convert("RGBA")
        fitted = ImageOps.contain(im, (inner_w, inner_h))
        px = inner[0] + (inner_w - fitted.width) // 2
        py = inner[1] + (inner_h - fitted.height) // 2
        canvas.alpha_composite(fitted, (px, py))


def _build_tilted_card(canvas_size: tuple[int, int], box: tuple[int, int, int, int], product_image_path: Path | None, accent: tuple[int, int, int], accent2: tuple[int, int, int], angle: float, rng: random.Random) -> tuple[Image.Image, tuple[int, int]]:
    """Compose the card (halo + shadow + card + photo + sparkles) on its own
    layer, then rotate it slightly as one unit for a hand-placed, dynamic feel."""
    left, top, right, bottom = box
    card_w, card_h = right - left, bottom - top
    margin = 220
    sub_size = (card_w + margin * 2, card_h + margin * 2)
    sub = Image.new("RGBA", sub_size, (0, 0, 0, 0))
    local_box = (margin, margin, margin + card_w, margin + card_h)

    _card_with_halo(sub, local_box, accent, accent2)
    if product_image_path and product_image_path.exists():
        _paste_product_image(sub, product_image_path, local_box)

    for _ in range(rng.randint(3, 5)):
        sx = local_box[0] + rng.randint(-40, card_w + 40)
        sy = local_box[1] + rng.randint(-40, 60)
        size = rng.randint(9, 22)
        color = WHITE if rng.random() > 0.4 else GOLD
        _sparkle(sub, (sx, sy), size, color, rng.randint(160, 235))

    rotated = sub.rotate(angle, resample=Image.BICUBIC, expand=True)
    cx, cy = (left + right) // 2, (top + bottom) // 2
    px, py = cx - rotated.width // 2, cy - rotated.height // 2
    return rotated, (px, py)


# ── Shared building blocks used by every layout ──────────────────────────────

def _compute_discount(product) -> int:
    discount = int(getattr(product, "discount_percent", 0) or 0)
    if discount <= 0 and getattr(product, "old_price", None):
        try:
            if product.old_price and product.price and product.old_price > product.price:
                discount = round(100 * (1 - float(product.price) / float(product.old_price)))
        except Exception:
            discount = 0
    return discount


def _top_bar(canvas: Image.Image, accent: tuple[int, int, int], accent2: tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.text((90, 74), "VIBEMALL", font=_font(FONT_BLACK, 42), fill=WHITE)
    tag = "TODAY'S PICK"
    tag_font = _font(FONT_BOLD, 24)
    tag_w = draw.textlength(tag, font=tag_font)
    pill_box = (990 - tag_w - 44, 76, 990, 122)
    grad_pill = _horizontal_gradient((int(tag_w + 44), 46), accent, accent2).convert("RGBA")
    mask = Image.new("L", grad_pill.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, grad_pill.size[0] - 1, grad_pill.size[1] - 1), radius=23, fill=255)
    canvas.paste(grad_pill, (int(pill_box[0]), int(pill_box[1])), mask)
    draw.text((pill_box[0] + 22, pill_box[1] + 11), tag, font=tag_font, fill=WHITE)


def _render_copy_block(canvas: Image.Image, product, accent: tuple[int, int, int], accent2: tuple[int, int, int], y: int, *, left_margin: int = 90, name_start_size: int = 64, name_shadow: bool = True, cta_text: str = "Shop Now") -> None:
    """Category eyebrow -> name -> price -> rating -> CTA -> footer. The one
    text sequence every layout shares, so composition differs but copy
    presentation stays consistent and legible."""
    draw = ImageDraw.Draw(canvas)
    text_width = 1080 - left_margin * 2

    category_label = (product.get_category_display() if product.category else "FEATURED").upper()
    cat_font = _font(FONT_BOLD, 26)
    draw.ellipse((left_margin, y + 8, left_margin + 10, y + 18), fill=accent)
    draw.text((left_margin + 22, y), category_label, font=cat_font, fill=accent)
    y += 48

    name_font = _fit_text(draw, product.name, FONT_BLACK, text_width, start_size=name_start_size, min_size=36)
    for line in _wrap_lines(draw, product.name, name_font, text_width, max_lines=2):
        if name_shadow:
            draw.text((left_margin + 2, y + 2), line, font=name_font, fill=(0, 0, 0, 120))
        draw.text((left_margin, y), line, font=name_font, fill=WHITE)
        y += name_font.size + 12
    y += 16

    price_font = _font(FONT_BLACK, 78)
    price_text = f"Rs {int(product.price):,}"
    price_w = _gradient_text(canvas, (left_margin, y), price_text, price_font, accent, accent2)
    draw = ImageDraw.Draw(canvas)

    if product.old_price and product.old_price > product.price:
        old_font = _font(FONT_REGULAR, 40)
        old_text = f"Rs {int(product.old_price):,}"
        ox = left_margin + price_w + 28
        oy = y + 26
        draw.text((ox, oy), old_text, font=old_font, fill=MUTED)
        ow = draw.textlength(old_text, font=old_font)
        draw.line((ox - 4, oy + 20, ox + ow + 4, oy + 20), fill=MUTED, width=3)
    y += 106

    rating = float(getattr(product, "rating", 0) or 0)
    if rating > 0:
        y += _rating_row(canvas, (left_margin, y), rating) + 22
        draw = ImageDraw.Draw(canvas)

    cta_text = f"{cta_text}  \u2192"
    cta_font = _font(FONT_BOLD, 34)
    cta_w = draw.textlength(cta_text, font=cta_font)
    pill_w, pill_h = int(cta_w + 84), 80
    glow = _glow_blob(canvas.size, (left_margin + pill_w // 2, y + pill_h // 2), 110, accent2, peak_alpha=110)
    canvas.alpha_composite(glow)
    grad_cta = _horizontal_gradient((pill_w, pill_h), accent, accent2).convert("RGBA")
    cta_mask = Image.new("L", (pill_w, pill_h), 0)
    ImageDraw.Draw(cta_mask).rounded_rectangle((0, 0, pill_w - 1, pill_h - 1), radius=40, fill=255)
    canvas.paste(grad_cta, (left_margin, int(y)), cta_mask)
    draw = ImageDraw.Draw(canvas)
    draw.text((left_margin + 42, y + 21), cta_text, font=cta_font, fill=WHITE)

    footer = "Link in bio"
    footer_font = _font(FONT_REGULAR, 26)
    fw = draw.textlength(footer, font=footer_font)
    draw.text(((1080 - fw) / 2, 1850), footer, font=footer_font, fill=MUTED)


# ── Layout 1: Card Stack ─────────────────────────────────────────────────────
# Blurred-photo backdrop, a tilted white product card floating on top, copy
# below. The original design - premium and safe.

def _layout_card_stack(product, theme: dict, image_path: Path | None, rng: random.Random, cta_text: str) -> Image.Image:
    accent, accent2 = theme["accent"], theme["accent2"]
    canvas = _photo_background(CANVAS_SIZE, image_path, theme)

    watermark = WATERMARK_WORDS[product.id % len(WATERMARK_WORDS)]
    _watermark_word(canvas, watermark, WHITE, angle=rng.choice([-9, -6, 6, 9]))

    canvas.alpha_composite(_glow_blob(CANVAS_SIZE, (140, 1750), 400, accent2, peak_alpha=45))
    canvas.alpha_composite(_glow_blob(CANVAS_SIZE, (960, 110), 360, accent, peak_alpha=45))
    _dot_grid(canvas)
    canvas.alpha_composite(_vertical_alpha_gradient(CANVAS_SIZE, 55, 235, (4, 5, 14)))

    _top_bar(canvas, accent, accent2)

    tilt_angle = rng.choice([-3.5, -2.5, 2.5, 3.5])
    tilted, pos = _build_tilted_card(CANVAS_SIZE, CARD_BOX, image_path, accent, accent2, tilt_angle, rng)
    canvas.paste(tilted, pos, tilted)

    discount = _compute_discount(product)
    if discount > 0:
        badge_rotation = rng.choice([-90, -75, -105])
        _discount_badge(canvas, (CARD_BOX[2] - 34, CARD_BOX[1] + 34), discount, accent, accent2, rotation=badge_rotation)

    _render_copy_block(canvas, product, accent, accent2, y=1188, cta_text=cta_text)
    return canvas


# ── Layout 2: Full Bleed ─────────────────────────────────────────────────────
# The product photo itself fills the entire canvas, crisp and unblurred -
# editorial/magazine-cover feel. Copy sits directly on the photo over a
# heavy bottom scrim for legibility.

def _layout_full_bleed(product, theme: dict, image_path: Path | None, rng: random.Random, cta_text: str) -> Image.Image:
    accent, accent2 = theme["accent"], theme["accent2"]
    canvas = _crisp_fit(CANVAS_SIZE, image_path, (20, 22, 40), tuple(max(0, c // 6) for c in accent2))

    # Top scrim so the brand bar stays legible over any photo, bottom scrim
    # (much heavier) for the copy block.
    canvas.alpha_composite(_vertical_alpha_gradient(CANVAS_SIZE, 130, 0, (0, 0, 0)))
    bottom_scrim_h = 950
    scrim = _vertical_alpha_gradient((CANVAS_SIZE[0], bottom_scrim_h), 0, 250, (4, 4, 12))
    canvas.alpha_composite(scrim, (0, CANVAS_SIZE[1] - bottom_scrim_h))

    _top_bar(canvas, accent, accent2)

    discount = _compute_discount(product)
    if discount > 0:
        _discount_badge(canvas, (990 - 106, 220), discount, accent, accent2, rotation=rng.choice([-90, -75, -105]))

    for _ in range(rng.randint(4, 6)):
        sx = rng.randint(60, 1020)
        sy = rng.randint(160, 900)
        size = rng.randint(8, 18)
        color = WHITE if rng.random() > 0.5 else GOLD
        _sparkle(canvas, (sx, sy), size, color, rng.randint(120, 200))

    _render_copy_block(canvas, product, accent, accent2, y=1230, name_start_size=72, name_shadow=True, cta_text=cta_text)
    return canvas


# ── Layout 3: Split Diagonal ─────────────────────────────────────────────────
# Photo panel on top with an angled bottom edge, solid theme-colored panel
# below holding the copy - modern, sport-brand energy.

def _layout_split_diagonal(product, theme: dict, image_path: Path | None, rng: random.Random, cta_text: str) -> Image.Image:
    accent, accent2 = theme["accent"], theme["accent2"]
    panel_dark = tuple(max(0, c // 10) for c in accent2)
    canvas = _vertical_gradient(CANVAS_SIZE, (8, 9, 18), panel_dark).convert("RGBA")

    photo_h = 1180
    slant = rng.choice([1, -1]) * 130
    panel = _crisp_fit((CANVAS_SIZE[0], photo_h), image_path, accent, accent2)

    mask = Image.new("L", (CANVAS_SIZE[0], photo_h), 0)
    md = ImageDraw.Draw(mask)
    if slant >= 0:
        pts = [(0, 0), (CANVAS_SIZE[0], 0), (CANVAS_SIZE[0], photo_h), (0, photo_h - slant)]
    else:
        pts = [(0, 0), (CANVAS_SIZE[0], 0), (CANVAS_SIZE[0], photo_h + slant), (0, photo_h)]
    md.polygon(pts, fill=255)
    canvas.paste(panel, (0, 0), mask)

    # Blend the photo panel's cut edge into the panel below with a short
    # dark fade, and darken its top slightly so the brand bar stays legible.
    edge_fade = _vertical_alpha_gradient((CANVAS_SIZE[0], 220), 0, 235, panel_dark)
    canvas.alpha_composite(edge_fade, (0, photo_h - 220))
    canvas.alpha_composite(_vertical_alpha_gradient((CANVAS_SIZE[0], 200), 120, 0, (0, 0, 0)))

    _top_bar(canvas, accent, accent2)

    discount = _compute_discount(product)
    if discount > 0:
        _discount_badge(canvas, (990 - 106, 220), discount, accent, accent2, rotation=rng.choice([-90, -75, -105]))

    text_y = photo_h - (abs(slant) // 2) + 40
    _render_copy_block(canvas, product, accent, accent2, y=text_y, name_start_size=58, cta_text=cta_text)
    return canvas


_LAYOUT_FUNCS = {
    "card_stack": _layout_card_stack,
    "full_bleed": _layout_full_bleed,
    "split_diagonal": _layout_split_diagonal,
}


# ── Main composition ─────────────────────────────────────────────────────────

def compose_banner(product, output_path: Path, cta_text: str = "Shop Now") -> Path:
    """Render one banner for `product` (a Hub.models.Product instance).

    `cta_text` should be the AI-written CTA from marketing_copy.generate_copy
    when available, so the button in the image matches the button implied
    by the caption - not a generic "Shop Now" regardless of context.
    """
    rng = random.Random(product.id)
    theme = THEMES[product.id % len(THEMES)]
    layout_name = LAYOUTS[product.id % len(LAYOUTS)]
    image_path = Path(product.image.path) if product.image else None

    layout_fn = _LAYOUT_FUNCS[layout_name]
    canvas = layout_fn(product, theme, image_path, rng, cta_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, "PNG", quality=95)
    return output_path


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def pick_next_product():
    """Rotate through all active, in-stock products in id order, never
    repeating until the whole catalog has been shown once."""
    from Hub.models import Product

    eligible_ids = list(
        Product.objects.filter(is_active=True, stock__gt=0)
        .exclude(image="")
        .order_by("id")
        .values_list("id", flat=True)
    )
    if not eligible_ids:
        return None

    state = _load_state()
    shown = set(state.get("shown_ids", []))
    remaining = [pid for pid in eligible_ids if pid not in shown]
    if not remaining:
        # Full cycle complete - start over.
        remaining = eligible_ids
        shown = set()

    next_id = remaining[0]
    shown.add(next_id)
    state["shown_ids"] = sorted(shown)
    state["last_product_id"] = next_id
    state["last_run_date"] = date.today().isoformat()
    _save_state(state)

    return Product.objects.get(id=next_id)


def generate_today_banner():
    """Generate today's banner, write its AI copy, log it in the Creative
    Library, and send it to Telegram for Approve/Reject/Regenerate.

    Returns the created CreativeAsset, or None if there is no eligible
    product.
    """
    from Hub.automation.creative_delivery import send_for_approval
    from Hub.automation.marketing_copy import generate_copy
    from Hub.models_creative import CreativeAsset

    product = pick_next_product()
    if product is None:
        return None

    # Copy first: the CTA text it writes (urgency-matched to the discount)
    # goes into the button on the banner image itself, not just the caption.
    copy = generate_copy(product)

    filename = f"{date.today().isoformat()}_{product.id}_{product.slug or product.id}.png"
    output_path = OUTPUT_DIR / filename
    compose_banner(product, output_path, cta_text=copy["cta"])

    theme_name = THEMES[product.id % len(THEMES)]["name"]
    layout_name = LAYOUTS[product.id % len(LAYOUTS)]

    asset = CreativeAsset.objects.create(
        product=product,
        image_path=f"social_banners/{filename}",
        theme_name=f"{theme_name} / {layout_name}",
        headline=copy["headline"],
        caption=copy["caption"],
        hashtags=",".join(copy["hashtags"]),
        cta_text=copy["cta"],
        ai_provider=copy.get("provider", ""),
    )
    send_for_approval(asset)
    return asset
