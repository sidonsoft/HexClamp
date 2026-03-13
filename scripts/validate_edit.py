#!/usr/bin/env python3
"""Edit validator - pre-flight checks for file edits.

Use this before calling the edit tool to ensure oldText matches.
Returns exit code 0 if valid, 1 if mismatch detected.

Usage:
    python3 scripts/validate_edit.py <file_path> <old_text_file>
    
Or in bash:
    if python3 scripts/validate_edit.py file.py old.txt; then
        # Safe to edit
    else
        # Need to re-read file
    fi
"""

import sys
from pathlib import Path


def validate_edit(file_path: str, old_text: str) -> tuple[bool, str]:
    """
    Validate that old_text exists in file_path.
    
    Returns:
        (is_valid, error_message)
    """
    path = Path(file_path)
    
    if not path.exists():
        return False, f"File does not exist: {file_path}"
    
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Cannot read file: {e}"
    
    if old_text in content:
        return True, "old_text found in file"
    
    # Calculate similarity for error message
    # Find the closest match
    best_match = ""
    best_ratio = 0
    
    # Try first line matching
    old_first_line = old_text.split('\n')[0] if old_text else ""
    if old_first_line:
        for i, line in enumerate(content.split('\n')):
            if old_first_line.strip() == line.strip():
                return False, f"First line matches but full text differs at line {i}"
    
    # Check for whitespace issues
    old_normalized = ' '.join(old_text.split())
    content_normalized = ' '.join(content.split())
    if old_normalized in content_normalized:
        return False, "Text matches but whitespace differs (extra/missing spaces or newlines)"
    
    # Check for line ending issues
    old_crlf = old_text.replace('\n', '\r\n')
    if old_crlf in content:
        return False, "Text matches but line endings differ (expected LF, file has CRLF)"
    
    old_lf = old_text.replace('\r\n', '\n')
    if old_lf in content:
        return False, "Text matches but line endings differ (expected CRLF, file has LF)"
    
    # Generic mismatch
    return False, f"old_text not found in file (file: {len(content)} chars, expected: {len(old_text)} chars)"


def show_context(file_path: str, old_text: str) -> None:
    """Show context around where we expected to find old_text."""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")
    
    # Find first line of old_text in content
    old_lines = old_text.split('\n')
    if not old_lines:
        return
    
    first_line = old_lines[0].strip()
    content_lines = content.split('\n')
    
    for i, line in enumerate(content_lines):
        if first_line in line or line in first_line:
            print(f"\n  Context around line {i}:")
            print(f"  {'─'*60}")
            start = max(0, i - 2)
            end = min(len(content_lines), i + 3)
            for j in range(start, end):
                marker = ">>>" if j == i else "   "
                print(f"  {marker} {j+1}: {content_lines[j][:80]}")
            print(f"  {'─'*60}")
            return
    
    print(f"\n  First line of expected text not found: {first_line[:60]}...")


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_edit.py <file_path> [old_text_file]")
        print("       validate_edit.py <file_path> --read-stdin")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if sys.argv[2] == "--read-stdin":
        old_text = sys.stdin.read()
    elif len(sys.argv) >= 3:
        old_text = Path(sys.argv[2]).read_text(encoding="utf-8")
    else:
        print("Usage: validate_edit.py <file_path> [old_text_file]")
        print("       validate_edit.py <file_path> --read-stdin")
        sys.exit(1)
    
    is_valid, message = validate_edit(file_path, old_text)
    
    if is_valid:
        print(f"✅ {message}")
        sys.exit(0)
    else:
        print(f"❌ {message}", file=sys.stderr)
        show_context(file_path, old_text)
        sys.exit(1)


if __name__ == "__main__":
    main()
