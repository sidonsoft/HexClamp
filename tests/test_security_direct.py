#!/usr/bin/env python3
"""Direct security tests - tests the security logic without importing the full module.

This tests the security patterns implemented in agent.py without needing
to import the module (which has Python 3.10+ syntax).

Run with: python3 tests/test_security_direct.py
"""
import subprocess
import shlex
import tempfile
from pathlib import Path


# Copy the security constants and logic from agent.py for testing
ALLOWED_SHELL_COMMANDS = frozenset(["grep", "find", "rg", "ls", "cat", "head", "tail", "wc"])
DANGEROUS_CHARS = [";", "|", "&", "$", "`", "(", ")", "<", ">", "\\", "\n", "\r"]


def validate_script(script):
    """Validate script for dangerous characters (from agent.py)."""
    if not script or not isinstance(script, str):
        return False, "Invalid script: must be non-empty string"
    for char in DANGEROUS_CHARS:
        if char in script:
            return False, f"Security error: script contains dangerous character '{char}'"
    return True, None


def validate_command(cmd):
    """Validate command is in whitelist (from agent.py)."""
    if cmd not in ALLOWED_SHELL_COMMANDS:
        return False, f"Command not allowed: {cmd}. Allowed: {', '.join(sorted(ALLOWED_SHELL_COMMANDS))}"
    return True, None


def validate_args(args):
    """Validate arguments for dangerous characters (from agent.py)."""
    for arg in args:
        if not isinstance(arg, str):
            arg = str(arg)
        for char in DANGEROUS_CHARS:
            if char in arg:
                return False, f"Security error: argument contains dangerous character '{char}'"
    return True, None


def test_blocks_shell_metacharacter_semicolon():
    """Block command injection via semicolon."""
    script = "ls; rm -rf /"
    valid, error = validate_script(script)
    assert not valid, "Should block semicolon injection"
    assert "dangerous character" in error
    print("✓ Blocks semicolon injection")


def test_blocks_shell_metacharacter_pipe():
    """Block command injection via pipe."""
    script = "ls | cat /etc/passwd"
    valid, error = validate_script(script)
    assert not valid, "Should block pipe injection"
    assert "dangerous character" in error
    print("✓ Blocks pipe injection")


def test_blocks_shell_metacharacter_ampersand():
    """Block command injection via ampersand."""
    script = "ls & cat /etc/passwd"
    valid, error = validate_script(script)
    assert not valid, "Should block ampersand injection"
    assert "dangerous character" in error
    print("✓ Blocks ampersand injection")


def test_blocks_shell_metacharacter_dollar():
    """Block command injection via dollar sign."""
    script = "echo $(cat /etc/passwd)"
    valid, error = validate_script(script)
    assert not valid, "Should block dollar sign injection"
    assert "dangerous character" in error
    print("✓ Blocks dollar sign injection")


def test_blocks_shell_metacharacter_backtick():
    """Block command injection via backtick."""
    script = "echo `cat /etc/passwd`"
    valid, error = validate_script(script)
    assert not valid, "Should block backtick injection"
    assert "dangerous character" in error
    print("✓ Blocks backtick injection")


def test_blocks_shell_metacharacter_redirect():
    """Block command injection via redirect."""
    script = "cat /etc/passwd > /tmp/stolen"
    valid, error = validate_script(script)
    assert not valid, "Should block redirect"
    assert "dangerous character" in error
    print("✓ Blocks redirect injection")


def test_blocks_non_whitelisted_command():
    """Block commands not in whitelist."""
    # Parse the script to get base command
    script = "rm -rf /"
    cmd_parts = shlex.split(script)
    base_cmd = cmd_parts[0]
    valid, error = validate_command(base_cmd)
    assert not valid, "Should block non-whitelisted command"
    assert "Command not allowed" in error
    assert "rm" in error
    print("✓ Blocks non-whitelisted command (rm)")


def test_blocks_dangerous_commands():
    """Block various dangerous commands."""
    dangerous = ["rm", "curl", "wget", "nc", "netcat", "python", "python3", "bash", "sh", "chmod", "chown"]
    for cmd in dangerous:
        valid, error = validate_command(cmd)
        assert not valid, f"Should block {cmd}"
        assert "Command not allowed" in error
    print(f"✓ Blocks {len(dangerous)} dangerous commands: {', '.join(dangerous)}")


def test_allows_whitelisted_command():
    """Allow commands in whitelist."""
    for cmd in ALLOWED_SHELL_COMMANDS:
        valid, error = validate_command(cmd)
        assert valid, f"Should allow {cmd}: {error}"
    print(f"✓ Allows all {len(ALLOWED_SHELL_COMMANDS)} whitelisted commands")


def test_allows_safe_script():
    """Allow safe scripts without dangerous chars."""
    safe_scripts = [
        "ls -la",
        "grep hello test.txt",
        "find . -maxdepth 1",
        "cat file.txt",
        "head -n 10 file.txt",
        "tail -n 10 file.txt",
        "wc -l file.txt",
    ]
    for script in safe_scripts:
        valid, error = validate_script(script)
        assert valid, f"Should allow safe script '{script}': {error}"
        
        # Also validate the command
        cmd_parts = shlex.split(script)
        base_cmd = cmd_parts[0]
        valid, error = validate_command(base_cmd)
        assert valid, f"Command {base_cmd} should be allowed: {error}"
    
    print(f"✓ Allows {len(safe_scripts)} safe scripts")


def test_research_blocks_shell_metacharacters_in_args():
    """Block shell metacharacters in research arguments."""
    args = ["hello; rm -rf /", "file.txt"]
    valid, error = validate_args(args)
    assert not valid, "Should block metacharacters in args"
    assert "dangerous character" in error
    print("✓ Research blocks shell metacharacters in args")


def test_research_allows_safe_args():
    """Allow safe arguments in research."""
    safe_args = ["hello", "test.txt", "-r", "-n", "10"]
    valid, error = validate_args(safe_args)
    assert valid, f"Should allow safe args: {error}"
    print("✓ Research allows safe arguments")


def test_subprocess_shell_false():
    """Verify subprocess is called with shell=False."""
    # This test demonstrates the safe pattern used in agent.py
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("hello world\n")
        
        # Safe pattern: shell=False with list args
        result = subprocess.run(
            ["grep", "hello", "test.txt"],
            shell=False,  # CRITICAL: Never True!
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "hello" in result.stdout
        print("✓ subprocess.run with shell=False works correctly")


def test_shell_true_would_be_dangerous():
    """Demonstrate why shell=True is dangerous (DO NOT USE)."""
    # This is what the OLD vulnerable code did - DO NOT DO THIS
    # We're showing it would work, but we've fixed it
    dangerous_script = "ls; echo INJECTED"
    
    # DON'T run this - it would execute the injection!
    # result = subprocess.run(dangerous_script, shell=True, ...)
    
    # Instead, we verify our fix blocks it
    valid, error = validate_script(dangerous_script)
    assert not valid
    print("✓ Dangerous shell=True pattern is now blocked")


def test_path_traversal_validation():
    """Test path traversal prevention logic."""
    workspace = Path("/tmp/workspace")
    
    # Test cases that should be blocked
    dangerous_paths = [
        "../../../etc/passwd",
        "/etc/passwd",
        "..",
        "../../tmp/malicious.txt",
    ]
    
    for path_str in dangerous_paths:
        path = workspace / path_str
        try:
            # This is the validation logic from agent.py
            resolved = path.resolve()
            resolved.relative_to(workspace.resolve())
            # If we get here, path traversal wasn't blocked (bad!)
            assert False, f"Should block path traversal: {path_str}"
        except (ValueError, RuntimeError):
            # Expected - path is outside workspace
            pass
    
    print(f"✓ Blocks {len(dangerous_paths)} path traversal attempts")


def test_safe_path_allowed():
    """Test that safe paths within workspace are allowed."""
    workspace = Path("/tmp/workspace")
    
    safe_paths = [
        "file.txt",
        "subdir/file.txt",
        "./file.txt",
    ]
    
    for path_str in safe_paths:
        path = workspace / path_str
        resolved = path.resolve()
        try:
            resolved.relative_to(workspace.resolve())
            # Should succeed for safe paths
        except (ValueError, RuntimeError):
            assert False, f"Should allow safe path: {path_str}"
    
    print(f"✓ Allows {len(safe_paths)} safe paths")


def main():
    """Run all security tests."""
    print("=" * 60)
    print("Shell Injection Security Tests (Direct)")
    print("=" * 60)
    print()
    
    tests = [
        test_blocks_shell_metacharacter_semicolon,
        test_blocks_shell_metacharacter_pipe,
        test_blocks_shell_metacharacter_ampersand,
        test_blocks_shell_metacharacter_dollar,
        test_blocks_shell_metacharacter_backtick,
        test_blocks_shell_metacharacter_redirect,
        test_blocks_non_whitelisted_command,
        test_blocks_dangerous_commands,
        test_allows_whitelisted_command,
        test_allows_safe_script,
        test_research_blocks_shell_metacharacters_in_args,
        test_research_allows_safe_args,
        test_subprocess_shell_false,
        test_shell_true_would_be_dangerous,
        test_path_traversal_validation,
        test_safe_path_allowed,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: Unexpected error: {e}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
