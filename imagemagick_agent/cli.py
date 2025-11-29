"""Command-line interface for ImageMagick Agent."""

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich.table import Table

from .config import load_settings
from .agent import ImageMagickAgent
from .logging_config import setup_logging


console = Console()


def print_banner():
    """Print welcome banner."""
    banner = """
    # ImageMagick Agent 🎨

    An LLM-powered assistant for image editing with ImageMagick.

    **Commands:**
    - Describe what you want to do with your images in natural language
    - Type `info <file>` to get information about an image
    - Type `reset` to clear conversation history
    - Type `help` for more information
    - Type `exit` or `quit` to exit
    """
    console.print(Panel(Markdown(banner), border_style="blue"))


def print_help():
    """Print help information."""
    help_text = """
    ## How to Use

    Simply describe what you want to do with your images in natural language:

    **Examples:**
    - "Resize data/sf-logo.jpeg to 800x600"
    - "Add a 10px red border to output.png"
    - "Convert data/sf-logo.jpeg to PNG format"
    - "Rotate output.png 90 degrees clockwise"
    - "Blur data/white-logo.png with a radius of 5"

    **Tips:**
    - Always specify the input file path
    - The agent will suggest an output filename, or you can specify one
    - Review commands before they execute (unless auto-execute is enabled)
    - Use relative or absolute paths for files

    **Special Commands:**
    - `info <file>` - Get information about an image file
    - `reset` - Clear conversation history and start fresh
    - `help` - Show this help message
    - `exit` or `quit` - Exit the agent
    """
    console.print(Panel(Markdown(help_text), title="Help", border_style="green"))


def print_settings(agent: ImageMagickAgent):
    """Print current settings."""
    table = Table(title="Current Settings", show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    settings = agent.settings
    table.add_row("LLM Provider", settings.llm_provider.value)
    table.add_row("Model", settings.llm_model)
    table.add_row("Auto Execute", "Yes" if settings.auto_execute else "No")
    table.add_row("Max History", str(settings.max_history))

    console.print(table)


def handle_special_commands(user_input: str, agent: ImageMagickAgent) -> bool:
    """Handle special commands like info, reset, help.

    Args:
        user_input: User input
        agent: Agent instance

    Returns:
        True if command was handled, False otherwise
    """
    user_input = user_input.strip().lower()

    if user_input in ["exit", "quit", "q"]:
        console.print("\n[bold blue]👋 Goodbye![/bold blue]\n")
        sys.exit(0)

    if user_input == "help":
        print_help()
        return True

    if user_input == "reset":
        agent.reset_conversation()
        console.print("[green]✓[/green] Conversation history cleared!")
        return True

    if user_input == "settings":
        print_settings(agent)
        return True

    if user_input.startswith("info "):
        file_path = user_input[5:].strip()
        if not agent.check_file_exists(file_path):
            console.print(f"[red]✗[/red] File not found: {file_path}")
        else:
            info = agent.get_image_info(file_path)
            if info:
                console.print(f"[cyan]Image info:[/cyan] {info}")
            else:
                console.print("[red]✗[/red] Could not get image information")
        return True

    return False


def main():
    """Main CLI entry point."""
    # Load settings
    try:
        settings = load_settings()
    except ValueError as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        console.print("\n[yellow]Please set up your .env file with API keys.[/yellow]")
        console.print("Copy .env.example to .env and add your API key.")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error loading settings:[/red] {e}")
        sys.exit(1)

    # Setup logging
    if settings.enable_logging:
        try:
            setup_logging(
                log_dir=settings.log_dir,
                app_log_level=settings.log_level,
                enable_llm_logging=settings.enable_llm_logging,
                enable_execution_logging=settings.enable_execution_logging,
                max_bytes=settings.log_max_bytes,
                backup_count=settings.log_backup_count,
            )
        except Exception as e:
            console.print(f"[yellow]Warning: Could not initialize logging:[/yellow] {e}")

    # Initialize agent
    try:
        agent = ImageMagickAgent(settings)
    except RuntimeError as e:
        console.print(f"[red]Initialization error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error initializing agent:[/red] {e}")
        sys.exit(1)

    # Print banner
    print_banner()
    print_settings(agent)
    console.print()

    # Main loop
    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

            if not user_input.strip():
                continue

            # Handle special commands
            if handle_special_commands(user_input, agent):
                continue

            # Process request
            console.print("[yellow]⏳ Generating command...[/yellow]")
            result = agent.process_request(user_input)

            # Handle errors
            if result.get("error"):
                console.print(f"[red]✗ Error:[/red] {result['error']}")
                continue

            # Handle clarification requests
            if result.get("clarification"):
                console.print(f"\n[bold yellow]Agent:[/bold yellow] {result['clarification']}\n")
                continue

            # Display generated command
            command = result["command"]
            console.print(f"\n[bold green]Generated command:[/bold green]")
            console.print(f"  [white]{command}[/white]\n")

            # Ask for confirmation if needed
            if result["needs_confirmation"]:
                execute = Confirm.ask("Execute this command?", default=False)
                if not execute:
                    console.print("[yellow]Command cancelled.[/yellow]")
                    continue

            # Execute command
            console.print("[yellow]⏳ Executing...[/yellow]")
            exec_result = agent.execute_command(command)

            # Display results
            if exec_result.success:
                console.print("[green]✓ Command executed successfully![/green]")
                if exec_result.output_file:
                    console.print(f"[cyan]Output saved to:[/cyan] {exec_result.output_file}")
                if exec_result.stdout:
                    console.print(f"[dim]{exec_result.stdout}[/dim]")
            else:
                console.print(f"[red]✗ Execution failed:[/red] {exec_result.error_message}")
                if exec_result.stderr:
                    console.print(f"[red]Error details:[/red] {exec_result.stderr}")

        except KeyboardInterrupt:
            console.print("\n\n[bold blue]👋 Goodbye![/bold blue]\n")
            sys.exit(0)
        except EOFError:
            console.print("\n\n[bold blue]👋 Goodbye![/bold blue]\n")
            sys.exit(0)
        except Exception as e:
            console.print(f"\n[red]Unexpected error:[/red] {e}")
            console.print("[yellow]Type 'help' for usage information[/yellow]\n")


if __name__ == "__main__":
    main()
