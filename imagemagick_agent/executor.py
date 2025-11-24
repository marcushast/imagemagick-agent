"""ImageMagick command executor with validation and safety checks."""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """Result of command execution."""

    success: bool
    command: str
    stdout: str
    stderr: str
    output_file: Optional[Path] = None
    error_message: Optional[str] = None


class CommandExecutor:
    """Executes ImageMagick commands safely."""

    # Allowed ImageMagick commands
    ALLOWED_COMMANDS = {"magick", "convert", "identify", "mogrify", "composite"}

    # Dangerous options that could cause issues
    DANGEROUS_OPTIONS = {
        "-script",  # Script execution
        "-write",  # Writing to arbitrary locations
        "@",  # File reference that could be exploited
    }

    def __init__(self):
        """Initialize the executor."""
        self.imagemagick_command = self._detect_imagemagick_command()

    def _detect_imagemagick_command(self) -> str:
        """Detect which ImageMagick command is available.

        Returns:
            The base command to use ('magick' for v7+ or 'convert' for v6)

        Raises:
            RuntimeError: If ImageMagick is not installed
        """
        # Check for ImageMagick 7.x (uses 'magick' command)
        if shutil.which("magick"):
            return "magick"

        # Check for ImageMagick 6.x (uses 'convert', 'identify', etc.)
        if shutil.which("convert"):
            return "convert"

        # Not found
        raise RuntimeError(
            "ImageMagick is not installed. Please install it:\n"
            "  Ubuntu/Debian: sudo apt-get install imagemagick\n"
            "  macOS: brew install imagemagick\n"
            "  Windows: https://imagemagick.org/script/download.php"
        )

    def validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Validate that a command is safe to execute.

        Args:
            command: The command to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        parts = command.strip().split()

        if not parts:
            return False, "Empty command"

        # Check if it's an allowed ImageMagick command
        base_command = parts[0]
        if base_command not in self.ALLOWED_COMMANDS:
            return False, f"Command '{base_command}' is not allowed. Use: {', '.join(self.ALLOWED_COMMANDS)}"

        # Check for dangerous options
        for part in parts:
            for dangerous in self.DANGEROUS_OPTIONS:
                if dangerous in part:
                    return False, f"Dangerous option detected: {dangerous}"

        # Check for shell injection attempts
        if any(char in command for char in [";", "|", "&", "$", "`"]):
            return False, "Shell metacharacters not allowed"

        return True, None

    def extract_output_file(self, command: str) -> Optional[Path]:
        """Extract the output file path from a command.

        Args:
            command: The ImageMagick command

        Returns:
            Path to output file if found, None otherwise
        """
        parts = command.split()

        # For most ImageMagick commands, the last argument is the output file
        # unless it's an option starting with -
        for part in reversed(parts):
            if not part.startswith("-") and not part == parts[0]:
                # This might be the output file
                if "." in part:  # Has an extension
                    return Path(part)

        return None

    def execute(self, command: str) -> ExecutionResult:
        """Execute an ImageMagick command.

        Args:
            command: The command to execute

        Returns:
            ExecutionResult with execution details
        """
        # Validate command
        is_valid, error_msg = self.validate_command(command)
        if not is_valid:
            return ExecutionResult(
                success=False,
                command=command,
                stdout="",
                stderr="",
                error_message=f"Command validation failed: {error_msg}",
            )

        # Extract output file
        output_file = self.extract_output_file(command)

        # Execute command
        try:
            result = subprocess.run(
                command,
                shell=True,  # Safe because we validated the command
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )

            if result.returncode == 0:
                return ExecutionResult(
                    success=True,
                    command=command,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    output_file=output_file,
                )
            else:
                return ExecutionResult(
                    success=False,
                    command=command,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    error_message=f"Command failed with exit code {result.returncode}",
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                command=command,
                stdout="",
                stderr="",
                error_message="Command timed out after 30 seconds",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                command=command,
                stdout="",
                stderr="",
                error_message=f"Execution error: {str(e)}",
            )

    def check_file_exists(self, file_path: str) -> bool:
        """Check if a file exists.

        Args:
            file_path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        return Path(file_path).exists()

    def get_image_info(self, file_path: str) -> Optional[str]:
        """Get information about an image file.

        Args:
            file_path: Path to image file

        Returns:
            Image information string or None if failed
        """
        if not self.check_file_exists(file_path):
            return None

        try:
            result = subprocess.run(
                ["identify", file_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None
