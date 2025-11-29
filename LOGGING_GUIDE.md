# ImageMagick Agent - Logging Framework Guide

## Overview

The ImageMagick Agent now includes a comprehensive logging framework that provides full visibility into LLM calls, command executions, and application behavior. This guide explains how to use and configure the logging system.

## Features

### 1. Structured Logging
- **JSON Lines Format**: Easy to parse and query
- **Multiple Log Files**: Separate concerns (LLM calls, executions, app logs)
- **Log Rotation**: Automatic file rotation based on size
- **Configurable Levels**: DEBUG, INFO, WARNING, ERROR

### 2. LLM Call Tracking
Captures detailed information about every LLM API call:
- **Request Logging**:
  - Provider (Anthropic, OpenAI, Google)
  - Model name
  - User input
  - Full conversation history
  - System prompt
  - Timestamp
  - Unique request ID for correlation

- **Response Logging**:
  - Generated command
  - Response time (milliseconds)
  - Token usage (input/output tokens)
  - Success/failure status
  - Error messages if any

- **Clarification Logging**:
  - When LLM requests more information
  - Original user input
  - Clarification message

### 3. Command Execution Audit Trail
Complete audit log of all ImageMagick commands:
- **Validation Logging**:
  - Command being validated
  - Individual check results (whitelist, dangerous options, shell injection)
  - Pass/fail status
  - Error messages if validation fails

- **Execution Logging**:
  - Command executed
  - Success/failure status
  - Execution time (milliseconds)
  - Output file path
  - stdout and stderr (truncated to 500 chars)
  - Error messages

### 4. Web-Based Log Viewer
Beautiful dashboard for analyzing logs:
- **Real-time Statistics**:
  - Total LLM calls (successful/failed)
  - Average response time
  - Total executions (successful/failed)
  - Token usage totals

- **Interactive Log Browser**:
  - Tabbed interface (LLM Calls, Executions, All Logs)
  - Expandable log entries with full details
  - Color-coded by type and status

- **Filtering & Search**:
  - Filter by provider (Anthropic, OpenAI, Google)
  - Filter by success/failure status
  - Full-text search across all logs
  - Time range filtering

- **Real-time Updates**:
  - Auto-refresh every 5-10 seconds
  - Live log streaming (future enhancement)

## Installation

The logging framework is included with the main package. Just install dependencies:

```bash
pip install -e .
```

Flask is now included as a dependency for the log viewer.

## Configuration

### Environment Variables

Add these to your `.env` file (all optional, defaults shown):

```bash
# Enable/disable logging
ENABLE_LOGGING=true

# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Log directory
LOG_DIR=logs

# Enable detailed LLM call tracking
ENABLE_LLM_LOGGING=true

# Enable command execution audit trail
ENABLE_EXECUTION_LOGGING=true

# Log file rotation settings
LOG_MAX_BYTES=10000000  # 10MB
LOG_BACKUP_COUNT=5      # Keep 5 backup files
```

### Log Files

Three types of log files are created in the `logs/` directory:

1. **`app.log`** - General application logs
   - Startup/shutdown events
   - Configuration loading
   - Errors and warnings
   - Standard log format with timestamps

2. **`llm_calls.jsonl`** - LLM interaction logs
   - JSON Lines format (one JSON object per line)
   - Request and response pairs
   - Correlated by `request_id`

3. **`executions.jsonl`** - Command execution logs
   - JSON Lines format
   - Validation and execution events
   - Full command details and results

## Usage

### Running the Agent

Just run the agent normally - logging happens automatically:

```bash
imagemagick-agent
```

Logs will be written to the `logs/` directory as you interact with the agent.

### Viewing Logs

#### Option 1: Web Dashboard (Recommended)

Start the log viewer web server:

```bash
imagemagick-agent-logs
```

Then open your browser to: **http://localhost:5000**

Custom port and log directory:
```bash
imagemagick-agent-logs --port 8080 --log-dir /path/to/logs
```

#### Option 2: Command Line

View logs directly:
```bash
# View application logs
tail -f logs/app.log

# View LLM calls (JSON Lines)
tail -f logs/llm_calls.jsonl | jq .

# View executions
tail -f logs/executions.jsonl | jq .
```

#### Option 3: Analysis Scripts

Process logs with Python:
```python
import json

# Load LLM calls
with open('logs/llm_calls.jsonl') as f:
    for line in f:
        log = json.loads(line)
        if log['event'] == 'llm_response' and log['success']:
            print(f"Command: {log['generated_command']}")
            print(f"Time: {log['response_time_ms']}ms")
            print()
```

## Example Log Entries

### LLM Request
```json
{
  "timestamp": "2025-11-27T10:30:45.123Z",
  "event": "llm_request",
  "request_id": "req_a1b2c3d4",
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "user_input": "resize the image to 800x600",
  "conversation_history": [
    {"role": "user", "content": "previous message"},
    {"role": "assistant", "content": "previous response"}
  ],
  "conversation_length": 2,
  "system_prompt": "You are an expert ImageMagick assistant..."
}
```

### LLM Response
```json
{
  "timestamp": "2025-11-27T10:30:46.789Z",
  "event": "llm_response",
  "request_id": "req_a1b2c3d4",
  "generated_command": "magick input.jpg -resize 800x600 output.jpg",
  "response_time_ms": 1666.23,
  "token_usage": {
    "input_tokens": 450,
    "output_tokens": 25
  },
  "error": null,
  "success": true
}
```

### Command Validation
```json
{
  "timestamp": "2025-11-27T10:30:47.100Z",
  "event": "command_validation",
  "command": "magick input.jpg -resize 800x600 output.jpg",
  "validation_result": "passed",
  "checks": {
    "not_empty": true,
    "allowed_command": true,
    "no_dangerous_options": true,
    "no_shell_injection": true
  },
  "error_message": null
}
```

### Command Execution
```json
{
  "timestamp": "2025-11-27T10:30:47.500Z",
  "event": "command_execution",
  "command": "magick input.jpg -resize 800x600 output.jpg",
  "success": true,
  "execution_time_ms": 423.56,
  "output_file": "/path/to/output.jpg",
  "stdout": "",
  "stderr": ""
}
```

## Use Cases

### 1. Debugging LLM Issues
- See exactly what context was sent to the LLM
- Track token usage to optimize prompts
- Identify slow API calls
- Debug failed requests with full error messages

### 2. Performance Analysis
- Measure average LLM response times
- Track command execution times
- Identify bottlenecks
- Monitor token usage trends

### 3. Audit & Compliance
- Complete record of all commands executed
- Track who requested what (via conversation history)
- Verify command validation worked correctly
- Identify security issues or attempted exploits

### 4. Cost Monitoring
- Track total token usage over time
- Calculate API costs by provider
- Identify expensive operations
- Optimize prompt engineering

### 5. Quality Assurance
- Review LLM-generated commands for accuracy
- Identify patterns in failures
- Test different models/providers
- Validate conversation context handling

## Troubleshooting

### Logs Not Being Created

1. Check if logging is enabled:
   ```bash
   grep ENABLE_LOGGING .env
   ```

2. Verify log directory exists and is writable:
   ```bash
   ls -la logs/
   ```

3. Check application logs for errors:
   ```bash
   tail -f logs/app.log
   ```

### Log Viewer Not Working

1. Ensure Flask is installed:
   ```bash
   pip install flask>=3.0.0
   ```

2. Check if port 5000 is available:
   ```bash
   lsof -i :5000
   ```

3. Try a different port:
   ```bash
   imagemagick-agent-logs --port 8080
   ```

### Logs Too Large

Adjust rotation settings in `.env`:
```bash
LOG_MAX_BYTES=5000000  # 5MB instead of 10MB
LOG_BACKUP_COUNT=3     # Keep fewer backups
```

### Want More Detail

Set log level to DEBUG:
```bash
LOG_LEVEL=DEBUG
```

This adds verbose logging including:
- Command validation details
- Executor initialization
- LLM client creation
- All function calls and returns

## Best Practices

1. **Production**: Use `LOG_LEVEL=INFO` or `WARNING`
2. **Development**: Use `LOG_LEVEL=DEBUG` for detailed traces
3. **Log Rotation**: Enable and configure appropriately for your usage
4. **Regular Review**: Check logs periodically for errors or anomalies
5. **Privacy**: Be aware logs contain conversation history - secure appropriately
6. **Backup**: Consider backing up logs for long-term analysis
7. **Monitoring**: Set up alerts for high error rates or slow response times

## Advanced: Custom Analysis

### Find Slowest Commands
```bash
cat logs/executions.jsonl | jq -r '. | select(.event=="command_execution") | "\(.execution_time_ms) \(.command)"' | sort -nr | head
```

### Calculate Average Response Time
```bash
cat logs/llm_calls.jsonl | jq -r '. | select(.event=="llm_response") | .response_time_ms' | awk '{sum+=$1; count++} END {print sum/count}'
```

### Count Tokens by Provider
```bash
cat logs/llm_calls.jsonl | jq -r '. | select(.event=="llm_request") | "\(.provider)"' | sort | uniq -c
```

### Export to CSV
```python
import json
import csv

with open('logs/llm_calls.jsonl') as infile, open('llm_calls.csv', 'w') as outfile:
    writer = csv.writer(outfile)
    writer.writerow(['timestamp', 'event', 'provider', 'response_time_ms', 'success'])

    for line in infile:
        log = json.loads(line)
        if log['event'] == 'llm_response':
            writer.writerow([
                log['timestamp'],
                log['event'],
                log.get('provider', ''),
                log.get('response_time_ms', ''),
                log.get('success', '')
            ])
```

## Architecture Details

### Logging Flow

```
User Request
    ↓
Agent.process_request() [logs to app.log]
    ↓
LLMCallLogger.log_request() [writes to llm_calls.jsonl]
    ↓
LLMClient.generate_command() [logs timing]
    ↓
LLMCallLogger.log_response() [writes to llm_calls.jsonl]
    ↓
CommandExecutor.validate_command() [logs validation]
    ↓
ExecutionLogger.log_validation() [writes to executions.jsonl]
    ↓
CommandExecutor.execute() [logs execution]
    ↓
ExecutionLogger.log_execution() [writes to executions.jsonl]
```

### Components

- **`logging_config.py`**: Centralized setup, creates loggers and handlers
- **`llm_logger.py`**: LLMCallLogger and ExecutionLogger classes
- **`web_logs.py`**: Flask app for web dashboard
- **`log_viewer_cli.py`**: CLI entry point for log viewer
- **`templates/dashboard.html`**: Web UI template

## Support

For issues or questions:
1. Check the logs for error messages
2. Review the CLAUDE.md documentation
3. Open an issue on GitHub with log snippets (remove sensitive data!)

---

**Happy Logging! 📊**
