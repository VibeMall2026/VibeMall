# Bugfix Requirements Document

## Introduction

When an admin uses the Add/Edit Photo page to save images to a folder, the system is expected to automatically create the category and sub-category folder structure on disk (e.g., `ProductImage/Home & Kitchen/Jewellery/1/`) if it does not already exist. Currently, the folder creation only happens for the deepest `product_folder` level (e.g., `1/`) when the "Create folder if missing" checkbox is checked, but the parent category and sub-category directories are NOT being created when they are new/missing. This means that if a category folder like `WomenWear` or a sub-category folder like `Watch` does not yet exist on disk, `os.makedirs` will still succeed (since it creates all intermediate directories), but the `build_folder_index` and `build_shop_folder_dropdown` functions only read folders that already exist on disk — so newly entered category/sub-category names that have no matching folder on disk are not resolved to a `folder_category` or `folder_subcategory` value. As a result, the hidden form fields `main_category` and `sub_category` end up empty, the validation check fails, and no folder is created at all.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the admin enters a category name (e.g., "WomenWear") that does not yet exist as a folder under `PRODUCT_IMAGE_ROOT` and submits the Save to Folder form THEN the system does NOT create the category folder on disk.

1.2 WHEN the admin enters a sub-category name (e.g., "Watch") under a new or existing category that has no matching sub-folder on disk and submits the Save to Folder form THEN the system does NOT create the sub-category folder on disk.

1.3 WHEN the admin selects a category/sub-category from the shop taxonomy dropdown whose `folder_category` or `folder_subcategory` is empty (because no matching folder exists on disk yet) THEN the hidden `main_category` and `sub_category` form fields are set to empty strings, causing the validation to fail with "Please select Main category, Sub_Category, and Product_folder."

1.4 WHEN the admin types a new category or sub-category name in the custom text inputs and submits the form THEN the system does NOT use those typed values to construct the target folder path, so no folder is created.

### Expected Behavior (Correct)

2.1 WHEN the admin enters or selects a category name and sub-category name and checks "Create folder if missing" and submits the Save to Folder form THEN the system SHALL create the full folder path `PRODUCT_IMAGE_ROOT/<category>/<sub_category>/<product_folder>/` including all missing intermediate directories.

2.2 WHEN the admin types a new category name in the custom category input (not present in the existing folder index) and submits the form THEN the system SHALL use that typed value as the folder segment and create the corresponding directory structure on disk.

2.3 WHEN the admin selects a shop taxonomy category/sub-category whose folder mapping is empty (no existing folder on disk) THEN the system SHALL fall back to using the category label and sub-category label directly as folder segment names to construct and create the target path.

2.4 WHEN the folder creation succeeds for a new category or sub-category THEN the system SHALL also register the category and sub-category in the database via `_ensure_category_and_subcategory` so the new folders appear in the shop taxonomy on subsequent page loads.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the admin selects a category and sub-category that already exist as folders on disk THEN the system SHALL CONTINUE TO resolve the correct `folder_category` and `folder_subcategory` values and save images to the existing folder path without errors.

3.2 WHEN the "Create folder if missing" checkbox is unchecked and the target folder does not exist THEN the system SHALL CONTINUE TO show the error "Target folder does not exist. Enable create folder."

3.3 WHEN the admin provides an invalid or non-numeric product folder number THEN the system SHALL CONTINUE TO show the validation error "Product_folder must be a number like 1, 2, 3."

3.4 WHEN images are successfully saved to a folder THEN the system SHALL CONTINUE TO redirect to the Add Product page with the session data pre-populated with the saved category, sub-category, and folder details.

3.5 WHEN the admin uses the web detection feature to auto-detect category from a product URL THEN the system SHALL CONTINUE TO populate the category and sub-category dropdowns with the detected values.
