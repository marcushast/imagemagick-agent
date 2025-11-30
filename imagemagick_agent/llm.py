"""LLM integration for generating ImageMagick commands."""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from anthropic import Anthropic
from openai import OpenAI
import google.generativeai as genai

from .config import Settings, LLMProvider
from .llm_logger import LLMCallLogger


def get_system_prompt(imagemagick_command: str = "magick") -> str:
    """Generate system prompt with the correct ImageMagick command.

    Args:
        imagemagick_command: The base command to use ('magick' or 'convert')

    Returns:
        System prompt string
    """
    return f"""You are an expert ImageMagick assistant. Your job is to generate ImageMagick CLI commands based on user requests.

Key guidelines:
1. Generate valid ImageMagick commands using the '{imagemagick_command}' CLI tool
2. Always specify input and output file paths clearly
3. Use common ImageMagick operations: -resize, -crop, -rotate, -blur, -sharpen, -border, -colorspace, etc.
4. Respond with ONLY the command to execute, no explanations or markdown
5. If the user's request is unclear, ask for clarification
6. Consider the file format when choosing operations
7. Use appropriate output file names (e.g., output.png, resized.jpg, etc.)

Example commands:
- Resize: {imagemagick_command} input.jpg -resize 800x600 output.jpg
- Add border: {imagemagick_command} input.jpg -bordercolor black -border 10 output.jpg
- Rotate: {imagemagick_command} input.jpg -rotate 90 output.jpg
- Convert format: {imagemagick_command} input.jpg output.png
- Blur: {imagemagick_command} input.jpg -blur 0x8 output.jpg
- Compose images: {imagemagick_command} background.jpg logo.png -gravity center -composite output.jpg

The user will provide image file paths and describe what they want to do."""


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def generate_command(self, user_message: str, history: List[Dict[str, str]], session_id: Optional[str] = None) -> str:
        """Generate an ImageMagick command based on user input.

        Args:
            user_message: The user's request
            history: List of previous messages in the conversation
            session_id: Optional session ID for tracking

        Returns:
            Generated ImageMagick command as a string
        """
        pass


class AnthropicClient(LLMClient):
    """Anthropic Claude LLM client."""

    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        llm_logger: Optional[LLMCallLogger] = None,
    ):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.system_prompt = system_prompt
        self.llm_logger = llm_logger
        self.logger = logging.getLogger("imagemagick_agent.llm")

    def generate_command(self, user_message: str, history: List[Dict[str, str]], session_id: Optional[str] = None) -> str:
        """Generate command using Claude."""
        messages = history + [{"role": "user", "content": user_message}]

        # Log request
        request_id = None
        if self.llm_logger:
            request_id = self.llm_logger.log_request(
                provider="anthropic",
                model=self.model,
                user_input=user_message,
                conversation_history=history,
                system_prompt=self.system_prompt,
                session_id=session_id,
            )

        start_time = time.time()
        error = None

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=messages,
            )

            command = response.content[0].text.strip()
            response_time_ms = (time.time() - start_time) * 1000

            # Log successful response
            if self.llm_logger:
                self.llm_logger.log_response(
                    request_id=request_id,
                    generated_command=command,
                    response_time_ms=response_time_ms,
                    token_usage={
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                    session_id=session_id,
                )

            self.logger.debug(
                f"Generated command via Anthropic in {response_time_ms:.2f}ms: {command[:100]}"
            )

            return command

        except Exception as e:
            error_msg = str(e)
            response_time_ms = (time.time() - start_time) * 1000

            self.logger.error(f"Anthropic LLM generation failed: {error_msg}")

            # Log error response
            if self.llm_logger:
                self.llm_logger.log_response(
                    request_id=request_id,
                    generated_command="",
                    response_time_ms=response_time_ms,
                    error=error_msg,
                    session_id=session_id,
                )

            raise


class OpenAIClient(LLMClient):
    """OpenAI LLM client."""

    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        llm_logger: Optional[LLMCallLogger] = None,
    ):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.system_prompt = system_prompt
        self.llm_logger = llm_logger
        self.logger = logging.getLogger("imagemagick_agent.llm")

    def generate_command(self, user_message: str, history: List[Dict[str, str]], session_id: Optional[str] = None) -> str:
        """Generate command using OpenAI."""
        messages = [{"role": "system", "content": self.system_prompt}] + history
        messages.append({"role": "user", "content": user_message})

        # Log request
        request_id = None
        if self.llm_logger:
            request_id = self.llm_logger.log_request(
                provider="openai",
                model=self.model,
                user_input=user_message,
                conversation_history=history,
                system_prompt=self.system_prompt,
                session_id=session_id,
            )

        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1024,
            )

            command = response.choices[0].message.content.strip()
            response_time_ms = (time.time() - start_time) * 1000

            # Log successful response
            if self.llm_logger:
                token_usage = {}
                if hasattr(response, "usage") and response.usage:
                    token_usage = {
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens,
                    }

                self.llm_logger.log_response(
                    request_id=request_id,
                    generated_command=command,
                    response_time_ms=response_time_ms,
                    token_usage=token_usage,
                    session_id=session_id,
                )

            self.logger.debug(
                f"Generated command via OpenAI in {response_time_ms:.2f}ms: {command[:100]}"
            )

            return command

        except Exception as e:
            error_msg = str(e)
            response_time_ms = (time.time() - start_time) * 1000

            self.logger.error(f"OpenAI LLM generation failed: {error_msg}")

            # Log error response
            if self.llm_logger:
                self.llm_logger.log_response(
                    request_id=request_id,
                    generated_command="",
                    response_time_ms=response_time_ms,
                    error=error_msg,
                    session_id=session_id,
                )

            raise


class GoogleClient(LLMClient):
    """Google Gemini LLM client."""

    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        llm_logger: Optional[LLMCallLogger] = None,
    ):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
        )
        self.system_prompt = system_prompt
        self.chat = None
        self.llm_logger = llm_logger
        self.logger = logging.getLogger("imagemagick_agent.llm")

    def generate_command(self, user_message: str, history: List[Dict[str, str]], session_id: Optional[str] = None) -> str:
        """Generate command using Google Gemini."""
        # Convert history to Gemini format
        gemini_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        # Log request
        request_id = None
        if self.llm_logger:
            request_id = self.llm_logger.log_request(
                provider="google",
                model=self.model.model_name,
                user_input=user_message,
                conversation_history=history,
                system_prompt=self.system_prompt,
                session_id=session_id,
            )

        start_time = time.time()

        try:
            # Create or update chat session
            if self.chat is None or len(history) == 0:
                self.chat = self.model.start_chat(history=gemini_history)

            # Send message and get response
            response = self.chat.send_message(user_message)
            command = response.text.strip()
            response_time_ms = (time.time() - start_time) * 1000

            # Log successful response
            if self.llm_logger:
                token_usage = {}
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    token_usage = {
                        "input_tokens": response.usage_metadata.prompt_token_count,
                        "output_tokens": response.usage_metadata.candidates_token_count,
                    }

                self.llm_logger.log_response(
                    request_id=request_id,
                    generated_command=command,
                    response_time_ms=response_time_ms,
                    token_usage=token_usage,
                    session_id=session_id,
                )

            self.logger.debug(
                f"Generated command via Google in {response_time_ms:.2f}ms: {command[:100]}"
            )

            return command

        except Exception as e:
            error_msg = str(e)
            response_time_ms = (time.time() - start_time) * 1000

            self.logger.error(f"Google LLM generation failed: {error_msg}")

            # Log error response
            if self.llm_logger:
                self.llm_logger.log_response(
                    request_id=request_id,
                    generated_command="",
                    response_time_ms=response_time_ms,
                    error=error_msg,
                    session_id=session_id,
                )

            raise


def create_llm_client(
    settings: Settings,
    imagemagick_command: str = "magick",
    llm_logger: Optional[LLMCallLogger] = None,
) -> LLMClient:
    """Create an LLM client based on settings.

    Args:
        settings: Application settings
        imagemagick_command: The ImageMagick command to use in prompts
        llm_logger: Optional LLM call logger for tracking requests/responses

    Returns:
        Configured LLM client

    Raises:
        ValueError: If provider is not supported
    """
    system_prompt = get_system_prompt(imagemagick_command)

    if settings.llm_provider == LLMProvider.ANTHROPIC:
        return AnthropicClient(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
            system_prompt=system_prompt,
            llm_logger=llm_logger,
        )
    elif settings.llm_provider == LLMProvider.OPENAI:
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
            system_prompt=system_prompt,
            llm_logger=llm_logger,
        )
    elif settings.llm_provider == LLMProvider.GOOGLE:
        return GoogleClient(
            api_key=settings.google_api_key,
            model=settings.llm_model,
            system_prompt=system_prompt,
            llm_logger=llm_logger,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
