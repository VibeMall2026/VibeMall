#!/usr/bin/env python
"""Setup Graphify for VibeMall codebase."""

import json
import sys
from pathlib import Path
from graphify.detect import detect
from graphify.extract import collect_files, extract

# Create output directory
output_dir = Path('graphify-out')
output_dir.mkdir(exist_ok=True)

print("\n" + "="*60)
print("GRAPHIFY SETUP FOR VIBEMALL")
print("="*60)

# Step 2: Detect files
print("\n[STEP 2] Detecting files in corpus...")
result = detect(Path('.'))
Path('graphify-out/.graphify_detect.json').write_text(json.dumps(result, indent=2))

total = result.get('total_files', 0)
words = result.get('total_words', 0)

print(f"\n✓ Corpus Summary:")
print(f"  Total files: {total}")
print(f"  Total words: ~{words:,}")

print(f"\n✓ File Types Detected:")
for ftype, files in result.get('files', {}).items():
    if files:
        print(f"  • {ftype.upper()}: {len(files)} files")

# Check if we should proceed
if total == 0:
    print("\n✗ ERROR: No supported files found!")
    sys.exit(1)

if words > 2_000_000 or total > 200:
    print(f"\n⚠ WARNING: Large corpus detected ({total} files, {words:,} words)")
    print("  Consider running on a subfolder for faster results")
    proceed = input("  Continue with full corpus? (y/n): ").strip().lower()
    if proceed != 'y':
        print("  Setup cancelled.")
        sys.exit(0)

# Step 3A: Structural extraction (AST)
print("\n[STEP 3A] Extracting structural entities (AST)...")
detect_data = json.loads(Path('graphify-out/.graphify_detect.json').read_text())
code_files = []

for f in detect_data.get('files', {}).get('code', []):
    p = Path(f)
    code_files.extend(collect_files(p) if p.is_dir() else [p])

if code_files:
    result = extract(code_files)
    Path('graphify-out/.graphify_ast.json').write_text(json.dumps(result, indent=2))
    print(f"✓ AST Extraction Complete:")
    print(f"  Nodes: {len(result['nodes'])}")
    print(f"  Edges: {len(result['edges'])}")
else:
    Path('graphify-out/.graphify_ast.json').write_text(json.dumps({'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}))
    print("✓ No code files to extract (skipped)")

print("\n" + "="*60)
print("SETUP PHASE 1 COMPLETE")
print("="*60)
print("\nNext steps:")
print("  1. Run semantic extraction (requires AI API)")
print("  2. Build knowledge graph")
print("  3. Generate HTML visualization and reports")
print("\nTo continue, run:")
print("  python continue_graphify.py")
print("="*60 + "\n")
