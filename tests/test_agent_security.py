"""Security tests for CLIAgent shell injection fixes."""
import tempfile
import pytest
from pathlib import Path
from hexclamp.agent import CLIAgent, ALLOWED_SHELL_COMMANDS
from hexclamp.models import Action, ActionType


class TestShellInjectionPrevention:
    """Test that shell injection vulnerabilities are prevented."""

    @pytest.fixture
    def agent(self):
        """Create a CLIAgent with a temp workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield CLIAgent(workspace=Path(tmpdir))

    def test_blocks_shell_metacharacter_semicolon(self, agent):
        """Block command injection via semicolon."""
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "ls; rm -rf /"},
        )
        result = agent.execute(action)
        assert not result.success
        assert "dangerous character" in result.message
        assert ";" in result.message

    def test_blocks_shell_metacharacter_pipe(self, agent):
        """Block command injection via pipe."""
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "ls | cat /etc/passwd"},
        )
        result = agent.execute(action)
        assert not result.success
        assert "dangerous character" in result.message

    def test_blocks_shell_metacharacter_ampersand(self, agent):
        """Block command injection via ampersand."""
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "ls & cat /etc/passwd"},
        )
        result = agent.execute(action)
        assert not result.success
        assert "dangerous character" in result.message

    def test_blocks_shell_metacharacter_dollar(self, agent):
        """Block command injection via dollar sign."""
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "echo $(cat /etc/passwd)"},
        )
        result = agent.execute(action)
        assert not result.success
        assert "dangerous character" in result.message

    def test_blocks_shell_metacharacter_backtick(self, agent):
        """Block command injection via backtick."""
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "echo `cat /etc/passwd`"},
        )
        result = agent.execute(action)
        assert not result.success
        assert "dangerous character" in result.message

    def test_blocks_non_whitelisted_command(self, agent):
        """Block commands not in whitelist."""
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "rm -rf /"},
        )
        result = agent.execute(action)
        assert not result.success
        assert "Command not allowed" in result.message
        assert "rm" in result.message

    def test_allows_whitelisted_command(self, agent):
        """Allow commands in whitelist."""
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "ls -la"},
        )
        result = agent.execute(action)
        assert result.success

    def test_allows_whitelisted_grep(self, agent):
        """Allow grep command from whitelist."""
        # Create a test file
        test_file = agent.workspace / "test.txt"
        test_file.write_text("hello world\nfoo bar\n")
        
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": "grep hello test.txt"},
        )
        result = agent.execute(action)
        assert result.success
        assert "hello" in result.message

    def test_blocks_path_traversal_read(self, agent):
        """Block path traversal in read command."""
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "read", "path": "../../../etc/passwd"},
        )
        result = agent.execute(action)
        assert not result.success
        assert "Invalid path" in result.message

    def test_blocks_path_traversal_write(self, agent):
        """Block path traversal in write command."""
        action = Action(
            type=ActionType.CODE,
            kwargs={
                "command": "write",
                "path": "../../../tmp/malicious.txt",
                "content": "malicious",
            },
        )
        result = agent.execute(action)
        assert not result.success
        assert "Invalid path" in result.message

    def test_research_blocks_non_whitelisted_command(self, agent):
        """Block non-whitelisted commands in research."""
        action = Action(
            type=ActionType.RESEARCH,
            kwargs={"command": "rm"},
            args=["-rf", "/"],
        )
        result = agent.execute(action)
        assert not result.success
        assert "Command not allowed" in result.message

    def test_research_blocks_shell_metacharacters_in_args(self, agent):
        """Block shell metacharacters in research arguments."""
        action = Action(
            type=ActionType.RESEARCH,
            kwargs={"command": "grep"},
            args=["hello; rm -rf /", "file.txt"],
        )
        result = agent.execute(action)
        assert not result.success
        assert "dangerous character" in result.message

    def test_research_allows_whitelisted_command(self, agent):
        """Allow whitelisted commands in research."""
        # Create a test file
        test_file = agent.workspace / "test.txt"
        test_file.write_text("hello world\n")
        
        action = Action(
            type=ActionType.RESEARCH,
            kwargs={"command": "grep"},
            args=["hello", "test.txt"],
        )
        result = agent.execute(action)
        assert result.success

    def test_empty_script_rejected(self, agent):
        """Reject empty script."""
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": ""},
        )
        result = agent.execute(action)
        assert not result.success
        assert "Invalid script" in result.message

    def test_none_script_rejected(self, agent):
        """Reject None script."""
        action = Action(
            type=ActionType.CODE,
            kwargs={"command": "run", "script": None},
        )
        result = agent.execute(action)
        assert not result.success

    def test_allows_all_whitelisted_commands(self, agent):
        """Verify all whitelisted commands work."""
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
            assert "Command not allowed" not in result.message
            assert "dangerous character" not in result.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
