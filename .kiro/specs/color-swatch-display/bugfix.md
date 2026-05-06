# Bugfix Requirements Document

## Introduction

Across multiple order-related pages (order details, order tracking, cart, checkout, and order confirmation), product color is displayed as plain text only (e.g., "ORANGE", "RED", "Navy Blue"). Users cannot visually identify the color at a glance because no color swatch or dot indicator is shown alongside the color name. This fix adds a small inline colored dot/circle (10–12px) next to the color name text in all affected templates, mapping common color name strings to their corresponding CSS color values.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a product has a color attribute (e.g., "ORANGE") and it is rendered in order details, order tracking, cart, checkout, or order confirmation templates THEN the system displays the color as plain text only, with no visual indicator of the actual color.

1.2 WHEN the color name is a multi-word value (e.g., "Navy Blue", "Hot Pink") THEN the system displays the full text string with no color swatch, making it indistinguishable from any other text attribute like size.

1.3 WHEN the color name uses mixed casing (e.g., "Pink", "ORANGE", "red") THEN the system displays the raw stored string with no normalization or visual representation.

### Expected Behavior (Correct)

2.1 WHEN a product has a color attribute and it is rendered in any order-related template THEN the system SHALL display a small filled circle (10–12px) in the corresponding CSS color alongside the color name text.

2.2 WHEN the color name is a multi-word value (e.g., "Navy Blue", "Hot Pink") THEN the system SHALL map it to the appropriate CSS color value and display the colored dot correctly next to the full color name.

2.3 WHEN the color name uses any casing (e.g., "Pink", "ORANGE", "red") THEN the system SHALL perform a case-insensitive lookup to resolve the CSS color and render the swatch correctly.

2.4 WHEN the color name does not match any known color in the mapping THEN the system SHALL display the color name text without a swatch dot (graceful fallback, no broken UI).

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a product has no color attribute THEN the system SHALL CONTINUE TO omit the color field from display without errors or empty swatch elements.

3.2 WHEN a product has both color and size attributes THEN the system SHALL CONTINUE TO display both attributes together in the same format (e.g., "ORANGE • FREE SIZE"), with only the color gaining the swatch dot.

3.3 WHEN the color swatch is rendered THEN the system SHALL CONTINUE TO display the color name text alongside the dot so the color is still readable as text.

3.4 WHEN order details, cart totals, pricing, and quantity information are displayed THEN the system SHALL CONTINUE TO render all existing data correctly and without layout breakage.

3.5 WHEN the templates are rendered on mobile viewports THEN the system SHALL CONTINUE TO display the color swatch inline without causing layout overflow or wrapping issues.
