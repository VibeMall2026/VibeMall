#!/usr/bin/env python
"""Graphify setup - non-interactive version with file output."""

import json
import sys
from pathlib import Path

try:
    from graphify.detect import detect
    from graphify.extract import collect_files, extract
except ImportError as e:
    with open('graphify-out/setup_error.log', 'w') as f:
        f.write(f"Import Error: {e}\n")
    sys.exit(1)

output_file = Path('graphify-out/setup_output.log')
output_dir = Path('graphify-out')
output_dir.mkdir(exist_ok=True)

logs = []

try:
    logs.append("="*60)
    logs.append("GRAPHIFY SETUP FOR VIBEMALL")
    logs.append("="*60)
    
    # Step 2: Detect files
    logs.append("\n[STEP 2] Detecting files in corpus...")
    result = detect(Path('.'))
    Path('graphify-out/.graphify_detect.json').write_text(json.dumps(result, indent=2))
    
    total = result.get('total_files', 0)
    words = result.get('total_words', 0)
    
    logs.append(f"\nCORPUS SUMMARY:")
    logs.append(f"  Total files: {total}")
    logs.append(f"  Total words: ~{words:,}")
    
    logs.append(f"\nFILE TYPES DETECTED:")
    for ftype, files in result.get('files', {}).items():
        if files:
            logs.append(f"  • {ftype.upper()}: {len(files)} files")
            # Show first 5 files of each type for reference
            sample_files = files[:5]
            for f in sample_files:
                logs.append(f"      - {f}")
            if len(files) > 5:
                logs.append(f"      ... and {len(files) - 5} more")
    
    # Step 3A: Structural extraction (AST)
    logs.append("\n[STEP 3A] Extracting structural entities (AST)...")
    detect_data = json.loads(Path('graphify-out/.graphify_detect.json').read_text())
    code_files = []
    
    for f in detect_data.get('files', {}).get('code', []):
        p = Path(f)
        code_files.extend(collect_files(p) if p.is_dir() else [p])
    
    if code_files:
        logs.append(f"  Found {len(code_files)} code files to extract")
        result = extract(code_files)
        Path('graphify-out/.graphify_ast.json').write_text(json.dumps(result, indent=2))
        logs.append(f"  AST Extraction Complete:")
        logs.append(f"    • Nodes: {len(result['nodes'])}")
        logs.append(f"    • Edges: {len(result['edges'])}")
    else:
        Path('graphify-out/.graphify_ast.json').write_text(json.dumps({'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}))
        logs.append("  No code files to extract (skipped)")
    
    logs.append("\n" + "="*60)
    logs.append("SETUP PHASE 1 COMPLETE")
    logs.append("="*60)
    logs.append("\nStatus: File detection and structural extraction completed")
    logs.append("Next: Semantic extraction and graph building")
    
except Exception as e:
    logs.append(f"\nERROR: {type(e).__name__}: {e}")
    import traceback
    logs.append(traceback.format_exc())

# Write to file
output_file.write_text('\n'.join(logs))

# Also print to stdout
for line in logs:
    print(line)
