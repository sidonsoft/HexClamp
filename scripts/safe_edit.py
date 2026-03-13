#!/usr/bin/env python3
"""Safe file editor - prevents edit mismatches by validating oldText first.

Usage:
    python3 scripts/safe_edit.py <file_path> <old_text_file> <new_text_file>
    
Or use as a module:
    from safe_edit import safe_edit
    safe_edit(file_path, old_text, new_text)
"""

import sys
from pathlib import Path


def safe_edit(file_path: str, old_text: str, new_text: str, verbose: bool = True) -> bool:
    """
    Safely edit a file by validating oldText matches before writing.
    
    Returns True if successful, False if oldText doesn't match.
    """
    path = Path(file_path)
    
    if not path.exists():
        if verbose:
            print(f"❌ File does not exist: {file_path}", file=sys.stderr)
        return False
    
    current_content = path.read_text(encoding="utf-8")
    
    if old_text not in current_content:
        if verbose:
            print(f"❌ old_text not found in {file_path}", file=sys.stderr)
            print(f"   File size: {len(current_content)} chars", file=sys.stderr)
            print(f"   old_text size: {len(old_text)} chars", file=sys.stderr)
            
            # Find closest match
            for i, (c1, c2) in enumerate(zip(current_content, old_text)):
                if c1 != c2:
                    print(f"   First diff at position {i}: got {repr(c1)}, expected {repr(c2)}", file=sys.stderr)
                    break
        return False
    
    # Perform the edit
    new_content = current_content.replace(old_text, new_text, 1)
    path.write_text(new_content, encoding="utf-8")
    
    if verbose:
        print(f"✅ Successfully edited {file_path}")
    return True


def preview_edit(file_path: str, old_text: str, new_text: str) -> None:
    """
    Preview what would change without actually editing.
    """
    path = Path(file_path)
    
    if not path.exists():
        print(f"❌ File does not exist: {file_path}")
        return
    
    current_content = path.read_text(encoding="utf-8")
    
    if old_text not in current_content:
        print(f"❌ old_text not found in {file_path}")
        
        # Show context around what we expected
        old_first_line = old_text.split('\n')[0] if old_text else ""
        if old_first_line:
            for i, line in enumerate(current_content.split('\n')):
                if old_first_line in line:
                    print(f"   Similar line found at {i}:")
                    print(f"   Got:     {repr(line)}")
                    print(f"   Expected: {repr(old_first_line)}")
                    break
        return
    
    print(f"✅ old_text found in {file_path}")
    print(f"   Changes: {len(old_text)} -> {len(new_text)} chars")
    print(f"   Old text preview: {old_text[:80]}...")
    print(f"   New text preview: {new_text[:80]}...")


def main():
    if len(sys.argv) < 2:
        print("Usage: safe_edit.py <file_path> [old_text_file] [new_text_file] [--preview]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if sys.argv[-1] == "--preview":
        # Preview mode - show what would change
        old_text_file = sys.argv[2] if len(sys.argv) > 3 else None
        if old_text_file:
            old_text = Path(old_text_file).read_text(encoding="utf-8")
            new_text = Path(sys.argv[3]).read_text(encoding="utf-8") if len(sys.argv) > 4 else ""
            preview_edit(file_path, old_text, new_text)
        else:
            print("Preview mode requires old_text_file")
        return
    
    if len(sys.argv) < 4:
        print("Usage: safe_edit.py <file_path> <old_text_file> <new_text_file>")
        print("       safe_edit.py <file_path> --preview")
        sys.exit(1)
    
    old_text = Path(sys.argv[2]).read_text(encoding="utf-8")
    new_text = Path(sys.argv[3]).read_text(encoding="utf-8")
    
    success = safe_edit(file_path, old_text, new_text)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
