"""Main agent orchestration."""

import logging
from typing import Dict, List, Optional
from pathlib import Path

from .config import Settings
from .llm import LLMClient, create_llm_client
from .llm_logger import LLMCallLogger, ExecutionLogger
from .executor import CommandExecutor, ExecutionResult


class ImageMagickAgent:
    """Main agent that orchestrates LLM and command execution."""

    def __init__(self, settings: Settings):
        """Initialize the agent.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = logging.getLogger("imagemagick_agent.agent")

        # Initialize loggers if logging is enabled
        self.llm_logger = None
        self.execution_logger = None

        if settings.enable_logging:
            if settings.enable_llm_logging:
                self.llm_logger = LLMCallLogger(enabled=True)
            if settings.enable_execution_logging:
                self.execution_logger = ExecutionLogger(enabled=True)

        # Initialize executor and LLM client
        self.executor = CommandExecutor(execution_logger=self.execution_logger)
        self.llm_client = create_llm_client(
            settings, self.executor.imagemagick_command, self.llm_logger
        )
        self.conversation_history: List[Dict[str, str]] = []

        self.logger.info(
            f"ImageMagick Agent initialized with {settings.llm_provider.value} "
            f"provider, model={settings.llm_model}"
        )

    def _add_to_history(self, role: str, content: str) -> None:
        """Add a message to conversation history.

        Args:
            role: Message role (user or assistant)
            content: Message content
        """
        self.conversation_history.append({"role": role, "content": content})

        # Trim history if it gets too long
        if len(self.conversation_history) > self.settings.max_history * 2:
            # Keep the most recent messages
            self.conversation_history = self.conversation_history[-self.settings.max_history * 2 :]

    def process_request(self, user_input: str) -> Dict[str, any]:
        """Process a user request.

        Args:
            user_input: User's natural language request

        Returns:
            Dictionary with processing results including:
                - command: Generated command
                - needs_confirmation: Whether confirmation is needed
                - error: Error message if any
        """
        self.logger.info(f"Processing user request: {user_input[:100]}")

        # Generate command using LLM
        try:
            command = self.llm_client.generate_command(user_input, self.conversation_history)
        except Exception as e:
            self.logger.error(f"LLM generation failed: {str(e)}")
            return {
                "error": f"LLM error: {str(e)}",
                "command": None,
                "needs_confirmation": False,
            }

        # Add to history
        self._add_to_history("user", user_input)
        self._add_to_history("assistant", command)

        # Check if it looks like a question or clarification request
        if any(
            indicator in command.lower()
            for indicator in ["?", "could you", "please specify", "which", "what", "unclear"]
        ):
            self.logger.info(f"LLM requested clarification: {command[:100]}")
            if self.llm_logger:
                # Log this as a clarification event
                self.llm_logger.log_clarification(
                    request_id="",  # No specific request ID available here
                    clarification_message=command,
                    user_input=user_input,
                )
            return {
                "command": None,
                "needs_confirmation": False,
                "clarification": command,
            }

        # Validate command
        is_valid, error_msg = self.executor.validate_command(command)
        if not is_valid:
            self.logger.warning(f"Generated invalid command: {command}, error: {error_msg}")
            return {
                "error": f"Generated invalid command: {error_msg}",
                "command": command,
                "needs_confirmation": False,
            }

        self.logger.info(f"Command validated successfully: {command}")
        return {
            "command": command,
            "needs_confirmation": not self.settings.auto_execute,
            "error": None,
        }

    def execute_command(self, command: str) -> ExecutionResult:
        """Execute a validated command.

        Args:
            command: The command to execute

        Returns:
            ExecutionResult with execution details
        """
        self.logger.info(f"Executing command: {command}")
        result = self.executor.execute(command)

        if result.success:
            self.logger.info(
                f"Command executed successfully. Output file: {result.output_file}"
            )
        else:
            self.logger.error(
                f"Command execution failed: {result.error_message or result.stderr}"
            )

        return result

    def check_file_exists(self, file_path: str) -> bool:
        """Check if a file exists.

        Args:
            file_path: Path to check

        Returns:
            True if file exists
        """
        return self.executor.check_file_exists(file_path)

    def get_image_info(self, file_path: str) -> Optional[str]:
        """Get information about an image.

        Args:
            file_path: Path to image file

        Returns:
            Image information or None
        """
        return self.executor.get_image_info(file_path)

    def reset_conversation(self) -> None:
        """Reset the conversation history."""
        self.logger.info("Resetting conversation history")
        self.conversation_history = []
