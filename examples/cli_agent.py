"""Reference CLI agent for HexClamp."""

from pathlib import Path
import subprocess
from typing import Any

from hexclamp.loop import HexClampAgent
from hexclamp.models import Action, Result, ActionType


class CLIAgent(HexClampAgent):
    """Reference CLI agent implementation.

    Supports:
    - CODE actions: File operations (read, write, delete, mkdir)
    - RESEARCH actions: Shell commands (grep, find, etc.)
    - MESSAGE actions: Console output
    """

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
            command = action.kwargs.get("command", "")
            path = action.kwargs.get("path", "")
            content = action.kwargs.get("content", "")

            if command == "read":
                file_path = self.workspace / path
                if not file_path.exists():
                    return Result(success=False, message=f"File not found: {path}")
                text = file_path.read_text()
                return Result(
                    success=True,
                    message=f"Read {len(text)} bytes from {path}",
                    evidence={"path": str(file_path), "content": text},
                )

            elif command == "write":
                file_path = self.workspace / path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
                return Result(success=True, message=f"Wrote to {path}")

            elif command == "delete":
                file_path = self.workspace / path
                if file_path.exists():
                    file_path.unlink()
                    return Result(success=True, message=f"Deleted {path}")
                return Result(success=False, message=f"File not found: {path}")

            elif command == "mkdir":
                dir_path = self.workspace / path
                dir_path.mkdir(parents=True, exist_ok=True)
                return Result(success=True, message=f"Created directory {path}")

            elif command == "run":
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

            return Result(success=False, message=f"Unknown code command: {command}")

        except subprocess.TimeoutExpired:
            return Result(success=False, message="Command timed out")
        except Exception as e:
            return Result(success=False, message=str(e))

    def _execute_research(self, action: Action) -> Result:
        """Execute a research action."""
        try:
            command = action.kwargs.get("command", "echo")
            args = list(action.args)

            result = subprocess.run(
                [command] + args,
                shell=command in ("grep", "find", "rg"),
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )

            return Result(
                success=result.returncode == 0,
                message=f"{command} completed",
                evidence={
                    "returncode": result.returncode,
                    "stdout": result.stdout[:1000],
                    "stderr": result.stderr[:500],
                },
            )

        except subprocess.TimeoutExpired:
            return Result(success=False, message="Research timed out")
        except Exception as e:
            return Result(success=False, message=str(e))

    def _execute_message(self, action: Action) -> Result:
        """Execute a message action."""
        message = action.kwargs.get("message", " ".join(str(a) for a in action.args))
        return Result(success=True, message=message)


def main() -> None:
    """Run CLI agent demo."""
    from hexclamp.loop import HexClampLoop
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        agent = CLIAgent(workspace)
        loop = HexClampLoop(workspace, agent)

        # Create a test file
        (workspace / "test.txt").write_text("Hello, HexClamp!")

        # Enqueue and run
        loop.enqueue("Read test.txt")
        loop.run_cycle()

        status = loop.get_status()
        print(f"Status: {status}")


if __name__ == "__main__":
    main()
