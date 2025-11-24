"""LLM integration for generating ImageMagick commands."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from anthropic import Anthropic
from openai import OpenAI
import google.generativeai as genai

from .config import Settings, LLMProvider


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
    def generate_command(self, user_message: str, history: List[Dict[str, str]]) -> str:
        """Generate an ImageMagick command based on user input.

        Args:
            user_message: The user's request
            history: List of previous messages in the conversation

        Returns:
            Generated ImageMagick command as a string
        """
        pass


class AnthropicClient(LLMClient):
    """Anthropic Claude LLM client."""

    def __init__(self, api_key: str, model: str, system_prompt: str):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.system_prompt = system_prompt

    def generate_command(self, user_message: str, history: List[Dict[str, str]]) -> str:
        """Generate command using Claude."""
        messages = history + [{"role": "user", "content": user_message}]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self.system_prompt,
            messages=messages,
        )

        return response.content[0].text.strip()


class OpenAIClient(LLMClient):
    """OpenAI LLM client."""

    def __init__(self, api_key: str, model: str, system_prompt: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.system_prompt = system_prompt

    def generate_command(self, user_message: str, history: List[Dict[str, str]]) -> str:
        """Generate command using OpenAI."""
        messages = [{"role": "system", "content": self.system_prompt}] + history
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=1024,
        )

        return response.choices[0].message.content.strip()


class GoogleClient(LLMClient):
    """Google Gemini LLM client."""

    def __init__(self, api_key: str, model: str, system_prompt: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
        )
        self.chat = None

    def generate_command(self, user_message: str, history: List[Dict[str, str]]) -> str:
        """Generate command using Google Gemini."""
        # Convert history to Gemini format
        gemini_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        # Create or update chat session
        if self.chat is None or len(history) == 0:
            self.chat = self.model.start_chat(history=gemini_history)

        # Send message and get response
        response = self.chat.send_message(user_message)
        return response.text.strip()


def create_llm_client(settings: Settings, imagemagick_command: str = "magick") -> LLMClient:
    """Create an LLM client based on settings.

    Args:
        settings: Application settings
        imagemagick_command: The ImageMagick command to use in prompts

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
        )
    elif settings.llm_provider == LLMProvider.OPENAI:
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
            system_prompt=system_prompt,
        )
    elif settings.llm_provider == LLMProvider.GOOGLE:
        return GoogleClient(
            api_key=settings.google_api_key,
            model=settings.llm_model,
            system_prompt=system_prompt,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
