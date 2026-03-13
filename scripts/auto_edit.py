#!/usr/bin/env python3
"""Auto-recovery file editor - handles edit mismatches automatically.

When oldText fails to match, this script:
1. Analyzes the mismatch
2. Attempts to find the closest matching content
3. Applies the edit with fuzzy matching if possible
4. Reports exactly what was different

Usage:
    python3 scripts/auto_edit.py <file_path> --find <old_snippet> --replace <new_snippet>
"""

import difflib
import sys
from pathlib import Path


def find_best_match(content: str, target: str, context_lines: int = 3) -> tuple:
    """
    Find the best matching location for target within content.
    Returns (match_ratio, matched_text, start_pos, end_pos)
    """
    if target in content:
        start = content.index(target)
        return (1.0, target, start, start + len(target))
    
    # Try line-by-line matching
    content_lines = content.split('\n')
    target_lines = target.strip().split('\n')
    
    if len(target_lines) <= 1:
        # Single line - use character matching
        best_ratio = 0
        best_start = 0
        target_len = len(target)
        
        for i in range(len(content) - target_len + 1):
            chunk = content[i:i + target_len]
            ratio = difflib.SequenceMatcher(None, chunk, target).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_start = i
        
        matched = content[best_start:best_start + target_len]
        return (best_ratio, matched, best_start, best_start + target_len)
    
    # Multi-line - try to match line blocks
    best_ratio = 0
    best_start_line = 0
    target_line_count = len(target_lines)
    
    for i in range(len(content_lines) - target_line_count + 1):
        block = '\n'.join(content_lines[i:i + target_line_count])
        ratio = difflib.SequenceMatcher(None, block, target).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_start_line = i
    
    # Get the matched block with context
    start_line = max(0, best_start_line - context_lines)
    end_line = min(len(content_lines), best_start_line + target_line_count + context_lines)
    matched_block = '\n'.join(content_lines[start_line:end_line])
    
    # Find exact position in content
    try:
        start_pos = content.index(content_lines[best_start_line])
        end_pos = content.index(content_lines[min(best_start_line + target_line_count - 1, len(content_lines) - 1)]) + len(content_lines[min(best_start_line + target_line_count - 1, len(content_lines) - 1)])
    except ValueError:
        start_pos = 0
        end_pos = len(matched_block)
    
    return (best_ratio, matched_block, start_pos, end_pos)


def show_diff(old: str, new: str, label: str = "") -> None:
    """Show a unified diff between old and new text."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"{label} (expected)", tofile=f"{label} (actual)", lineterm='')
    
    print(f"\n{'='*60}")
    print(f"DIFF: {label}")
    print('='*60)
    for line in diff:
        print(line, end='')
    print()


def auto_edit(file_path: str, expected_old: str, new_text: str, threshold: float = 0.85) -> bool:
    """
    Attempt to edit file with auto-recovery for mismatches.
    
    Args:
        threshold: Minimum match ratio to accept (0.0-1.0)
    
    Returns:
        True if edit succeeded (either exact or fuzzy match)
    """
    path = Path(file_path)
    
    if not path.exists():
        print(f"❌ File not found: {file_path}", file=sys.stderr)
        return False
    
    content = path.read_text(encoding="utf-8")
    
    # Try exact match first
    if expected_old in content:
        new_content = content.replace(expected_old, new_text, 1)
        path.write_text(new_content, encoding="utf-8")
        print(f"✅ Exact match edit succeeded: {file_path}")
        return True
    
    # No exact match - try to find best match
    print(f"⚠️  Exact match failed for {file_path}", file=sys.stderr)
    print(f"   Looking for best match...", file=sys.stderr)
    
    ratio, matched, start, end = find_best_match(content, expected_old)
    
    print(f"   Best match ratio: {ratio:.2%}", file=sys.stderr)
    
    if ratio >= threshold:
        print(f"   Using fuzzy match (threshold: {threshold:.0%})", file=sys.stderr)
        
        # Show what we're about to replace
        print(f"\n   Would replace:")
        print(f"   {'='*60}")
        print(f"   {matched[:200]}..." if len(matched) > 200 else f"   {matched}")
        print(f"   {'='*60}")
        print(f"\n   With new content ({len(new_text)} chars)")
        
        # Apply the edit
        new_content = content[:start] + new_text + content[end:]
        path.write_text(new_content, encoding="utf-8")
        print(f"✅ Fuzzy match edit succeeded: {file_path}")
        
        # Show the diff
        show_diff(expected_old, matched, "Fuzzy Match")
        
        return True
    else:
        print(f"❌ Match ratio too low ({ratio:.2%} < {threshold:.0%})", file=sys.stderr)
        show_diff(expected_old, matched, "Best Available Match")
        return False


def main():
    if len(sys.argv) < 6 or "--find" not in sys.argv or "--replace" not in sys.argv:
        print("Usage: auto_edit.py <file_path> --find <old_snippet_file> --replace <new_snippet_file> [--threshold <0.0-1.0>]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # Parse arguments
    find_idx = sys.argv.index("--find")
    replace_idx = sys.argv.index("--replace")
    
    old_file = sys.argv[find_idx + 1]
    new_file = sys.argv[replace_idx + 1]
    
    threshold = 0.85
    if "--threshold" in sys.argv:
        thresh_idx = sys.argv.index("--threshold")
        threshold = float(sys.argv[thresh_idx + 1])
    
    old_text = Path(old_file).read_text(encoding="utf-8")
    new_text = Path(new_file).read_text(encoding="utf-8")
    
    success = auto_edit(file_path, old_text, new_text, threshold)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
