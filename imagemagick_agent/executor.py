"""ImageMagick command executor with validation and safety checks."""

import logging
import re
import shutil
import subprocess
import time
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

    def __init__(self, execution_logger=None, session_id: Optional[str] = None):
        """Initialize the executor.

        Args:
            execution_logger: Optional ExecutionLogger for audit trail
            session_id: Optional session ID for tracking
        """
        self.imagemagick_command = self._detect_imagemagick_command()
        self.execution_logger = execution_logger
        self.session_id = session_id
        self.logger = logging.getLogger("imagemagick_agent.executor")
        self.logger.info(f"CommandExecutor initialized with {self.imagemagick_command} command")

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

        checks = {
            "not_empty": True,
            "allowed_command": True,
            "no_dangerous_options": True,
            "no_shell_injection": True,
        }
        error_message = None

        if not parts:
            checks["not_empty"] = False
            error_message = "Empty command"
            self._log_validation(command, False, checks, error_message)
            return False, error_message

        # Check if it's an allowed ImageMagick command
        base_command = parts[0]
        if base_command not in self.ALLOWED_COMMANDS:
            checks["allowed_command"] = False
            error_message = f"Command '{base_command}' is not allowed. Use: {', '.join(self.ALLOWED_COMMANDS)}"
            self._log_validation(command, False, checks, error_message)
            return False, error_message

        # Check for dangerous options
        for part in parts:
            for dangerous in self.DANGEROUS_OPTIONS:
                if dangerous in part:
                    checks["no_dangerous_options"] = False
                    error_message = f"Dangerous option detected: {dangerous}"
                    self._log_validation(command, False, checks, error_message)
                    return False, error_message

        # Check for shell injection attempts
        if any(char in command for char in [";", "|", "&", "$", "`"]):
            checks["no_shell_injection"] = False
            error_message = "Shell metacharacters not allowed"
            self._log_validation(command, False, checks, error_message)
            return False, error_message

        self._log_validation(command, True, checks, None)
        return True, None

    def _log_validation(
        self, command: str, passed: bool, checks: dict, error_message: Optional[str]
    ) -> None:
        """Log validation results.

        Args:
            command: Command that was validated
            passed: Whether validation passed
            checks: Dictionary of check results
            error_message: Error message if validation failed
        """
        if self.execution_logger:
            self.execution_logger.log_validation(
                command, passed, checks, error_message, session_id=self.session_id
            )

        if passed:
            self.logger.debug(f"Command validation passed: {command}")
        else:
            self.logger.warning(f"Command validation failed: {command} - {error_message}")

    def sanitize_output_path(self, command: str) -> str:
        """Sanitize command by removing directory paths from output filenames.

        Args:
            command: The ImageMagick command

        Returns:
            Sanitized command with only filenames (no directory paths)
        """
        parts = command.split()

        # Find the output file (last non-option argument)
        for i in range(len(parts) - 1, 0, -1):
            part = parts[i]
            if not part.startswith("-") and part != parts[0] and "." in part:
                # This is likely the output file
                original_path = part
                sanitized_path = Path(part).name  # Extract just the filename

                if original_path != sanitized_path:
                    # Replace the path in the command
                    parts[i] = sanitized_path
                    self.logger.info(
                        f"Sanitized output path: '{original_path}' -> '{sanitized_path}'"
                    )
                break

        return " ".join(parts)

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
                    # Extract just the filename, strip any directory paths
                    # This prevents issues with non-existent directories
                    output_path = Path(part)
                    return Path(output_path.name)

        return None

    def execute(self, command: str) -> ExecutionResult:
        """Execute an ImageMagick command.

        Args:
            command: The command to execute

        Returns:
            ExecutionResult with execution details
        """
        start_time = time.time()

        # Sanitize output path (remove directory paths from output filenames)
        sanitized_command = self.sanitize_output_path(command)

        # Validate command
        is_valid, error_msg = self.validate_command(sanitized_command)
        if not is_valid:
            result = ExecutionResult(
                success=False,
                command=sanitized_command,
                stdout="",
                stderr="",
                error_message=f"Command validation failed: {error_msg}",
            )
            self._log_execution(result, 0)
            return result

        # Extract output file
        output_file = self.extract_output_file(sanitized_command)

        # Execute command
        try:
            subprocess_result = subprocess.run(
                sanitized_command,
                shell=True,  # Safe because we validated the command
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )

            execution_time_ms = (time.time() - start_time) * 1000

            if subprocess_result.returncode == 0:
                result = ExecutionResult(
                    success=True,
                    command=sanitized_command,
                    stdout=subprocess_result.stdout,
                    stderr=subprocess_result.stderr,
                    output_file=output_file,
                )
                self._log_execution(result, execution_time_ms)
                return result
            else:
                result = ExecutionResult(
                    success=False,
                    command=sanitized_command,
                    stdout=subprocess_result.stdout,
                    stderr=subprocess_result.stderr,
                    error_message=f"Command failed with exit code {subprocess_result.returncode}",
                )
                self._log_execution(result, execution_time_ms)
                return result

        except subprocess.TimeoutExpired:
            execution_time_ms = (time.time() - start_time) * 1000
            result = ExecutionResult(
                success=False,
                command=sanitized_command,
                stdout="",
                stderr="",
                error_message="Command timed out after 30 seconds",
            )
            self._log_execution(result, execution_time_ms)
            return result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            result = ExecutionResult(
                success=False,
                command=sanitized_command,
                stdout="",
                stderr="",
                error_message=f"Execution error: {str(e)}",
            )
            self._log_execution(result, execution_time_ms)
            return result

    def _log_execution(self, result: ExecutionResult, execution_time_ms: float) -> None:
        """Log execution results.

        Args:
            result: Execution result to log
            execution_time_ms: Execution time in milliseconds
        """
        if self.execution_logger:
            self.execution_logger.log_execution(
                command=result.command,
                success=result.success,
                execution_time_ms=execution_time_ms,
                output_file=str(result.output_file) if result.output_file else None,
                stdout=result.stdout,
                stderr=result.stderr,
                error_message=result.error_message,
                session_id=self.session_id,
            )

        if result.success:
            self.logger.info(
                f"Command executed successfully in {execution_time_ms:.2f}ms: {result.command}"
            )
        else:
            self.logger.error(
                f"Command execution failed after {execution_time_ms:.2f}ms: "
                f"{result.command} - {result.error_message}"
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

    def set_session_id(self, session_id: str) -> None:
        """Set the current session ID.

        Args:
            session_id: The new session ID
        """
        self.session_id = session_id
