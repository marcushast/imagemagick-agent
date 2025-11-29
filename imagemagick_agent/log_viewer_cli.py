"""
Command-line interface for the log viewer web server.
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console

from .web_logs import run_server

console = Console()


def main():
    """Main entry point for the log viewer CLI."""
    parser = argparse.ArgumentParser(
        description="ImageMagick Agent Log Viewer - Web interface for viewing and analyzing logs"
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Directory containing log files (default: logs)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run the web server on (default: 5000)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode",
    )

    args = parser.parse_args()

    # Check if log directory exists
    if not args.log_dir.exists():
        console.print(
            f"[yellow]Warning:[/yellow] Log directory '{args.log_dir}' does not exist yet."
        )
        console.print("[yellow]It will be created when the agent starts logging.[/yellow]\n")

    try:
        run_server(log_dir=args.log_dir, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        console.print("\n[cyan]Shutting down log viewer...[/cyan]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
