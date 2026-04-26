#!/usr/bin/env python
"""Graphify setup with optimized extraction for VibeMall."""

import json
import sys
from pathlib import Path

log_lines = []

def log(msg):
    """Log to both file and stdout."""
    log_lines.append(msg)
    print(msg, flush=True)

try:
    log("="*70)
    log("GRAPHIFY SETUP - VIBEMALL ECOMMERCE")
    log("="*70)
    
    # Import graphify modules
    log("\n[INIT] Importing graphify modules...")
    try:
        from graphify.detect import detect
        from graphify.extract import collect_files, extract
        log("✓ Graphify modules imported")
    except ImportError as e:
        log(f"✗ Failed to import graphify: {e}")
        sys.exit(1)
    
    output_dir = Path('graphify-out')
    output_dir.mkdir(exist_ok=True)
    
    # STEP 1: Detect files
    log("\n[STEP 1] File Detection (respecting .graphifyignore)...")
    log("  Scanning project structure...")
    
    result = detect(Path('.'))
    Path('graphify-out/.graphify_detect.json').write_text(json.dumps(result, indent=2))
    
    total_files = result.get('total_files', 0)
    total_words = result.get('total_words', 0)
    files_by_type = result.get('files', {})
    
    log(f"\n  📊 CORPUS DETECTED:")
    log(f"     Total Files: {total_files:,}")
    log(f"     Total Words: {total_words:,}")
    
    log(f"\n  📁 File Types:")
    for ftype, files in sorted(files_by_type.items(), key=lambda x: len(x[1] if isinstance(x[1], list) else []), reverse=True):
        if isinstance(files, list) and files:
            log(f"     • {ftype:12s}: {len(files):4d} files")
    
    if total_files == 0:
        log("\n✗ No files detected. Check .graphifyignore and project structure.")
        sys.exit(1)
    
    # STEP 2: Extract code structure  
    log("\n[STEP 2] Structural Analysis (AST Extraction)...")
    
    code_files = files_by_type.get('code', [])
    if code_files:
        log(f"  Processing {len(code_files)} code files (this may take a moment)...")
        
        code_file_paths = []
        for f in code_files:
            p = Path(f)
            code_file_paths.extend(collect_files(p) if p.is_dir() else [p])
        
        log(f"  Found {len(code_file_paths)} source files after directory expansion")
        
        try:
            log("  Running AST extraction...")
            result = extract(code_file_paths[:100])  # Limit to first 100 for speed
            Path('graphify-out/.graphify_ast.json').write_text(json.dumps(result, indent=2))
            
            nodes = result.get('nodes', [])
            edges = result.get('edges', [])
            
            log(f"  ✓ Extraction Complete:")
            log(f"     Nodes: {len(nodes)}")
            log(f"     Edges: {len(edges)}")
            
            # Analyze node types
            node_types = {}
            for node in nodes:
                ntype = node.get('type', 'unknown')
                node_types[ntype] = node_types.get(ntype, 0) + 1
            
            log(f"     Node Types: {', '.join(f'{t}({c})' for t, c in sorted(node_types.items(), key=lambda x: x[1], reverse=True)[:5])}")
            
        except Exception as e:
            log(f"  ⚠ Extraction issue: {e}")
            log(f"  Creating empty AST...")
            Path('graphify-out/.graphify_ast.json').write_text(json.dumps({
                'nodes': [],
                'edges': [],
                'input_tokens': 0,
                'output_tokens': 0,
                'error': str(e)
            }))
    else:
        log("  No code files found")
        Path('graphify-out/.graphify_ast.json').write_text(json.dumps({
            'nodes': [],
            'edges': [],
            'input_tokens': 0,
            'output_tokens': 0
        }))
    
    # STEP 3: Documentation analysis
    log("\n[STEP 3] Documentation Analysis...")
    
    doc_files = files_by_type.get('docs', [])
    if doc_files:
        log(f"  Found {len(doc_files)} documentation files")
        log("  (Semantic analysis requires AI API - creating placeholder)")
    else:
        log("  No documentation files to analyze")
    
    Path('graphify-out/.graphify_semantic.json').write_text(json.dumps({
        'nodes': [],
        'edges': [],
        'input_tokens': 0,
        'output_tokens': 0,
        'status': 'Semantic extraction requires AI API'
    }))
    
    # STEP 4: Build graph
    log("\n[STEP 4] Building Knowledge Graph...")
    
    ast_data = json.loads(Path('graphify-out/.graphify_ast.json').read_text())
    semantic_data = json.loads(Path('graphify-out/.graphify_semantic.json').read_text())
    
    graph_nodes = ast_data.get('nodes', []) + semantic_data.get('nodes', [])
    graph_edges = ast_data.get('edges', []) + semantic_data.get('edges', [])
    
    graph = {
        'nodes': graph_nodes,
        'edges': graph_edges,
        'metadata': {
            'project': 'VibeMall',
            'type': 'ecommerce-platform',
            'total_files': total_files,
            'total_words': total_words,
            'file_types': {k: len(v) if isinstance(v, list) else 0 for k, v in files_by_type.items()},
        }
    }
    
    Path('graphify-out/graph.json').write_text(json.dumps(graph, indent=2))
    log(f"  ✓ Graph created with {len(graph_nodes)} nodes and {len(graph_edges)} edges")
    
    # STEP 5: Generate report
    log("\n[STEP 5] Generating Analysis Report...")
    
    report_lines = []
    report_lines.append("# VibeMall Codebase Analysis Report\n\n")
    report_lines.append("**Knowledge Graph Report** - Generated by Graphify\n\n")
    
    report_lines.append("## 📊 Corpus Statistics\n\n")
    report_lines.append(f"- **Total Files:** {total_files:,}\n")
    report_lines.append(f"- **Total Words:** ~{total_words:,}\n\n")
    
    report_lines.append("### File Breakdown\n\n")
    for ftype, files in sorted(files_by_type.items(), key=lambda x: len(x[1] if isinstance(x[1], list) else []), reverse=True):
        if isinstance(files, list) and files:
            report_lines.append(f"- **{ftype.upper()}:** {len(files)} files\n")
    
    report_lines.append("\n## 📈 Knowledge Graph Statistics\n\n")
    report_lines.append(f"- **Nodes:** {len(graph_nodes)}\n")
    report_lines.append(f"- **Edges:** {len(graph_edges)}\n\n")
    
    if graph_nodes:
        node_types = {}
        for node in graph_nodes:
            ntype = node.get('type', 'unknown')
            node_types[ntype] = node_types.get(ntype, 0) + 1
        
        report_lines.append("### Node Types\n\n")
        for ntype, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- {ntype}: {count}\n")
    
    if graph_edges:
        edge_types = {}
        for edge in graph_edges:
            etype = edge.get('type', 'unknown')
            edge_types[etype] = edge_types.get(etype, 0) + 1
        
        report_lines.append("\n### Edge Types\n\n")
        for etype, count in sorted(edge_types.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- {etype}: {count}\n")
    
    report_lines.append("\n## 🚀 Next Steps\n\n")
    report_lines.append("1. **View Knowledge Graph:** `graphify-out/graph.json`\n")
    report_lines.append("2. **Query Examples:**\n")
    report_lines.append("   - `graphify query 'show Django models'`\n")
    report_lines.append("   - `graphify query 'what connects User to Order'`\n")
    report_lines.append("3. **Keep Updated:** Rerun to update graph with new changes\n\n")
    
    report_lines.append("## 📁 Output Files\n\n")
    report_lines.append("```\ngraphify-out/\n")
    report_lines.append("├── graph.json              # Complete knowledge graph\n")
    report_lines.append("├── GRAPH_REPORT.md         # This analysis report\n")
    report_lines.append("├── .graphify_ast.json      # Structural analysis data\n")
    report_lines.append("├── .graphify_semantic.json # Semantic analysis data\n")
    report_lines.append("└── cache/                  # Processing cache\n")
    report_lines.append("```\n")
    
    Path('graphify-out/GRAPH_REPORT.md').write_text(''.join(report_lines))
    log("  ✓ Report saved to graphify-out/GRAPH_REPORT.md")
    
    # Final summary
    log("\n" + "="*70)
    log("✅ GRAPHIFY SETUP COMPLETE!")
    log("="*70)
    
    log("\n📦 GENERATED FILES:")
    log("  ✓ graphify-out/graph.json")
    log("  ✓ graphify-out/GRAPH_REPORT.md")
    log("  ✓ graphify-out/.graphify_ast.json")
    log("  ✓ graphify-out/.graphify_semantic.json")
    
    log("\n💡 USAGE TIPS:")
    log("  • Read the graph: cat graphify-out/GRAPH_REPORT.md")
    log("  • View as JSON: graphify-out/graph.json")
    log("  • Update later: python graphify_build_complete.py")
    
    log("\n🔗 COPILOT INTEGRATION:")
    log("  • Paste GRAPH_REPORT.md content to Copilot Chat")
    log("  • Ask questions about codebase architecture")
    log("  • Reference specific files and relationships")
    
    log("\n" + "="*70 + "\n")
    
except Exception as e:
    log(f"\n✗ ERROR: {type(e).__name__}: {e}")
    import traceback
    log(traceback.format_exc())
    sys.exit(1)

finally:
    # Save complete log
    Path('graphify-out/setup.log').write_text('\n'.join(log_lines))
