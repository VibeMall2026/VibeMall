# Task #17 - `views.py` Refactor (Safe Modular Extraction)

## What was refactored

A safe, non-breaking modular extraction was performed to reduce `Hub/views.py` complexity while preserving all existing routes, templates, and logic.

### New module
- Added `Hub/view_helpers.py`

### Extracted helper functions from `Hub/views.py`
- `_split_full_name`
- `_get_checkout_items`
- `_get_checkout_total_quantity`
- `_get_checkout_item_product_and_qty`
- `_get_resell_link_matching_quantity`
- `_get_checkout_min_unit_price`
- `_verify_upi_with_razorpay`
- `_validate_indian_pincode`
- `_lookup_ifsc_details`

### `Hub/views.py` updates
- Imported helpers from `Hub/view_helpers.py`
- Removed duplicated in-file helper implementations
- Kept existing view function names, URL mappings, and response behavior unchanged
- Preserved UPI debug logging by passing `logger` into helper calls:
  - `validate_upi_id`
  - checkout-related UPI validation blocks

## Why this is safe

- No URL changes
- No template changes
- No schema/model changes
- No business logic changes
- Function call signatures in views remain consistent for runtime behavior

## Validation

- Static file diagnostics checked via VS Code problems tool:
  - `Hub/views.py`: no errors
  - `Hub/view_helpers.py`: no errors

## Benefit

- Reduces helper clutter in `Hub/views.py`
- Improves readability and maintainability
- Provides a clear path for further modular extraction in later tasks
