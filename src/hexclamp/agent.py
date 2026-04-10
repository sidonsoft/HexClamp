"""Reference CLI agent implementation."""

import logging
import shlex
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from hexclamp.models import Action, ActionType, Result

logger = logging.getLogger(__name__)

# Whitelist of allowed commands for security
ALLOWED_SHELL_COMMANDS = frozenset(["grep", "find", "rg", "ls", "cat", "head", "tail", "wc"])

class HexClampAgent(ABC):
    """Abstract agent interface."""

    @abstractmethod
    def execute(self, action: Action) -> Result:
        """Execute an action and return result."""
        pass

    @abstractmethod
    def get_workspace(self) -> Path:
        """Get the agent's workspace path."""
        pass

class CLIAgent(HexClampAgent):
    """Reference CLI agent for testing and demonstration."""

    def __init__(self, workspace: Path | str | None = None) -> None:
        """Initialize CLI agent."""
        self.workspace = Path(workspace) if workspace else Path.cwd()

    def get_workspace(self) -> Path:
        """Get workspace path."""
        return self.workspace

    def execute(self, action: Action) -> Result:
        """Execute an action."""
        if action.type == ActionType.CODE:
            return self._execute_code(action)
        elif action.type == ActionType.RESEARCH:
            return self._execute_research(action)
        elif action.type == ActionType.MESSAGE:
            return self._execute_message(action)
        else:
            return Result(
                success=False,
                message=f"Unknown action type: {action.type}",
            )

    def _execute_code(self, action: Action) -> Result:
        """Execute a code action."""
        try:
            cmd = action.kwargs.get("command", "echo")

            if cmd == "read":
                path = self.workspace / action.kwargs.get("path", "")
                # Prevent path traversal
                try:
                    path = path.resolve()
                    path.relative_to(self.workspace.resolve())
                except (ValueError, RuntimeError):
                    return Result(success=False, message="Invalid path: outside workspace")
                if path.exists():
                    content = path.read_text()
                    return Result(
                        success=True,
                        message=f"Read {len(content)} bytes",
                        evidence={"path": str(path), "content": content},
                    )
                return Result(success=False, message=f"File not found: {path}")

            elif cmd == "write":
                path_str = action.kwargs.get("path", "")
                # Prevent path traversal
                path = self.workspace / path_str
                try:
                    path = path.resolve()
                    path.relative_to(self.workspace.resolve())
                except (ValueError, RuntimeError):
                    return Result(success=False, message="Invalid path: outside workspace")
                content = action.kwargs.get("content", "")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                return Result(success=True, message=f"Wrote to {path}")

            elif cmd == "run":
                script = action.kwargs.get("script", "")
                # SECURITY: Validate script input - no shell metacharacters
                if not script or not isinstance(script, str):
                    return Result(success=False, message="Invalid script: must be non-empty string")
                # Block dangerous shell metacharacters
                dangerous_chars = [";", "|", "&", "$", "`", "(", ")", "<", ">", "\\", "\n", "\r"]
                for char in dangerous_chars:
                    if char in script:
                        return Result(
                            success=False,
                            message=f"Security error: script contains dangerous character '{char}'",
                        )
                # Parse command safely using shlex
                try:
                    cmd_parts = shlex.split(script)
                except ValueError as e:
                    return Result(success=False, message=f"Invalid script syntax: {e}")
                if not cmd_parts:
                    return Result(success=False, message="Empty command")
                # SECURITY: Only allow whitelisted commands
                base_cmd = cmd_parts[0]
                if base_cmd not in ALLOWED_SHELL_COMMANDS:
                    return Result(
                        success=False,
                        message=f"Command not allowed: {base_cmd}. Allowed: {', '.join(sorted(ALLOWED_SHELL_COMMANDS))}",
                    )
                # Execute safely without shell=True
                result = subprocess.run(
                    cmd_parts,
                    shell=False,
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return Result(
                    success=result.returncode == 0,
                    message=result.stdout[:500] if result.stdout else result.stderr[:500],
                    evidence={
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    },
                )

            return Result(success=False, message=f"Unknown code command: {cmd}")

        except subprocess.TimeoutExpired:
            return Result(success=False, message="Command timed out")
        except Exception as e:
            logger.exception("Code execution failed")
            return Result(success=False, message=str(e))

    def _execute_research(self, action: Action) -> Result:
        """Execute a research action."""
        try:
            cmd = action.kwargs.get("command", "echo")
            # SECURITY: Validate command is in whitelist
            if cmd not in ALLOWED_SHELL_COMMANDS:
                return Result(
                    success=False,
                    message=f"Command not allowed: {cmd}. Allowed: {', '.join(sorted(ALLOWED_SHELL_COMMANDS))}",
                )
            # SECURITY: Validate and sanitize arguments
            args = []
            for arg in action.args:
                if not isinstance(arg, str):
                    arg = str(arg)
                # Block dangerous shell metacharacters in arguments
                dangerous_chars = [";", "|", "&", "$", "`", "(", ")", "<", ">", "\\", "\n", "\r"]
                for char in dangerous_chars:
                    if char in arg:
                        return Result(
                            success=False,
                            message=f"Security error: argument contains dangerous character '{char}'",
                        )
                args.append(arg)
            # Execute safely without shell=True
            result = subprocess.run(
                [cmd] + args,
                shell=False,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )

            return Result(
                success=result.returncode == 0,
                message=f"{cmd} completed",
                evidence={
                    "returncode": result.returncode,
                    "stdout": result.stdout[:1000],
                    "stderr": result.stderr[:500],
                },
            )

        except subprocess.TimeoutExpired:
            return Result(success=False, message="Research timed out")
        except Exception as e:
            logger.exception("Research execution failed")
            return Result(success=False, message=str(e))

    def _execute_message(self, action: Action) -> Result:
        """Execute a message action."""
        message = action.kwargs.get("message", " ".join(str(a) for a in action.args))
        logger.info(f"Message: {message}")
        return Result(success=True, message=message)
