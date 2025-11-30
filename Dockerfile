# Multi-stage build for ImageMagick Agent
# Stage 1: Build stage
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml ./

# Create a minimal setup to extract dependencies
# We'll install just the dependencies, not the package itself
RUN pip install --no-cache-dir --prefix=/install \
    anthropic>=0.39.0 \
    openai>=1.0.0 \
    google-generativeai>=0.3.0 \
    python-dotenv>=1.0.0 \
    rich>=13.0.0 \
    pydantic>=2.0.0 \
    pydantic-settings>=2.0.0 \
    gradio>=4.0.0 \
    flask>=3.0.0 \
    waitress>=2.1.0

# Stage 2: Runtime stage
FROM python:3.11-slim

# Install ImageMagick and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY imagemagick_agent/ ./imagemagick_agent/
COPY pyproject.toml ./
COPY CLAUDE.md README.md ./

# Install the package in editable mode
RUN pip install --no-cache-dir -e .

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports
# 7860: Gradio web interface
# 5000: Log viewer
EXPOSE 7860 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    LOG_DIR=/app/logs

# Health check for web interface
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:7860').read()" || exit 1

# Default command: run web interface
CMD ["imagemagick-agent-web"]
