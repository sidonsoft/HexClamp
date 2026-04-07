"""HexClamp CLI."""

import argparse
import logging
import sys
from pathlib import Path

from hexclamp.agent import CLIAgent
from hexclamp.loop import HexClampLoop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def init(args: argparse.Namespace) -> int:
    """Initialize workspace."""
    workspace = Path(args.workspace)
    hexclamp_dir = workspace / ".hexclamp"

    if hexclamp_dir.exists() and not args.force:
        logger.error("Workspace already initialized. Use --force to reinitialize.")
        return 1

    hexclamp_dir.mkdir(parents=True, exist_ok=True)
    (hexclamp_dir / "events").mkdir(exist_ok=True)
    (hexclamp_dir / "loops").mkdir(exist_ok=True)
    (hexclamp_dir / "results").mkdir(exist_ok=True)

    logger.info(f"Initialized workspace at {workspace}")
    return 0


def enqueue(args: argparse.Namespace) -> int:
    """Enqueue a task."""

    workspace = Path(args.workspace)
    agent = CLIAgent(workspace)
    loop = HexClampLoop(workspace, agent)

    task_loop = loop.enqueue(args.task, source=args.source)
    logger.info(f"Enqueued task: {task_loop.id}")
    return 0


def run(args: argparse.Namespace) -> int:
    """Run loop cycle."""
    workspace = Path(args.workspace)
    agent = CLIAgent(workspace)
    loop = HexClampLoop(workspace, agent)

    logger.info("Running cycle...")
    processed = loop.run_cycle()
    logger.info(f"Processed {len(processed)} loops")
    return 0


def status(args: argparse.Namespace) -> int:
    """Show status."""
    workspace = Path(args.workspace)
    agent = CLIAgent(workspace)
    loop = HexClampLoop(workspace, agent)

    status = loop.get_status()
    print(f"Total loops: {status['total']}")
    print(f"  Open: {status['open']}")
    print(f"  In Progress: {status['in_progress']}")
    print(f"  Completed: {status['completed']}")
    print(f"  Failed: {status['failed']}")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="HexClamp - Agent Integration Platform")
    parser.add_argument("--workspace", default=".", help="Workspace path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize workspace")
    p_init.add_argument("--force", action="store_true", help="Force reinitialize")

    # enqueue
    p_enqueue = subparsers.add_parser("enqueue", help="Enqueue a task")
    p_enqueue.add_argument("task", help="Task description")
    p_enqueue.add_argument("--source", default="cli", help="Task source")

    # run
    subparsers.add_parser("run", help="Run cycle")

    # status
    subparsers.add_parser("status", help="Show status")

    args = parser.parse_args()

    commands = {
        "init": init,
        "enqueue": enqueue,
        "run": run,
        "status": status,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
