#!/usr/bin/env python
import json

# Read views.py to find the last line
with open(r"Hub\views.py", 'r', encoding='utf-8') as f:
    lines = f.readlines()
    print(f"Total lines in views.py: {len(lines)}")
    # Print last 20 lines to see what's at the end
    print("\nLast 20 lines:")
    for i, line in enumerate(lines[-20:], start=len(lines)-19):
        print(f"{i}: {line.rstrip()}")
