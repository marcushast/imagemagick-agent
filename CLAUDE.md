# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An LLM-powered conversational agent for image editing using ImageMagick. Users describe image transformations in natural language, and the agent generates and executes appropriate ImageMagick CLI commands.

**Key Features:**
- Natural language interface for ImageMagick operations
- Support for multiple LLM providers (Anthropic Claude, OpenAI, Google Gemini)
- Safe command execution with validation
- Configurable auto-execute or confirmation mode

## Development Setup

### Prerequisites
- Python 3.9+
- ImageMagick CLI tools: `sudo apt-get install imagemagick` (Linux) or `brew install imagemagick` (macOS)
- SVG support (optional): `sudo apt-get install librsvg2-bin` (Linux) or `brew install librsvg` (macOS)

### Installation
```bash
pip install -e .              # Install package
pip install -e ".[dev]"       # Install with dev dependencies
cp .env.example .env          # Set up environment
# Edit .env and add API key(s)
```

### Running the Agent
```bash
imagemagick-agent             # Start interactive CLI
imagemagick-agent-web         # Start Gradio web interface
imagemagick-agent-logs        # Start log viewer web server (port 5000)
```

### Testing
```bash
pytest                        # Run all tests
pytest tests/test_executor.py # Run specific test file
pytest -v                     # Verbose output
pytest --cov                  # With coverage report
```

### Code Quality
```bash
black imagemagick_agent/      # Format code
ruff check imagemagick_agent/ # Lint code
```

## Architecture

### Core Components

**1. Agent (`imagemagick_agent/agent.py`)**
- Main orchestrator coordinating LLM and command execution
- Maintains conversation history for context
- Handles request routing and response formatting

**2. LLM Integration (`imagemagick_agent/llm.py`)**
- Abstract `LLMClient` base class for provider implementations
- `AnthropicClient`: Claude API integration
- `OpenAIClient`: OpenAI API integration
- `GoogleClient`: Google Gemini API integration
- System prompt engineering for ImageMagick command generation
- Dynamic prompt generation based on detected ImageMagick version

**3. Command Executor (`imagemagick_agent/executor.py`)**
- Auto-detects ImageMagick version (v6 uses `convert`, v7+ uses `magick`)
- Validates commands before execution (safety critical)
- Blocks dangerous operations: shell metacharacters, script execution, arbitrary file writes
- Executes ImageMagick commands via subprocess
- Extracts output file paths from commands

**4. Configuration (`imagemagick_agent/config.py`)**
- Pydantic-based settings from environment variables
- Provider selection, model configuration, execution mode
- API key validation

**5. CLI Interface (`imagemagick_agent/cli.py`)**
- Rich-based terminal UI with colors and formatting
- Interactive REPL with special commands (`info`, `reset`, `help`)
- Command confirmation flow (unless auto-execute enabled)

**6. Logging Framework (`imagemagick_agent/logging_config.py`, `llm_logger.py`)**
- Structured logging in JSON Lines (.jsonl) format
- **LLM Call Logger**: Tracks all LLM requests/responses with full context
  - Request: provider, model, user input, conversation history, system prompt
  - Response: generated command, response time, token usage, errors
- **Execution Logger**: Audit trail for all ImageMagick command executions
  - Validation: command checks (whitelist, dangerous options, shell injection)
  - Execution: command, success/failure, timing, output files, stdout/stderr
- **Application Logger**: General application events and errors
- **Log Rotation**: Configurable file size limits and backup counts
- **Web Viewer** (`web_logs.py`): Flask-based dashboard for log analysis
  - Real-time log streaming with Server-Sent Events
  - Filtering by provider, time range, success/failure
  - Full-text search across all logs
  - Statistics dashboard (avg response time, token usage, success rates)
  - Expandable log entries with full request/response details

### Data Flow

```
User Input (natural language)
    ↓
Agent.process_request()
    ↓
LLMClient.generate_command() → ImageMagick command string
    ↓
CommandExecutor.validate_command() → Safety checks
    ↓
[Optional] User confirmation prompt
    ↓
CommandExecutor.execute() → subprocess call
    ↓
ExecutionResult → User feedback
```

### Safety Features

The `CommandExecutor` implements multiple safety layers:
- **Command whitelist**: Only allows `magick`, `convert`, `identify`, `mogrify`, `composite`
- **Dangerous option blocking**: Rejects `-script`, `-write`, `@` file references
- **Shell injection prevention**: Blocks `;`, `|`, `&`, `$`, backticks
- **Output path sanitization**: Automatically strips directory paths from output filenames to prevent errors from non-existent directories (e.g., `outputs/image.png` → `image.png`)
- **Timeout protection**: 30-second command timeout
- **Validation before execution**: All commands validated before subprocess call

## Configuration

Environment variables (`.env` file):
- `LLM_PROVIDER`: `anthropic`, `openai`, or `google`
- `LLM_MODEL`: Model identifier
  - Anthropic: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`
  - OpenAI: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`
  - Google: `gemini-1.5-pro`, `gemini-1.5-flash`
- `ANTHROPIC_API_KEY`: Required for Anthropic provider
- `OPENAI_API_KEY`: Required for OpenAI provider
- `GOOGLE_API_KEY`: Required for Google provider
- `AUTO_EXECUTE`: `true` to skip confirmation, `false` for manual approval
- `MAX_HISTORY`: Maximum conversation turns to keep (default: 10)

### Logging Configuration

- `ENABLE_LOGGING`: `true` to enable structured logging (default: `true`)
- `LOG_LEVEL`: Logging level - `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`)
- `LOG_DIR`: Directory for log files (default: `logs`)
- `ENABLE_LLM_LOGGING`: `true` to enable detailed LLM call tracking (default: `true`)
- `ENABLE_EXECUTION_LOGGING`: `true` to enable command execution audit trail (default: `true`)
- `LOG_MAX_BYTES`: Maximum size of each log file before rotation (default: 10000000 / 10MB)
- `LOG_BACKUP_COUNT`: Number of backup log files to keep (default: 5)

**Log Files:**
- `logs/app.log` - General application logs (startup, errors, warnings)
- `logs/llm_calls.jsonl` - Structured LLM request/response logs (JSON Lines)
- `logs/executions.jsonl` - Command execution audit trail (JSON Lines)

**Viewing Logs:**
```bash
# Start web-based log viewer
imagemagick-agent-logs

# With custom port and log directory
imagemagick-agent-logs --port 8080 --log-dir /path/to/logs

# Open browser to http://localhost:5000
```

## Testing Images

Test images in `data/` directory:
- `sf-logo.jpeg` - JPEG source image
- `white-logo.png` - PNG with transparency
- `output*.png` - Example generated outputs

## Common ImageMagick Operations

The agent is trained to generate commands for:
- Resizing: `-resize WIDTHxHEIGHT`
- Cropping: `-crop WIDTHxHEIGHT+X+Y`
- Rotation: `-rotate DEGREES`
- Borders: `-bordercolor COLOR -border SIZE`
- Blur/Sharpen: `-blur RADIUS`, `-sharpen RADIUS`
- Format conversion: Input `file.jpg` → Output `file.png`
- Compositing: Overlay images with `-composite`
- Color adjustments: `-colorspace`, `-modulate`, `-brightness-contrast`
