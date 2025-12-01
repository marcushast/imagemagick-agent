"""Tests for command executor."""

import pytest
from pathlib import Path
from unittest.mock import patch

from imagemagick_agent.executor import CommandExecutor


@pytest.fixture
def executor():
    """Create a CommandExecutor instance."""
    return CommandExecutor()


class TestImageMagickDetection:
    """Test ImageMagick version detection."""

    def test_detect_magick_v7(self):
        """Test detection of ImageMagick 7.x (magick command)."""
        with patch("shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/bin/magick" if cmd == "magick" else None
            executor = CommandExecutor()
            assert executor.imagemagick_command == "magick"

    def test_detect_convert_v6(self):
        """Test detection of ImageMagick 6.x (convert command)."""
        with patch("shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/bin/convert" if cmd == "convert" else None
            executor = CommandExecutor()
            assert executor.imagemagick_command == "convert"

    def test_prefer_magick_over_convert(self):
        """Test that magick is preferred if both exist."""
        with patch("shutil.which") as mock_which:
            # Both commands exist
            mock_which.return_value = "/usr/bin/something"
            executor = CommandExecutor()
            assert executor.imagemagick_command == "magick"

    def test_not_installed_raises_error(self):
        """Test that missing ImageMagick raises RuntimeError."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="ImageMagick is not installed"):
                CommandExecutor()


class TestCommandValidation:
    """Test command validation."""

    def test_valid_magick_command(self, executor):
        """Test that valid magick commands pass validation."""
        command = "magick input.jpg -resize 800x600 output.jpg"
        is_valid, error = executor.validate_command(command)
        assert is_valid
        assert error is None

    def test_valid_convert_command(self, executor):
        """Test that valid convert commands pass validation."""
        command = "convert input.jpg -rotate 90 output.jpg"
        is_valid, error = executor.validate_command(command)
        assert is_valid
        assert error is None

    def test_invalid_command(self, executor):
        """Test that invalid commands fail validation."""
        command = "rm -rf /"
        is_valid, error = executor.validate_command(command)
        assert not is_valid
        assert "not allowed" in error

    def test_dangerous_shell_metacharacters(self, executor):
        """Test that shell metacharacters are rejected."""
        commands = [
            "magick input.jpg | cat",
            "magick input.jpg; rm file.txt",
            "magick input.jpg && echo 'test'",
            "magick $(whoami).jpg output.jpg",
        ]
        for command in commands:
            is_valid, error = executor.validate_command(command)
            assert not is_valid
            assert "metacharacters" in error.lower()

    def test_dangerous_options(self, executor):
        """Test that dangerous options are rejected."""
        command = "magick -script malicious.txt input.jpg output.jpg"
        is_valid, error = executor.validate_command(command)
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_empty_command(self, executor):
        """Test that empty commands are rejected."""
        is_valid, error = executor.validate_command("")
        assert not is_valid
        assert "empty" in error.lower()


class TestOutputPathSanitization:
    """Test output path sanitization."""

    def test_sanitize_simple_filename(self, executor):
        """Test that simple filenames are not changed."""
        command = "magick input.jpg -resize 800x600 output.jpg"
        sanitized = executor.sanitize_output_path(command)
        assert sanitized == command

    def test_sanitize_directory_path(self, executor):
        """Test that directory paths are stripped from output filenames."""
        command = "magick input.jpg -resize 800x600 outputs/output.jpg"
        sanitized = executor.sanitize_output_path(command)
        assert sanitized == "magick input.jpg -resize 800x600 output.jpg"

    def test_sanitize_nested_directory_path(self, executor):
        """Test that nested directory paths are stripped."""
        command = "magick input.jpg -blur 0x8 path/to/outputs/blurred.png"
        sanitized = executor.sanitize_output_path(command)
        assert sanitized == "magick input.jpg -blur 0x8 blurred.png"

    def test_sanitize_relative_path(self, executor):
        """Test that relative paths (./) are stripped."""
        command = "convert input.jpg -rotate 90 ./rotated.jpg"
        sanitized = executor.sanitize_output_path(command)
        assert sanitized == "convert input.jpg -rotate 90 rotated.jpg"

    def test_sanitize_parent_directory_path(self, executor):
        """Test that parent directory paths (../) are stripped."""
        command = "magick input.jpg -border 10 ../parent/output.png"
        sanitized = executor.sanitize_output_path(command)
        assert sanitized == "magick input.jpg -border 10 output.png"


class TestOutputFileExtraction:
    """Test output file extraction."""

    def test_extract_simple_output(self, executor):
        """Test extracting output file from simple command."""
        command = "magick input.jpg output.png"
        output = executor.extract_output_file(command)
        assert output == Path("output.png")

    def test_extract_with_options(self, executor):
        """Test extracting output file with options."""
        command = "magick input.jpg -resize 800x600 -quality 90 output.jpg"
        output = executor.extract_output_file(command)
        assert output == Path("output.jpg")

    def test_extract_with_directory_path(self, executor):
        """Test that directory paths are stripped during extraction."""
        command = "magick input.jpg -resize 800x600 outputs/result.jpg"
        output = executor.extract_output_file(command)
        assert output == Path("result.jpg")

    def test_no_output_file(self, executor):
        """Test when no clear output file exists."""
        command = "identify input.jpg"
        output = executor.extract_output_file(command)
        # identify doesn't typically have an output file
        assert output is None or output == Path("input.jpg")


class TestFileOperations:
    """Test file operations."""

    def test_check_existing_file(self, executor):
        """Test checking for an existing file."""
        # Create a temporary file
        test_file = Path("test_image.txt")
        test_file.write_text("test")

        try:
            assert executor.check_file_exists(str(test_file))
        finally:
            test_file.unlink()

    def test_check_nonexistent_file(self, executor):
        """Test checking for a nonexistent file."""
        assert not executor.check_file_exists("nonexistent_file.jpg")
