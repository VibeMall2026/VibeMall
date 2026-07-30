"""
Image understanding
===================

Sends staged images to Claude and gets back, per image: its role (main /
gallery / description), the colourway it shows, and alt text.

This is what removes manual sorting. Suppliers post a mixed pile — three shots
of the red piece, two of the blue, a size chart, a fabric close-up — and the
result here is what lets the publisher build correct per-colour variants.

Cost control: images are downscaled before upload and the batch is capped.
Beyond ~14 images the marginal classification value drops well below the token
cost, so the remainder is classified heuristically instead.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

from django.conf import settings

from .client import AIUnavailable
from .prompts import VISION_SYSTEM
from .schema import build_image_schema

logger = logging.getLogger(__name__)

#: Long-edge pixels for vision uploads. Well under the providers' resolution
#: ceilings — catalogue classification does not need full resolution, and this
#: keeps per-image token cost roughly 4x lower.
VISION_MAX_EDGE = int(getattr(settings, 'AUTOMATION_VISION_MAX_EDGE', 768))

#: Maximum images sent in one vision request. Gemini's free tier caps
#: *input tokens per minute*, and images are the expensive part — a large batch
#: can exhaust the window in a single call, so the default is deliberately
#: modest. Raise it on a paid key.
VISION_MAX_IMAGES = int(getattr(settings, 'AUTOMATION_VISION_MAX_IMAGES', 8))


def _encode(path_or_file: Any) -> tuple[str, str] | None:
    """Downscale and base64-encode an image. Returns ``(media_type, data)``."""
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is a hard project dependency
        logger.error('[vision] Pillow is not available; cannot analyse images.')
        return None

    try:
        with Image.open(path_or_file) as img:
            img = img.convert('RGB')
            img.thumbnail((VISION_MAX_EDGE, VISION_MAX_EDGE), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=80, optimize=True)
        return 'image/jpeg', base64.standard_b64encode(buffer.getvalue()).decode('ascii')
    except Exception as exc:
        logger.warning('[vision] Could not encode image: %s', exc)
        return None


def analyse_images(client: Any, images: list[Any], *, context: str = '') -> dict[str, Any]:
    """
    Classify staged images.

    ``images`` is a list of ``ProductDraftImage``. Returns the parsed vision
    payload; on any failure returns an empty dict so the caller can fall back
    to heuristics rather than failing the draft.
    """
    if not images:
        return {}

    batch = images[:VISION_MAX_IMAGES]
    content: list[dict[str, Any]] = []
    encoded_count = 0

    for index, draft_image in enumerate(batch):
        try:
            encoded = _encode(draft_image.image.path)
        except (ValueError, OSError) as exc:
            logger.warning('[vision] Image %s unreadable: %s', draft_image.pk, exc)
            encoded = None

        if not encoded:
            continue

        media_type, data = encoded
        content.append({'type': 'text', 'text': f'Image index {index}:'})
        content.append(
            {
                'type': 'image',
                'source': {'type': 'base64', 'media_type': media_type, 'data': data},
            }
        )
        encoded_count += 1

    if not encoded_count:
        return {}

    instruction = (
        f'Classify these {encoded_count} product images. '
        'Return exactly one entry per image, using the index labels shown above.'
    )
    if context.strip():
        instruction += f'\n\nSupplier text for context:\n```\n{context.strip()[:2000]}\n```'
    content.append({'type': 'text', 'text': instruction})

    try:
        result = client.complete_json(
            system=VISION_SYSTEM,
            content=content,
            schema=build_image_schema(),
        )
    except AIUnavailable as exc:
        logger.warning('[vision] Analysis unavailable: %s', exc)
        return {}
    except Exception:
        logger.exception('[vision] Unexpected failure during image analysis')
        return {}

    result['_analysed_count'] = encoded_count
    result['_total_count'] = len(images)
    return result


def apply_to_images(images: list[Any], findings: dict[str, Any]) -> None:
    """
    Write vision results back onto the staged image rows.

    Images beyond the analysed batch, and every image if vision was
    unavailable, fall back to a positional heuristic: first image is the hero,
    the rest are gallery. That is the same assumption the manual Add Product
    flow makes, so the draft stays usable either way.
    """
    from Hub.models import ProductDraftImage

    entries = {int(item.get('index', -1)): item for item in (findings.get('images') or [])}
    colorways = findings.get('detected_colorways') or []
    main_assigned = False

    for index, draft_image in enumerate(images):
        entry = entries.get(index)

        if entry:
            role = entry.get('role') or ProductDraftImage.ROLE_GALLERY
            # Guard against the model marking several images as the hero.
            if role == ProductDraftImage.ROLE_MAIN:
                if main_assigned:
                    role = ProductDraftImage.ROLE_GALLERY
                else:
                    main_assigned = True

            draft_image.role = role
            draft_image.color = (entry.get('color') or '').strip()[:100]
            draft_image.alt_text = (entry.get('alt_text') or '').strip()[:255]
            draft_image.analysis = entry
        else:
            draft_image.role = ProductDraftImage.ROLE_GALLERY
            if not draft_image.color and len(colorways) == 1:
                draft_image.color = str(colorways[0])[:100]

        draft_image.order = index
        draft_image.save(update_fields=['role', 'color', 'alt_text', 'analysis', 'order'])

    # Nothing was nominated as the hero — promote the first usable photo.
    if not main_assigned:
        for draft_image in images:
            if draft_image.role != ProductDraftImage.ROLE_DESCRIPTION:
                draft_image.role = ProductDraftImage.ROLE_MAIN
                draft_image.save(update_fields=['role'])
                break
