#!/usr/bin/env python
"""
Remove the second/duplicate desktop view section that starts around line 1178
"""

file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with "<!-- DESKTOP VIEW -->" followed by 'vm-copy-page'
duplicate_start = None
for i, line in enumerate(lines):
    if '<!-- DESKTOP VIEW -->' in line and i+1 < len(lines) and 'vm-copy-page vm-copy-rp-desktop' in lines[i+1]:
        duplicate_start = i
        print(f"Found duplicate section at line {i+1}")
        break

if duplicate_start is not None:
    # Find the closing section tag - look for the next "<!-- ========== SHARED SCRIPTS =========="
    section_count = 0
    duplicate_end = None
    
    for i in range(duplicate_start, len(lines)):
        if '<!-- ========== SHARED SCRIPTS ==========' in lines[i]:
            duplicate_end = i
            print(f"Found end marker at line {i+1}")
            break
    
    if duplicate_end:
        # Keep everything before the duplicate and everything from the shared scripts marker onwards
        new_lines = lines[:duplicate_start] + lines[duplicate_end:]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"✓ Removed duplicate desktop section ({duplicate_end - duplicate_start} lines)")
        print("✓ Kept only the first desktop view")
    else:
        print("Could not find end of duplicate section")
else:
    print("No duplicate desktop section found")

# Verify
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()
    import re
    matches = list(re.finditer(r'<header class="vm-copy-rp-header">', content))
    print(f"\nResult: {len(matches)} headers remaining")
