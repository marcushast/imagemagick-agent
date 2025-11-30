# ImageMagick Agent

An LLM-powered conversational agent that helps you edit images using ImageMagick tools through natural language commands.

## Features

- **Natural Language Interface**: Describe what you want in plain English
- **Multiple LLM Providers**: Support for Anthropic Claude, OpenAI, and Google Gemini
- **Safe Execution**: Review generated commands before execution (configurable)
- **Transparent**: Always shows the ImageMagick commands being generated

## Prerequisites

- Python 3.9 or higher
- ImageMagick installed on your system (both v6 and v7 are supported)
  - Ubuntu/Debian: `sudo apt-get install imagemagick`
  - macOS: `brew install imagemagick`
  - Windows: Download from [imagemagick.org](https://imagemagick.org/script/download.php)

**Note:** The agent automatically detects your ImageMagick version and uses the appropriate command (`convert` for v6, `magick` for v7+).

## Installation

### Option 1: Docker (Recommended)

The easiest way to run ImageMagick Agent is using Docker:

1. Clone the repository:
```bash
git clone <repository-url>
cd imagemagick-agent
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your API key(s)
```

3. Run with Docker Compose:
```bash
docker-compose up -d
```

The web interface will be available at `http://localhost:7860`

### Option 2: Local Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd imagemagick-agent
```

2. Install dependencies:
```bash
pip install -e .
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your API key(s)
```

## Usage

Start the agent:
```bash
imagemagick-agent
```

Example conversation:
```
You: Resize data/sf-logo.jpeg to 800x600 pixels
Agent: I'll generate this command: magick data/sf-logo.jpeg -resize 800x600 output.png
Execute this command? [y/N]: y
Agent: ✓ Image resized successfully! Output saved to output.png

You: Add a 10px red border to the output
Agent: I'll generate this command: magick output.png -bordercolor red -border 10 output_bordered.png
Execute this command? [y/N]: y
Agent: ✓ Border added! Output saved to output_bordered.png
```

## Configuration

Edit `.env` to configure:
- `LLM_PROVIDER`: Choose between `anthropic`, `openai`, or `google`
- `LLM_MODEL`: Specific model to use
  - Anthropic: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`
  - OpenAI: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`
  - Google: `gemini-1.5-pro`, `gemini-1.5-flash`
- `AUTO_EXECUTE`: Set to `true` to skip confirmation prompts

**API Keys** (set the one(s) you need):
- `ANTHROPIC_API_KEY`: Get from [console.anthropic.com](https://console.anthropic.com/)
- `OPENAI_API_KEY`: Get from [platform.openai.com](https://platform.openai.com/api-keys)
- `GOOGLE_API_KEY`: Get from [aistudio.google.com](https://aistudio.google.com/app/apikey)

## Development

Install development dependencies:
```bash
pip install -e ".[dev]"
```

Run tests:
```bash
pytest
```

Format code:
```bash
black imagemagick_agent/
ruff check imagemagick_agent/
```

## Docker Usage

### Quick Start

Run with Docker Compose:
```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

Access the web interface at `http://localhost:7860`

### Docker Commands

Build the image manually:
```bash
docker build -t imagemagick-agent:latest .
```

Run without Docker Compose:
```bash
# Run web interface
docker run -d \
  -p 7860:7860 \
  -e ANTHROPIC_API_KEY=your_key_here \
  -e LLM_PROVIDER=anthropic \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  --name imagemagick-agent \
  imagemagick-agent:latest

# Run CLI interface (interactive)
docker run -it --rm \
  -e ANTHROPIC_API_KEY=your_key_here \
  -v $(pwd)/data:/app/data \
  imagemagick-agent:latest \
  imagemagick-agent

# Run log viewer
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/logs:/app/logs:ro \
  imagemagick-agent:latest \
  imagemagick-agent-logs
```

### Environment Variables

Configure via `.env` file or pass directly:

```bash
# Required: At least one API key
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AI...

# LLM Configuration
LLM_PROVIDER=anthropic          # Options: anthropic, openai, google
LLM_MODEL=claude-3-5-sonnet-20241022
AUTO_EXECUTE=false              # true to skip confirmations

# Logging (optional)
ENABLE_LOGGING=true
LOG_LEVEL=INFO
ENABLE_LLM_LOGGING=true
ENABLE_EXECUTION_LOGGING=true
```

### Volume Mounts

- `/app/logs` - Log files (LLM calls, executions, app logs)
- `/app/data` - Input/output images

### Port Mapping

- `7860` - Gradio web interface
- `5000` - Log viewer web interface

### Health Checks

The container includes a health check that monitors the web interface:
```bash
docker ps  # Check health status
```

### Resource Limits

Adjust in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
```
