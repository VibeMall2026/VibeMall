"""
VibeMall Product Automation
===========================

Turns an unstructured supplier message into a fully-populated draft product
that an admin only has to categorise and approve.

Pipeline::

    source (Telegram / WhatsApp / CSV / API)
        -> ingest        create or extend a ProductDraft
        -> parsing       rule-based pre-pass (prices, sizes, fabrics)
        -> ai            Claude extraction + copywriting + image vision
        -> images        dedupe, compress, SEO-rename, role/colour assignment
        -> duplicates    guard against re-listing the same product
        -> [admin picks Category + Sub Category, clicks Approve]
        -> publisher     atomic write to Product / ProductImage /
                         ProductVariant / ProductSEO

Only ``publisher`` touches the live catalogue, and only on approval.
"""
