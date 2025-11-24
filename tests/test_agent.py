"""Tests for agent orchestration."""

import pytest
from unittest.mock import Mock, patch

from imagemagick_agent.agent import ImageMagickAgent
from imagemagick_agent.config import Settings, LLMProvider
from imagemagick_agent.executor import ExecutionResult


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    return Settings(
        llm_provider=LLMProvider.ANTHROPIC,
        anthropic_api_key="test-key",
        auto_execute=False,
    )


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    mock = Mock()
    mock.generate_command = Mock(return_value="magick input.jpg output.png")
    return mock


@pytest.fixture
def agent(mock_settings, mock_llm_client):
    """Create an agent with mocked dependencies."""
    with patch("imagemagick_agent.agent.create_llm_client", return_value=mock_llm_client):
        return ImageMagickAgent(mock_settings)


class TestAgentProcessing:
    """Test agent request processing."""

    def test_process_simple_request(self, agent, mock_llm_client):
        """Test processing a simple request."""
        result = agent.process_request("Resize input.jpg to 800x600")

        assert result["command"] == "magick input.jpg output.png"
        assert result["needs_confirmation"] is True
        assert result["error"] is None
        mock_llm_client.generate_command.assert_called_once()

    def test_process_with_auto_execute(self, agent, mock_llm_client):
        """Test processing with auto_execute enabled."""
        agent.settings.auto_execute = True
        result = agent.process_request("Resize input.jpg to 800x600")

        assert result["needs_confirmation"] is False

    def test_process_clarification(self, agent, mock_llm_client):
        """Test when LLM asks for clarification."""
        mock_llm_client.generate_command.return_value = "Could you specify the output size?"

        result = agent.process_request("Resize the image")

        assert "clarification" in result
        assert result["command"] is None

    def test_conversation_history(self, agent, mock_llm_client):
        """Test that conversation history is maintained."""
        agent.process_request("First request")
        agent.process_request("Second request")

        assert len(agent.conversation_history) == 4  # 2 requests + 2 responses

    def test_reset_conversation(self, agent):
        """Test resetting conversation history."""
        agent.process_request("Test request")
        assert len(agent.conversation_history) > 0

        agent.reset_conversation()
        assert len(agent.conversation_history) == 0


class TestAgentExecution:
    """Test command execution."""

    def test_execute_command(self, agent):
        """Test executing a command."""
        with patch.object(agent.executor, "execute") as mock_execute:
            mock_execute.return_value = ExecutionResult(
                success=True,
                command="magick input.jpg output.jpg",
                stdout="",
                stderr="",
            )

            result = agent.execute_command("magick input.jpg output.jpg")
            assert result.success
            mock_execute.assert_called_once()
