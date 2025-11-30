# Docker Setup Guide

## Prerequisites
Make sure you have Docker permissions:
```bash
# Add yourself to docker group (one-time setup)
sudo usermod -aG docker $USER
newgrp docker  # Or log out and back in
```

## Quick Start

### Option 1: Using Docker Compose (Recommended)
```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

The web interface will be available at:
- **Gradio UI**: http://localhost:7860
- **Log Viewer**: http://localhost:5000 (if enabled)

### Option 2: Using Docker CLI
```bash
# Build the image
docker build -t imagemagick-agent:latest .

# Run the web interface
docker run -d \
  --name imagemagick-agent \
  -p 7860:7860 \
  -p 5000:5000 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  imagemagick-agent:latest

# View logs
docker logs -f imagemagick-agent

# Stop the container
docker stop imagemagick-agent
docker rm imagemagick-agent
```

## Configuration

### Environment Variables
The container uses environment variables from your `.env` file. Make sure you have:

```bash
# Required: Set at least one API key
ANTHROPIC_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
# GOOGLE_API_KEY=your_key_here

# LLM Configuration
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
AUTO_EXECUTE=false

# Logging (optional)
ENABLE_LOGGING=true
LOG_LEVEL=INFO
```

### Volumes
The Docker setup mounts two directories:
- `./logs` - Persistent logs (LLM calls, executions, app logs)
- `./data` - Input/output images

## Troubleshooting

### Container won't start
Check logs:
```bash
docker-compose logs imagemagick-agent
# or
docker logs imagemagick-agent
```

### Missing API key error
Make sure your `.env` file has the correct API key set:
```bash
cat .env | grep API_KEY
```

### Port already in use
If port 7860 or 5000 is already in use, edit `docker-compose.yml`:
```yaml
ports:
  - "8080:7860"  # Change 8080 to any available port
```

### Permission issues with volumes
Make sure the mounted directories exist and are writable:
```bash
mkdir -p logs data
chmod 755 logs data
```

## Advanced Usage

### Running CLI instead of web interface
```bash
docker run -it --rm \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  imagemagick-agent:latest \
  imagemagick-agent
```

### Running log viewer separately
```bash
docker run -d \
  --name imagemagick-logs \
  -p 5001:5000 \
  -v $(pwd)/logs:/app/logs:ro \
  imagemagick-agent:latest \
  imagemagick-agent-logs
```

### Building with custom tag
```bash
docker build -t myusername/imagemagick-agent:v1.0 .
```

## Health Check

The container includes a health check that monitors the Gradio web interface:
```bash
docker inspect imagemagick-agent | grep -A 5 Health
```

## Resource Limits

To limit CPU and memory usage, uncomment the `deploy.resources` section in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
```
