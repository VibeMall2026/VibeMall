#!/usr/bin/env python
import re

file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Count all headers
matches = list(re.finditer(r'<header class="vm-copy-rp-header">', content))
print(f"Total desktop headers: {len(matches)}")

# Also check for "section" tags to understand structure
section_matches = list(re.finditer(r'<section class="vm-copy-rp-desktop">', content))
print(f"Desktop sections: {len(section_matches)}")

# Find their positions
for i, m in enumerate(matches):
    line_num = content[:m.start()].count('\n') + 1
    print(f"  Header {i+1} at line {line_num}")

if len(matches) > 1:
    print("\n⚠ Found multiple headers - might need to remove one")
elif len(matches) == 1:
    print("\n✓ Only one desktop header found (good)")
