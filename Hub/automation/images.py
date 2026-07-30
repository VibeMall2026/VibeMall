"""
Image pipeline
==============

Runs over a draft's staged images before they are shown for approval:

1. **Perceptual hashing** — a 64-bit difference hash per image.
2. **Near-duplicate removal** — suppliers routinely repost the same photo
   across an album; identical or near-identical images are dropped.
3. **Compression** — oversized supplier photos are re-encoded so the media
   directory does not balloon. The existing ``Product`` / ``ProductImage``
   ``save()`` hooks still apply their own 4:5 framing and compression on
   publish, so this is about staging cost, not final presentation.
4. **SEO renaming** — files are renamed to
   ``<product-slug>-<colour>-<role>-<n>.jpg``.

The hash is also reused by :mod:`Hub.automation.duplicates` to spot a product
that has already been listed from a different message.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.text import slugify

logger = logging.getLogger(__name__)

#: Hamming distance below which two images count as the same photo.
DUPLICATE_HAMMING_THRESHOLD = 6

#: Staged images are re-encoded above this long edge.
STAGE_MAX_EDGE = 1600
STAGE_JPEG_QUALITY = 85


def _pillow():
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is a project dependency
        return None
    return Image


def difference_hash(path_or_file: Any, size: int = 8) -> str:
    """
    64-bit dHash as a hex string.

    Compares each pixel to its right-hand neighbour on a 9x8 greyscale
    thumbnail. Robust to rescaling and re-compression — which is exactly how
    the same product photo differs between two supplier posts — while staying
    dependency-free (no imagehash/numpy needed).
    """
    Image = _pillow()
    if Image is None:
        return ''

    try:
        with Image.open(path_or_file) as img:
            img = img.convert('L').resize((size + 1, size), Image.LANCZOS)
            pixels = list(img.getdata())
    except Exception as exc:
        logger.warning('[images] Could not hash image: %s', exc)
        return ''

    bits = 0
    position = 0
    for row in range(size):
        offset = row * (size + 1)
        for col in range(size):
            if pixels[offset + col] > pixels[offset + col + 1]:
                bits |= 1 << position
            position += 1

    return f'{bits:016x}'


def hamming(a: str, b: str) -> int:
    """Bit distance between two hex hashes. Returns 64 (max) if either is missing."""
    if not a or not b or len(a) != len(b):
        return 64
    try:
        return bin(int(a, 16) ^ int(b, 16)).count('1')
    except ValueError:
        return 64


# --------------------------------------------------------------------------
# Supplier code strip detection
# --------------------------------------------------------------------------

#: A row counts as "background" when at least this fraction of its pixels match
#: the bottom-corner colour.
FOOTER_ROW_BACKGROUND_RATIO = 0.80

#: How close a pixel must be to the background colour, per channel.
FOOTER_COLOUR_TOLERANCE = 20

#: Never suggest trimming more than this fraction of the image height.
FOOTER_MAX_FRACTION = 0.22

#: Ignore strips thinner than this fraction — not worth a crop.
FOOTER_MIN_FRACTION = 0.015


def detect_footer_band(path_or_file: Any) -> int:
    """
    Height in pixels of the plain strip at the bottom of an image.

    Wholesale suppliers print a catalogue code ("s-558186268") on a solid band
    beneath the product shot. Detection walks up from the bottom edge counting
    rows that are overwhelmingly the background colour — small dark text still
    leaves a row ~95% background, whereas the first row containing the garment
    drops well below the threshold and stops the scan.

    Returns 0 when no meaningful strip is found.
    """
    Image = _pillow()
    if Image is None:
        return 0

    try:
        with Image.open(path_or_file) as img:
            img = img.convert('RGB')
            width, height = img.size
            if height < 50:
                return 0

            # Narrow the image so each row is cheap to scan; height is kept
            # exact because the result is measured in source pixels.
            sample_width = min(width, 120)
            if sample_width != width:
                img = img.resize((sample_width, height), Image.NEAREST)
            pixels = img.load()

        background = pixels[0, height - 1]
        tolerance = FOOTER_COLOUR_TOLERANCE

        def is_background(pixel) -> bool:
            return all(abs(a - b) <= tolerance for a, b in zip(pixel, background))

        limit = int(height * FOOTER_MAX_FRACTION)
        band = 0
        for y in range(height - 1, height - 1 - limit, -1):
            matches = sum(1 for x in range(sample_width) if is_background(pixels[x, y]))
            if matches / sample_width < FOOTER_ROW_BACKGROUND_RATIO:
                break
            band += 1
    except Exception as exc:
        logger.warning('[images] Footer detection failed: %s', exc)
        return 0

    if band < height * FOOTER_MIN_FRACTION:
        return 0
    return band


def cropped_bytes(path: str, crop_bottom_px: int) -> bytes | None:
    """Re-encode an image with ``crop_bottom_px`` trimmed off the bottom."""
    Image = _pillow()
    if Image is None or crop_bottom_px <= 0:
        return None

    try:
        import io

        with Image.open(path) as img:
            img = img.convert('RGB')
            width, height = img.size
            keep = height - int(crop_bottom_px)
            # Refuse to crop away the whole photo.
            if keep < height * 0.4:
                logger.warning(
                    '[images] Ignoring crop of %dpx on a %dpx-tall image (too aggressive).',
                    crop_bottom_px, height,
                )
                return None
            cropped = img.crop((0, 0, width, keep))

            buffer = io.BytesIO()
            cropped.save(buffer, format='JPEG', quality=STAGE_JPEG_QUALITY, optimize=True)
            return buffer.getvalue()
    except Exception as exc:
        logger.warning('[images] Could not crop %s: %s', path, exc)
        return None


def _compress(draft_image: Any, filename: str) -> bool:
    """Re-encode a staged image in place. Returns True if it was rewritten."""
    Image = _pillow()
    if Image is None:
        return False

    try:
        import io

        with Image.open(draft_image.image.path) as img:
            needs_resize = max(img.size) > STAGE_MAX_EDGE
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            if needs_resize:
                img.thumbnail((STAGE_MAX_EDGE, STAGE_MAX_EDGE), Image.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=STAGE_JPEG_QUALITY, optimize=True)
            payload = buffer.getvalue()
    except Exception as exc:
        logger.warning('[images] Could not compress image %s: %s', draft_image.pk, exc)
        return False

    old_path = draft_image.image.path
    draft_image.image.save(filename, ContentFile(payload), save=False)

    # Remove the original only once the replacement is safely written.
    if old_path != draft_image.image.path and os.path.isfile(old_path):
        try:
            os.remove(old_path)
        except OSError:
            pass
    return True


def _seo_filename(slug: str, draft_image: Any, index: int) -> str:
    parts = [slug or 'product']
    if draft_image.color:
        parts.append(slugify(draft_image.color))
    parts.append(draft_image.role)
    parts.append(str(index))
    return '-'.join(p for p in parts if p)[:120] + '.jpg'


def process_draft_images(draft: Any, *, slug: str) -> dict[str, int]:
    """
    Hash, de-duplicate, compress and rename every staged image on a draft.

    Returns a small stats dict for the audit log. Ordering is preserved, with
    the main image forced to position zero so the approval screen and the
    published gallery agree.
    """
    images = list(draft.images.all().order_by('order', 'id'))
    stats = {'total': len(images), 'duplicates_removed': 0, 'compressed': 0}
    if not images:
        return stats

    kept: list[Any] = []

    for draft_image in images:
        try:
            image_path = draft_image.image.path
        except (ValueError, OSError):
            logger.warning('[images] Draft image %s has no file; discarding.', draft_image.pk)
            draft_image.delete()
            continue

        if not os.path.isfile(image_path):
            draft_image.delete()
            continue

        draft_image.phash = difference_hash(image_path)

        # Near-duplicate of something we already kept?
        if draft_image.phash:
            twin = next(
                (
                    existing
                    for existing in kept
                    if hamming(existing.phash, draft_image.phash) <= DUPLICATE_HAMMING_THRESHOLD
                ),
                None,
            )
            if twin is not None:
                # Keep whichever carries the richer role/colour information.
                if not twin.color and draft_image.color:
                    twin.color = draft_image.color
                    twin.save(update_fields=['color'])
                draft_image.image.delete(save=False)
                draft_image.delete()
                stats['duplicates_removed'] += 1
                continue

        kept.append(draft_image)

    # Hero first, description images last, gallery in between.
    role_rank = {'main': 0, 'gallery': 1, 'description': 2}
    kept.sort(key=lambda i: (role_rank.get(i.role, 1), i.order, i.pk))

    stats['footer_detected'] = 0

    for index, draft_image in enumerate(kept):
        draft_image.order = index
        if _compress(draft_image, _seo_filename(slug, draft_image, index + 1)):
            stats['compressed'] += 1

        # Detect the supplier code strip *after* compression, since that step
        # may resize the file and the crop is stored in final-image pixels.
        # Size charts and infographics are legitimately text on a plain
        # background, so they are exempt.
        suggested = 0
        if draft_image.role != 'description':
            try:
                suggested = detect_footer_band(draft_image.image.path)
            except (ValueError, OSError):
                suggested = 0

        draft_image.suggested_crop_bottom_px = suggested
        if suggested:
            stats['footer_detected'] += 1
            # Pre-apply so the common case needs no clicks; the review screen
            # exposes it as an editable value the admin can zero out.
            draft_image.crop_bottom_px = suggested

        if not draft_image.alt_text:
            label = f'{draft_image.color} ' if draft_image.color else ''
            draft_image.alt_text = f'{label}{slug.replace("-", " ")}'.strip()[:255]

        draft_image.save(
            update_fields=[
                'order', 'image', 'phash', 'alt_text',
                'crop_bottom_px', 'suggested_crop_bottom_px',
            ]
        )

    stats['kept'] = len(kept)
    return stats

