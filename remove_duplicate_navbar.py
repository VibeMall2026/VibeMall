#!/usr/bin/env python
"""
Remove the duplicate desktop view section that starts at line ~1178
Keep only the first one
"""

file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with "<!-- DESKTOP VIEW -->"
desktop_view_count = 0
duplicate_start = None

for i, line in enumerate(lines):
    if '<!-- DESKTOP VIEW -->' in line and '<section class="vm-copy-page vm-copy-rp-desktop">' in lines[i+1]:
        duplicate_start = i
        break

if duplicate_start is not None:
    # Find the closing </section> tag for this duplicate section
    section_count = 1
    duplicate_end = None
    
    for i in range(duplicate_start + 2, len(lines)):
        if '<!-- ========== SHARED SCRIPTS ==========' in lines[i]:
            duplicate_end = i
            break
    
    if duplicate_end:
        # Remove from duplicate_start to duplicate_end
        new_lines = lines[:duplicate_start] + lines[duplicate_end:]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"✓ Removed duplicate desktop section (lines {duplicate_start+1}-{duplicate_end})")
        print("✓ Kept only the first desktop view")
    else:
        print("Could not find end of duplicate section")
else:
    print("No duplicate desktop section found")
