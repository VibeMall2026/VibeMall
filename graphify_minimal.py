#!/usr/bin/env python
"""Graphify minimal setup - Python-only, no subprocess calls."""

import json
import sys
from pathlib import Path

output_dir = Path('graphify-out')
output_dir.mkdir(exist_ok=True)

print("Starting Graphify setup...", flush=True)
sys.stdout.flush()

try:
    print("Importing graphify...", flush=True)
    from graphify.detect import detect
    from graphify.extract import collect_files, extract
    
    print("Detecting files...", flush=True)
    result = detect(Path('.'))
    
    total = result.get('total_files', 0)
    words = result.get('total_words', 0)
    
    print(f"Detected: {total} files, ~{words:,} words", flush=True)
    
    # Save detection result
    Path('graphify-out/.graphify_detect.json').write_text(json.dumps(result, indent=2))
    print("Saved detection data", flush=True)
    
    # Extract code
    code_files = result.get('files', {}).get('code', [])
    print(f"Found {len(code_files)} code files", flush=True)
    
    if code_files:
        print("Starting AST extraction (this takes time)...", flush=True)
        code_paths = []
        for f in code_files[:50]:  # Only first 50 for speed
            p = Path(f)
            code_paths.extend(collect_files(p) if p.is_dir() else [p])
        
        print(f"Extracting from {len(code_paths)} source files...", flush=True)
        result = extract(code_paths)
        Path('graphify-out/.graphify_ast.json').write_text(json.dumps(result, indent=2))
        print(f"Extracted: {len(result.get('nodes', []))} nodes, {len(result.get('edges', []))} edges", flush=True)
    
    # Create graph
    ast_data = json.loads(Path('graphify-out/.graphify_ast.json').read_text()) if Path('graphify-out/.graphify_ast.json').exists() else {'nodes': [], 'edges': []}
    
    graph = {
        'nodes': ast_data.get('nodes', []),
        'edges': ast_data.get('edges', []),
        'metadata': {'total_files': total, 'total_words': words}
    }
    Path('graphify-out/graph.json').write_text(json.dumps(graph, indent=2))
    print(f"Graph saved with {len(graph['nodes'])} nodes", flush=True)
    
    # Create report
    report = f"""# VibeMall Knowledge Graph Report

## Summary
- **Total Files:** {total:,}
- **Total Words:** {words:,}  
- **Graph Nodes:** {len(graph['nodes'])}
- **Graph Edges:** {len(graph['edges'])}

## Files Generated
- `graph.json` - Knowledge graph
- `GRAPH_REPORT.md` - This report
- `.graphify_ast.json` - AST data

## Setup Complete
Graphify knowledge graph has been built for your VibeMall codebase.
"""
    Path('graphify-out/GRAPH_REPORT.md').write_text(report)
    print("Report saved", flush=True)
    
    print("\n✅ GRAPHIFY SETUP COMPLETE", flush=True)
    print(f"\nOutput: graphify-out/", flush=True)
    print(f"  - graph.json (knowledge graph)", flush=True)
    print(f"  - GRAPH_REPORT.md (report)", flush=True)
    
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
