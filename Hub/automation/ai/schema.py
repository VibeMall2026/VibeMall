"""
Extraction schema
=================

The JSON schema Claude's output is constrained to. It is the contract between
the AI layer and everything downstream — ``ProductDraft.parsed`` always has
this shape, so the publisher and the approval template never have to
defensively probe for keys.

Schema rules for Anthropic structured outputs: every object needs
``additionalProperties: false`` and a complete ``required`` list; length and
numeric constraints are not supported and are enforced in Python instead.

Unknown values are the empty string / empty list rather than ``null`` — Django
``CharField``s reject ``None``, and a uniform "empty means unknown" convention
keeps the merge logic simple.
"""

from __future__ import annotations

from typing import Any

#: Attributes with no column on ``Product``. They are preserved verbatim in
#: ``ProductDraft.parsed``, rendered on the approval screen, and folded into
#: ``care_info`` / ``tags`` / the specification block on publish.
EXTENDED_ATTRIBUTE_FIELDS = [
    'product_type',
    'fabric',
    'material',
    'top_fabric',
    'bottom_fabric',
    'dupatta_fabric',
    'inner_fabric',
    'sleeve_type',
    'neck_type',
    'pattern',
    'occasion',
    'style',
    'fit',
    'work_type',
    'stitch_type',
    'length',
    'wash_care',
    'package_contents',
    'country_of_origin',
]


def _str(description: str) -> dict[str, Any]:
    return {'type': 'string', 'description': description}


def _str_array(description: str) -> dict[str, Any]:
    return {'type': 'array', 'items': {'type': 'string'}, 'description': description}


def build_extraction_schema(category_keys: list[str]) -> dict[str, Any]:
    """
    Build the extraction schema.

    ``category_keys`` comes from ``Product.CATEGORY_CHOICES`` at call time, so
    adding a category in the admin automatically widens what the AI may
    suggest — no code change here.
    """
    properties: dict[str, Any] = {
        # --- Identity ------------------------------------------------------
        'name': _str('Concise, professional product title (6-12 words). Never include price or emoji.'),
        'short_description': _str('One-sentence summary, max ~160 characters, for listing cards.'),
        'description': _str(
            'Full product description, 90-160 words, in natural marketing prose. '
            'Must be unique to this product and must not invent facts.'
        ),
        'highlights': _str_array('4-6 short bullet points of key selling features.'),
        'brand': _str('Brand name if stated, otherwise empty string.'),
        'sku': _str('Supplier style/design code if present, otherwise empty string.'),

        # --- Commercials ---------------------------------------------------
        'price': _str('Selling price as a plain number string, e.g. "799". Empty if unknown.'),
        'old_price': _str('Original/MRP price as a plain number string. Empty if unknown.'),
        'stock': _str('Stock quantity as a plain number string. Empty if not stated.'),

        # --- Variants ------------------------------------------------------
        'sizes': _str_array('Available sizes, normalised (S, M, L, XL, XXL, Free Size, or numeric).'),
        'colors': _str_array('Available colours, title-cased. One entry per distinct colourway.'),

        # --- Physical ------------------------------------------------------
        'weight': _str('Shipping weight with unit, e.g. "450 g". Empty if unknown.'),
        'dimensions': _str('Product dimensions if stated. Empty if unknown.'),

        # --- SEO -----------------------------------------------------------
        'meta_title': _str('SEO title, max 60 characters.'),
        'meta_description': _str('SEO meta description, max 160 characters.'),
        'meta_keywords': _str_array('6-12 SEO keywords a shopper would actually search for.'),
        'tags': _str_array('4-10 short catalogue tags.'),

        # --- Category suggestion -------------------------------------------
        'suggested_category': {
            'type': 'string',
            'enum': category_keys + [''],
            'description': 'Best-matching main category key, or empty string if genuinely unclear.',
        },
        'suggested_sub_category': _str('Suggested sub-category label, e.g. "Kurti", "Saree".'),
        'category_confidence': {
            'type': 'string',
            'enum': ['high', 'medium', 'low'],
            'description': 'Confidence in the category suggestion.',
        },
        'category_reasoning': _str('One sentence explaining the category choice.'),

        # --- Data quality --------------------------------------------------
        'inferred_fields': _str_array(
            'Names of fields you generated rather than read from the supplier message.'
        ),
        'warnings': _str_array('Anything the admin should check before approving.'),
    }

    # Extended attributes: no Product column, preserved as structured data.
    for field in EXTENDED_ATTRIBUTE_FIELDS:
        properties[field] = _str(
            f'{field.replace("_", " ").title()} if stated or confidently inferable, otherwise empty string.'
        )

    return {
        'type': 'object',
        'properties': properties,
        'required': list(properties.keys()),
        'additionalProperties': False,
    }


def build_image_schema() -> dict[str, Any]:
    """Schema for the vision pass that classifies each staged image."""
    return {
        'type': 'object',
        'properties': {
            'images': {
                'type': 'array',
                'description': 'One entry per supplied image, in the same order.',
                'items': {
                    'type': 'object',
                    'properties': {
                        'index': {'type': 'integer', 'description': 'Zero-based index of the image.'},
                        'role': {
                            'type': 'string',
                            'enum': ['main', 'gallery', 'description'],
                            'description': (
                                'main = best hero shot of the product; '
                                'description = a text/size-chart/infographic image; '
                                'gallery = everything else.'
                            ),
                        },
                        'color': _str(
                            'Dominant garment colour, title-cased (e.g. "Navy Blue"). '
                            'Empty string if the product has no distinct colourway.'
                        ),
                        'alt_text': _str('Descriptive alt text, max ~120 characters, SEO-friendly.'),
                        'is_text_heavy': {
                            'type': 'boolean',
                            'description': 'True if the image is mostly text rather than product photography.',
                        },
                        'quality': {
                            'type': 'string',
                            'enum': ['good', 'acceptable', 'poor'],
                            'description': 'Suitability as a catalogue image.',
                        },
                    },
                    'required': ['index', 'role', 'color', 'alt_text', 'is_text_heavy', 'quality'],
                    'additionalProperties': False,
                },
            },
            'detected_colorways': _str_array('Distinct colourways visible across all images.'),
            'product_type_guess': _str('What the product appears to be, from the images alone.'),
        },
        'required': ['images', 'detected_colorways', 'product_type_guess'],
        'additionalProperties': False,
    }
