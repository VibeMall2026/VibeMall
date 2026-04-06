#!/usr/bin/env python
"""
Remove the duplicate desktop section from the HTML
"""

file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find line 1178 (the duplicate "<!-- DESKTOP VIEW -->")
# and remove from there until we hit the first <script> tag
duplicate_start = None
duplicate_end = None

for i, line in enumerate(lines):
    # Find the line with the second "<!-- DESKTOP VIEW -->"
    if i > 600 and '<!-- DESKTOP VIEW -->' in line:
        duplicate_start = i
        print(f"Found duplicate desktop section start at line {i+1}")
        break

if duplicate_start:
    # Find where this section ends (where the closing </section> is before the shared script)
    for i in range(duplicate_start, len(lines)):
        if '</section>' in lines[i] and '<script>' not in lines[i]:
            # Check if the next non-empty line is a script tag
            for j in range(i+1, min(i+5, len(lines))):
                if lines[j].strip():
                    if '<script>' in lines[j]:
                        duplicate_end = i + 1  # Include the closing </section>
                        print(f"Found duplicate desktop section end at line {duplicate_end}")
                    break
            if duplicate_end:
                break

if duplicate_start and duplicate_end:
    # Remove the duplicate section
    new_lines = lines[:duplicate_start] + lines[duplicate_end:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"✓ Removed {duplicate_end - duplicate_start} lines of duplicate desktop section")
    
    # Verify
    import re
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    matches = list(re.finditer(r'<header class="vm-copy-rp-header">', content))
    print(f"✓ Now has {len(matches)} desktop headers")
else:
    print("Could not find duplicate section boundaries")
