#!/usr/bin/env python3
"""Edit toolkit - safe file editing utilities for OpenClaw.

This module provides robust file editing with validation, auto-recovery,
and clear error reporting. Use these instead of raw edit calls.

Functions:
    safe_edit(file_path, old_text, new_text) -> bool
    validate_before_edit(file_path, old_text) -> (bool, str)
    find_text_in_file(file_path, target_text) -> (ratio, matched_text, position)
    show_edit_preview(file_path, old_text, new_text) -> None
"""

import difflib
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

BASE = Path(__file__).parent.parent.resolve()


def find_text_in_file(file_path: str, target_text: str) -> Tuple[float, str, int]:
    """
    Find the best matching location for target_text in file.

    Returns:
        (match_ratio, matched_text, start_position)
    """
    path = Path(file_path)
    if not path.exists():
        return 0.0, "", -1

    content = path.read_text(encoding="utf-8")

    # Try exact match
    if target_text in content:
        start = content.index(target_text)
        return 1.0, target_text, start

    # Try line-by-line matching
    content_lines = content.split("\n")
    target_lines = target_text.strip().split("\n")

    if len(target_lines) > 1:
        best_ratio = 0.0
        best_start = 0
        target_count = len(target_lines)

        for i in range(len(content_lines) - target_count + 1):
            block = "\n".join(content_lines[i : i + target_count])
            ratio = difflib.SequenceMatcher(None, block, target_text).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_start = i

        if best_ratio > 0.5:
            matched = "\n".join(content_lines[best_start : best_start + target_count])
            pos = content.index(matched) if matched in content else 0
            return best_ratio, matched, pos

    # Character-level matching
    best_ratio = 0.0
    best_pos = 0
    target_len = len(target_text)

    for i in range(max(1, len(content) - target_len + 1)):
        chunk = content[i : i + target_len]
        ratio = difflib.SequenceMatcher(None, chunk, target_text).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_pos = i

    matched = content[best_pos : best_pos + target_len]
    return best_ratio, matched, best_pos


def validate_before_edit(file_path: str, old_text: str) -> Tuple[bool, str]:
    """
    Validate that old_text exists in file_path.

    Returns:
        (is_valid, error_message_or_matched_text)
    """
    ratio, matched, _ = find_text_in_file(file_path, old_text)

    if ratio == 1.0:
        return True, "Exact match"

    if ratio >= 0.9:
        return (
            False,
            f"Close match ({ratio:.1%}) but not exact. Matched: {matched[:80]}...",
        )

    if ratio >= 0.5:
        return False, f"Partial match ({ratio:.1%}). Best match: {matched[:80]}..."

    return False, f"No match found (best: {ratio:.1%})"


def show_diff(old_text: str, new_text: str, context: str = "") -> None:
    """Show a unified diff between old and new text."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    fromfile = f"{context} (current)" if context else "current"
    tofile = f"{context} (new)" if context else "new"

    diff = difflib.unified_diff(
        old_lines, new_lines, fromfile=fromfile, tofile=tofile, lineterm=""
    )

    print(f"\n{'=' * 60}")
    print(f"EDIT PREVIEW: {context}")
    print("=" * 60)
    for line in diff:
        print(line, end="")
    print()


def safe_edit(
    file_path: str, old_text: str, new_text: str, verbose: bool = True
) -> bool:
    """
    Safely edit a file with validation and auto-recovery.

    This function:
    1. Validates the old_text exists
    2. Shows a diff preview (if verbose)
    3. Applies the edit if valid
    4. Attempts fuzzy match if exact fails (ratio > 0.85)
    5. Reports clear errors if edit fails

    Args:
        file_path: Path to file to edit
        old_text: Text to replace (must match exactly or closely)
        new_text: Replacement text
        verbose: Show progress and diffs

    Returns:
        True if edit succeeded
    """
    path = Path(file_path)

    if not path.exists():
        if verbose:
            print(f"❌ File not found: {file_path}")
        return False

    # Read current content
    content = path.read_text(encoding="utf-8")

    # Try exact match
    if old_text in content:
        new_content = content.replace(old_text, new_text, 1)
        path.write_text(new_content, encoding="utf-8")
        if verbose:
            print(f"✅ Exact match edit: {file_path}")
        return True

    # Exact match failed - try fuzzy
    if verbose:
        print(f"⚠️  Exact match failed for: {file_path}")
        print("   Attempting fuzzy match...")

    ratio, matched, pos = find_text_in_file(file_path, old_text)

    if verbose:
        print(f"   Match ratio: {ratio:.1%}")

    if ratio >= 0.85:
        # Fuzzy match - apply with warning
        new_content = content[:pos] + new_text + content[pos + len(matched) :]
        path.write_text(new_content, encoding="utf-8")

        if verbose:
            print("⚠️  Fuzzy match edit applied (threshold: 85%)")
            show_diff(matched, new_text, file_path)
        return True

    # Failed to match
    if verbose:
        print(f"❌ Edit failed - match ratio too low ({ratio:.1%} < 85%)")
        show_diff(old_text, matched, "What was expected vs what was found")

        # Suggest using write instead
        print(
            "\n💡 Suggestion: The file has changed. Consider using write() instead of edit()"
        )
        print("   Or re-read the file to get the current content.")

    return False


def edit_with_fallback(
    file_path: str, old_text: str, new_text: str, force: bool = False
) -> bool:
    """
    Edit with automatic fallback to write if edit fails.

    Args:
        force: If True, always use write (full replacement)
    """
    if force:
        Path(file_path).write_text(new_text, encoding="utf-8")
        print(f"✅ Force write: {file_path}")
        return True

    if safe_edit(file_path, old_text, new_text):
        return True

    # Edit failed - ask user what to do
    print(f"\n⚠️  Edit failed for {file_path}")
    print("   Options:")
    print("   1. Re-read file and try again")
    print("   2. Use write() to replace entire file")
    print("   3. Use auto_edit.py for fuzzy matching")

    return False


# Convenience function for OpenClaw integration
def edit(file_path: str, old_text: str, new_text: str) -> bool:
    """
    Main entry point - use this for all file edits.

    Example:
        from edit_toolkit import edit
        success = edit("myfile.py", "old code", "new code")
        if not success:
            # Handle failure
            pass
    """
    return safe_edit(file_path, old_text, new_text)


if __name__ == "__main__":
    # Demo/test
    test_file = "/tmp/edit_toolkit_test.txt"
    Path(test_file).write_text("Hello\nWorld\nOld Line\nEnd")

    print("Testing edit toolkit...")
    print(f"\nOriginal content:\n{Path(test_file).read_text()}")

    # Test exact match
    success = edit(test_file, "Old Line", "New Line")
    print(f"\nAfter edit (exact match):\n{Path(test_file).read_text()}")

    # Test mismatch
    success = edit(test_file, "Nonexistent", "Should fail")
    print(f"\nEdit success: {success}")

    # Cleanup
    Path(test_file).unlink(missing_ok=True)
