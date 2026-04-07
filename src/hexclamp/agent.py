"""Reference CLI agent implementation."""

import logging
import subprocess
from pathlib import Path

from hexclamp.loop import HexClampAgent
from hexclamp.models import Action, ActionType, Result

logger = logging.getLogger(__name__)


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
                if path.exists():
                    content = path.read_text()
                    return Result(
                        success=True,
                        message=f"Read {len(content)} bytes",
                        evidence={"path": str(path), "content": content},
                    )
                return Result(success=False, message=f"File not found: {path}")

            elif cmd == "write":
                path = self.workspace / action.kwargs.get("path", "")
                content = action.kwargs.get("content", "")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                return Result(success=True, message=f"Wrote to {path}")

            elif cmd == "run":
                script = action.kwargs.get("script", "")
                result = subprocess.run(
                    script,
                    shell=True,
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

            result = subprocess.run(
                [cmd] + list(action.args),
                shell=cmd in ("grep", "find", "rg"),
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
