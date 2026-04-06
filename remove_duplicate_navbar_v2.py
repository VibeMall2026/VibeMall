#!/usr/bin/env python
"""
Find and remove duplicate desktop view section
"""

file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the second "<!-- DESKTOP VIEW -->" section
import re

# Count occurrences of "<!-- DESKTOP VIEW -->"
pattern = r'<!-- DESKTOP VIEW -->'
matches = list(re.finditer(pattern, content))

print(f"Found {len(matches)} instances of '<!-- DESKTOP VIEW -->'")

if len(matches) >= 2:
    second_pos = matches[1].start()
    print(f"Second instance at position: {second_pos}")
    
    # Find where it ends by looking for the next "<!-- ========== SHARED SCRIPTS ==========" 
    # but skip the first occurrence
    script_pattern = r'<!-- ========== SHARED SCRIPTS ==========['
    script_matches = list(re.finditer(script_pattern, content))
    
    if len(script_matches) >= 2:
        # Find the one after second_pos
        for match in script_matches:
            if match.start() > second_pos:
                end_pos = match.start()
                print(f"Duplicate section ends at: {end_pos}")
                
                # Remove the duplicate section
                new_content = content[:second_pos] + content[end_pos:]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print("✓ Removed duplicate desktop section")
                break
    else:
        print("Could not find end marker")
else:
    print("Could not find second desktop view section")
