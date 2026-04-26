#!/usr/bin/env python
"""Complete Graphify pipeline for VibeMall codebase."""

import json
import sys
from pathlib import Path

# Setup logging
log_lines = []

def log(msg):
    """Log message to file and print."""
    log_lines.append(msg)
    print(msg)

try:
    log("="*70)
    log("GRAPHIFY COMPLETE PIPELINE FOR VIBEMALL")
    log("="*70)
    
    from graphify.detect import detect
    from graphify.extract import collect_files, extract
    from graphify.build import build
    
    output_dir = Path('graphify-out')
    
    # Step 2: Detect files (using .graphifyignore)
    log("\n[STEP 2] Detecting files with .graphifyignore rules...")
    result = detect(Path('.'))
    Path('graphify-out/.graphify_detect.json').write_text(json.dumps(result, indent=2))
    
    total = result.get('total_files', 0)
    words = result.get('total_words', 0)
    
    log(f"\n✓ CORPUS SUMMARY:")
    log(f"  Files: {total:,}")
    log(f"  Words: {words:,}")
    
    log(f"\n✓ FILE TYPES:")
    file_summary = {}
    for ftype, files in result.get('files', {}).items():
        if files:
            file_summary[ftype] = len(files)
            log(f"  • {ftype.upper():12s} {len(files):4d} files")
    
    if total == 0:
        log("\n✗ ERROR: No supported files found!")
        sys.exit(1)
    
    if words > 2_000_000 or total > 200:
        log(f"\n⚠ Large corpus detected. Proceeding with optimization...")
    
    # Step 3A: Structural extraction (AST)
    log("\n[STEP 3A] Extracting structural entities (AST)...")
    detect_data = json.loads(Path('graphify-out/.graphify_detect.json').read_text())
    code_files = []
    
    for f in detect_data.get('files', {}).get('code', []):
        p = Path(f)
        code_files.extend(collect_files(p) if p.is_dir() else [p])
    
    if code_files:
        log(f"  Processing {len(code_files)} code files...")
        result = extract(code_files)
        Path('graphify-out/.graphify_ast.json').write_text(json.dumps(result, indent=2))
        log(f"  ✓ AST Complete: {len(result['nodes'])} nodes, {len(result['edges'])} edges")
    else:
        Path('graphify-out/.graphify_ast.json').write_text(json.dumps({'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}))
        log(f"  ✓ No code files to extract")
    
    # Step 3B: Semantic extraction (if docs/markdown exist)
    log("\n[STEP 3B] Extracting semantic entities from docs...")
    detect_data = json.loads(Path('graphify-out/.graphify_detect.json').read_text())
    doc_files = detect_data.get('files', {}).get('docs', [])
    
    if doc_files:
        log(f"  Found {len(doc_files)} documentation files")
        doc_file_paths = [Path(f) for f in doc_files[:50]]  # Limit to first 50 for speed
        
        # For semantic extraction, we'd call AI here
        # Since this requires API calls, we'll skip for now but create placeholder
        Path('graphify-out/.graphify_semantic.json').write_text(json.dumps({
            'nodes': [],
            'edges': [],
            'input_tokens': 0,
            'output_tokens': 0,
            'note': 'Semantic extraction requires AI API. Run with API key to enable.'
        }))
        log(f"  ℹ Semantic extraction skipped (requires AI API)")
    else:
        Path('graphify-out/.graphify_semantic.json').write_text(json.dumps({'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}))
        log(f"  ℹ No documentation files found")
    
    # Step 4: Build knowledge graph
    log("\n[STEP 4] Building knowledge graph...")
    ast_data = json.loads(Path('graphify-out/.graphify_ast.json').read_text())
    semantic_data = json.loads(Path('graphify-out/.graphify_semantic.json').read_text())
    
    # Merge AST and semantic data
    all_nodes = ast_data.get('nodes', []) + semantic_data.get('nodes', [])
    all_edges = ast_data.get('edges', []) + semantic_data.get('edges', [])
    
    graph_data = {
        'nodes': all_nodes,
        'edges': all_edges,
        'metadata': {
            'total_files': total,
            'total_words': words,
            'file_types': file_summary,
            'built_with': 'graphify',
        }
    }
    
    Path('graphify-out/graph.json').write_text(json.dumps(graph_data, indent=2))
    log(f"  ✓ Graph built: {len(all_nodes)} nodes, {len(all_edges)} edges")
    
    # Step 5: Generate report
    log("\n[STEP 5] Generating GRAPH_REPORT.md...")
    
    report = []
    report.append("# VibeMall Codebase Knowledge Graph Report\n")
    report.append(f"**Generated:** {Path('graphify-out/GRAPH_REPORT.md').stat().st_mtime if Path('graphify-out/GRAPH_REPORT.md').exists() else 'Now'}\n\n")
    
    report.append("## Corpus Overview\n")
    report.append(f"- **Total Files:** {total:,}\n")
    report.append(f"- **Total Words:** {words:,}\n")
    report.append(f"- **Knowledge Graph Nodes:** {len(all_nodes)}\n")
    report.append(f"- **Knowledge Graph Edges:** {len(all_edges)}\n\n")
    
    report.append("## File Type Breakdown\n")
    for ftype, count in sorted(file_summary.items(), key=lambda x: x[1], reverse=True):
        report.append(f"- **{ftype.upper()}:** {count} files\n")
    
    report.append("\n## Graph Statistics\n")
    if all_nodes:
        node_types = {}
        for node in all_nodes:
            ntype = node.get('type', 'unknown')
            node_types[ntype] = node_types.get(ntype, 0) + 1
        
        report.append("### Node Types\n")
        for ntype, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True):
            report.append(f"- {ntype}: {count}\n")
    
    if all_edges:
        edge_types = {}
        for edge in all_edges:
            etype = edge.get('type', 'unknown')
            edge_types[etype] = edge_types.get(etype, 0) + 1
        
        report.append("\n### Edge Types\n")
        for etype, count in sorted(edge_types.items(), key=lambda x: x[1], reverse=True):
            report.append(f"- {etype}: {count}\n")
    
    report.append("\n## Next Steps\n\n")
    report.append("1. **View the Graph:** Open `graphify-out/graph.html` in your browser\n")
    report.append("2. **Query the Graph:** Use graphify CLI to explore relationships\n")
    report.append("3. **Update Regularly:** Run `/graphify .` to keep graph in sync\n\n")
    
    report.append("## Output Files\n\n")
    report.append("```\ngraphify-out/\n")
    report.append("├── graph.json              # Complete knowledge graph\n")
    report.append("├── GRAPH_REPORT.md         # This report\n")
    report.append("├── .graphify_ast.json      # Structural extraction data\n")
    report.append("├── .graphify_detect.json   # File detection results\n")
    report.append("└── cache/                  # Extraction cache\n")
    report.append("```\n")
    
    Path('graphify-out/GRAPH_REPORT.md').write_text(''.join(report))
    log(f"  ✓ Report generated at graphify-out/GRAPH_REPORT.md")
    
    log("\n" + "="*70)
    log("✓ GRAPHIFY SETUP COMPLETE!")
    log("="*70)
    log("\n📊 Output Files Generated:")
    log("  • graphify-out/graph.json          - Knowledge graph (JSON)")
    log("  • graphify-out/GRAPH_REPORT.md    - Analysis report (Markdown)")
    log("  • graphify-out/.graphify_ast.json - Structural data")
    log("\n🔍 Usage Examples:")
    log("  graphify query 'show Django models'")
    log("  graphify query 'what connects views to models'")
    log("  graphify path 'User' 'Order'")
    log("\n📖 Documentation:")
    log("  Read: graphify-out/GRAPH_REPORT.md")
    log("  View: graphify-out/graph.json")
    log("\n" + "="*70 + "\n")
    
except Exception as e:
    log(f"\n✗ ERROR: {type(e).__name__}")
    log(f"  {e}")
    import traceback
    log("\nFull traceback:")
    log(traceback.format_exc())
    sys.exit(1)

finally:
    # Save log to file
    Path('graphify-out/setup_complete.log').write_text('\n'.join(log_lines))
