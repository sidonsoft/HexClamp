#!/usr/bin/env python3
"""Standalone security tests for CLIAgent shell injection fixes.

Run with: python3 tests/test_security_standalone.py
"""
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import directly to avoid Python 3.9 issues with union types in other modules
# We'll exec the agent module in isolation
import types

# Create a mock models module
class MockActionType:
    CODE = "code"
    RESEARCH = "research"
    MESSAGE = "message"

class MockResult:
    def __init__(self, success=False, message="", evidence=None):
        self.success = success
        self.message = message
        self.evidence = evidence or {}

class MockAction:
    def __init__(self, type, args=None, kwargs=None):
        self.type = type
        self.args = args or []
        self.kwargs = kwargs or {}

# Now exec the agent module with our mock
agent_code = open(Path(__file__).parent.parent / "src" / "hexclamp" / "agent.py").read()
# Replace the import from hexclamp.models with our mocks
agent_code = agent_code.replace(
    "from hexclamp.models import Action, ActionType, Result",
    "Action, ActionType, Result = MockAction, MockActionType, MockResult"
)
exec(agent_code, globals())

# Now we have CLIAgent and ALLOWED_SHELL_COMMANDS available


def test_blocks_shell_metacharacter_semicolon():
    """Block command injection via semicolon."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "ls; rm -rf /"},
        )
        result = agent.execute(action)
        assert not result.success, "Should block semicolon injection"
        assert "dangerous character" in result.message, f"Wrong message: {result.message}"
        print("✓ Blocks semicolon injection")


def test_blocks_shell_metacharacter_pipe():
    """Block command injection via pipe."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "ls | cat /etc/passwd"},
        )
        result = agent.execute(action)
        assert not result.success, "Should block pipe injection"
        assert "dangerous character" in result.message, f"Wrong message: {result.message}"
        print("✓ Blocks pipe injection")


def test_blocks_shell_metacharacter_ampersand():
    """Block command injection via ampersand."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "ls & cat /etc/passwd"},
        )
        result = agent.execute(action)
        assert not result.success, "Should block ampersand injection"
        assert "dangerous character" in result.message, f"Wrong message: {result.message}"
        print("✓ Blocks ampersand injection")


def test_blocks_shell_metacharacter_dollar():
    """Block command injection via dollar sign."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "echo $(cat /etc/passwd)"},
        )
        result = agent.execute(action)
        assert not result.success, "Should block dollar sign injection"
        assert "dangerous character" in result.message, f"Wrong message: {result.message}"
        print("✓ Blocks dollar sign injection")


def test_blocks_shell_metacharacter_backtick():
    """Block command injection via backtick."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "echo `cat /etc/passwd`"},
        )
        result = agent.execute(action)
        assert not result.success, "Should block backtick injection"
        assert "dangerous character" in result.message, f"Wrong message: {result.message}"
        print("✓ Blocks backtick injection")


def test_blocks_non_whitelisted_command():
    """Block commands not in whitelist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "rm -rf /"},
        )
        result = agent.execute(action)
        assert not result.success, "Should block non-whitelisted command"
        assert "Command not allowed" in result.message, f"Wrong message: {result.message}"
        assert "rm" in result.message, "Should mention the blocked command"
        print("✓ Blocks non-whitelisted command (rm)")


def test_allows_whitelisted_command():
    """Allow commands in whitelist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "ls -la"},
        )
        result = agent.execute(action)
        assert result.success, f"Should allow ls command: {result.message}"
        print("✓ Allows whitelisted command (ls)")


def test_allows_whitelisted_grep():
    """Allow grep command from whitelist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        # Create a test file
        test_file = agent.workspace / "test.txt"
        test_file.write_text("hello world\nfoo bar\n")
        
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "grep hello test.txt"},
        )
        result = agent.execute(action)
        assert result.success, f"Should allow grep: {result.message}"
        assert "hello" in result.message, "Should find hello in output"
        print("✓ Allows whitelisted command (grep)")


def test_blocks_path_traversal_read():
    """Block path traversal in read command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "read", "path": "../../../etc/passwd"},
        )
        result = agent.execute(action)
        assert not result.success, "Should block path traversal"
        assert "Invalid path" in result.message, f"Wrong message: {result.message}"
        print("✓ Blocks path traversal (read)")


def test_blocks_path_traversal_write():
    """Block path traversal in write command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.CODE,
            kwargs={
                "command": "write",
                "path": "../../../tmp/malicious.txt",
                "content": "malicious",
            },
        )
        result = agent.execute(action)
        assert not result.success, "Should block path traversal"
        assert "Invalid path" in result.message, f"Wrong message: {result.message}"
        print("✓ Blocks path traversal (write)")


def test_research_blocks_non_whitelisted_command():
    """Block non-whitelisted commands in research."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.RESEARCH,
            kwargs={"command": "rm"},
            args=["-rf", "/"],
        )
        result = agent.execute(action)
        assert not result.success, "Should block non-whitelisted command"
        assert "Command not allowed" in result.message, f"Wrong message: {result.message}"
        print("✓ Research blocks non-whitelisted command (rm)")


def test_research_blocks_shell_metacharacters_in_args():
    """Block shell metacharacters in research arguments."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.RESEARCH,
            kwargs={"command": "grep"},
            args=["hello; rm -rf /", "file.txt"],
        )
        result = agent.execute(action)
        assert not result.success, "Should block metacharacters in args"
        assert "dangerous character" in result.message, f"Wrong message: {result.message}"
        print("✓ Research blocks shell metacharacters in args")


def test_research_allows_whitelisted_command():
    """Allow whitelisted commands in research."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        # Create a test file
        test_file = agent.workspace / "test.txt"
        test_file.write_text("hello world\n")
        
        action = Action(
            type=ActionType.RESEARCH,
            kwargs={"command": "grep"},
            args=["hello", "test.txt"],
        )
        result = agent.execute(action)
        assert result.success, f"Should allow grep: {result.message}"
        print("✓ Research allows whitelisted command (grep)")


def test_empty_script_rejected():
    """Reject empty script."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": ""},
        )
        result = agent.execute(action)
        assert not result.success, "Should reject empty script"
        assert "Invalid script" in result.message, f"Wrong message: {result.message}"
        print("✓ Rejects empty script")


def test_allows_all_whitelisted_commands():
    """Verify all whitelisted commands work."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CLIAgent(workspace=Path(tmpdir))
        
        for cmd in ALLOWED_SHELL_COMMANDS:
            # Test with simple args that won't fail
            if cmd in ("grep", "rg"):
                # Create test file first
                test_file = agent.workspace / "test.txt"
                test_file.write_text("test\n")
                script = f"{cmd} test test.txt"
            elif cmd == "find":
                script = f"{cmd} . -maxdepth 1"
            elif cmd in ("head", "tail", "cat", "wc"):
                # Create test file first
                test_file = agent.workspace / "test.txt"
                test_file.write_text("test\n")
                script = f"{cmd} test.txt"
            else:
                script = f"{cmd}"
            
            action = Action(
                type=ActionType.CODE,
                kwargs={"command": "run", "script": script},
            )
            result = agent.execute(action)
            # Command should be allowed (may fail for other reasons, but not security)
            assert "Command not allowed" not in result.message, f"Command {cmd} should be allowed"
            assert "dangerous character" not in result.message, f"Command {cmd} should not trigger security"
        
        print(f"✓ All {len(ALLOWED_SHELL_COMMANDS)} whitelisted commands work: {', '.join(sorted(ALLOWED_SHELL_COMMANDS))}")


def main():
    """Run all security tests."""
    print("=" * 60)
    print("Shell Injection Security Tests")
    print("=" * 60)
    print()
    
    tests = [
        test_blocks_shell_metacharacter_semicolon,
        test_blocks_shell_metacharacter_pipe,
        test_blocks_shell_metacharacter_ampersand,
        test_blocks_shell_metacharacter_dollar,
        test_blocks_shell_metacharacter_backtick,
        test_blocks_non_whitelisted_command,
        test_allows_whitelisted_command,
        test_allows_whitelisted_grep,
        test_blocks_path_traversal_read,
        test_blocks_path_traversal_write,
        test_research_blocks_non_whitelisted_command,
        test_research_blocks_shell_metacharacters_in_args,
        test_research_allows_whitelisted_command,
        test_empty_script_rejected,
        test_allows_all_whitelisted_commands,
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
    sys.exit(main())
