"""
Web interface for viewing and analyzing logs.

Provides a Flask-based dashboard for:
- Viewing LLM call logs
- Viewing command execution logs
- Filtering and searching logs
- Real-time log streaming
"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from flask import Flask, render_template, request, jsonify, Response, send_from_directory


def create_app(log_dir: Path = Path("logs")) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        log_dir: Directory containing log files

    Returns:
        Configured Flask app
    """
    app = Flask(__name__, template_folder="templates")
    app.config["LOG_DIR"] = log_dir

    @app.route("/")
    def index():
        """Dashboard homepage."""
        return render_template("dashboard.html")

    @app.route("/api/llm-calls")
    def get_llm_calls():
        """
        Get LLM call logs with optional filtering.

        Query parameters:
            start: Start timestamp (ISO format)
            end: End timestamp (ISO format)
            provider: Filter by provider (anthropic, openai, google)
            success: Filter by success status (true/false)
            limit: Maximum number of results to return
        """
        # Parse query params
        start_time = request.args.get("start")
        end_time = request.args.get("end")
        provider = request.args.get("provider")
        success_filter = request.args.get("success")
        limit = int(request.args.get("limit", 100))

        logs = []
        llm_log_file = app.config["LOG_DIR"] / "llm_calls.jsonl"

        if llm_log_file.exists():
            with open(llm_log_file, "r") as f:
                for line in f:
                    try:
                        log = json.loads(line.strip())

                        # Apply filters
                        if start_time and log.get("timestamp", "") < start_time:
                            continue
                        if end_time and log.get("timestamp", "") > end_time:
                            continue
                        if provider and log.get("provider") != provider:
                            continue
                        if success_filter is not None:
                            success_bool = success_filter.lower() == "true"
                            if log.get("success") != success_bool:
                                continue

                        logs.append(log)

                        # Apply limit
                        if len(logs) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue

        # Return most recent first
        logs.reverse()
        return jsonify(logs)

    @app.route("/api/executions")
    def get_executions():
        """
        Get command execution logs with optional filtering.

        Query parameters:
            start: Start timestamp (ISO format)
            end: End timestamp (ISO format)
            success: Filter by success status (true/false)
            limit: Maximum number of results to return
        """
        start_time = request.args.get("start")
        end_time = request.args.get("end")
        success_filter = request.args.get("success")
        limit = int(request.args.get("limit", 100))

        logs = []
        exec_log_file = app.config["LOG_DIR"] / "executions.jsonl"

        if exec_log_file.exists():
            with open(exec_log_file, "r") as f:
                for line in f:
                    try:
                        log = json.loads(line.strip())

                        # Apply filters
                        if start_time and log.get("timestamp", "") < start_time:
                            continue
                        if end_time and log.get("timestamp", "") > end_time:
                            continue
                        if success_filter is not None:
                            success_bool = success_filter.lower() == "true"
                            if log.get("success") != success_bool:
                                continue

                        logs.append(log)

                        if len(logs) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue

        logs.reverse()
        return jsonify(logs)

    @app.route("/api/stats")
    def get_stats():
        """
        Get summary statistics for logs.

        Returns:
            JSON with counts, averages, and other metrics
        """
        stats = {
            "llm_calls": {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "avg_response_time_ms": 0,
                "total_tokens": {"input": 0, "output": 0},
            },
            "executions": {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "avg_execution_time_ms": 0,
            },
        }

        # Process LLM calls
        llm_log_file = app.config["LOG_DIR"] / "llm_calls.jsonl"
        if llm_log_file.exists():
            response_times = []
            with open(llm_log_file, "r") as f:
                for line in f:
                    try:
                        log = json.loads(line.strip())
                        if log.get("event") == "llm_response":
                            stats["llm_calls"]["total"] += 1
                            if log.get("success"):
                                stats["llm_calls"]["successful"] += 1
                            else:
                                stats["llm_calls"]["failed"] += 1

                            if "response_time_ms" in log:
                                response_times.append(log["response_time_ms"])

                            if "token_usage" in log and log["token_usage"]:
                                stats["llm_calls"]["total_tokens"]["input"] += log[
                                    "token_usage"
                                ].get("input_tokens", 0)
                                stats["llm_calls"]["total_tokens"]["output"] += log[
                                    "token_usage"
                                ].get("output_tokens", 0)
                    except json.JSONDecodeError:
                        continue

            if response_times:
                stats["llm_calls"]["avg_response_time_ms"] = round(
                    sum(response_times) / len(response_times), 2
                )

        # Process executions
        exec_log_file = app.config["LOG_DIR"] / "executions.jsonl"
        if exec_log_file.exists():
            execution_times = []
            with open(exec_log_file, "r") as f:
                for line in f:
                    try:
                        log = json.loads(line.strip())
                        if log.get("event") == "command_execution":
                            stats["executions"]["total"] += 1
                            if log.get("success"):
                                stats["executions"]["successful"] += 1
                            else:
                                stats["executions"]["failed"] += 1

                            if "execution_time_ms" in log:
                                execution_times.append(log["execution_time_ms"])
                    except json.JSONDecodeError:
                        continue

            if execution_times:
                stats["executions"]["avg_execution_time_ms"] = round(
                    sum(execution_times) / len(execution_times), 2
                )

        return jsonify(stats)

    @app.route("/api/stream")
    def stream_logs():
        """
        Server-Sent Events endpoint for live log streaming.

        Streams new log entries as they are written to files.
        """

        def generate():
            """Generate SSE stream of new log entries."""
            # Track last read position for each file
            llm_log_file = app.config["LOG_DIR"] / "llm_calls.jsonl"
            exec_log_file = app.config["LOG_DIR"] / "executions.jsonl"

            llm_position = llm_log_file.stat().st_size if llm_log_file.exists() else 0
            exec_position = exec_log_file.stat().st_size if exec_log_file.exists() else 0

            while True:
                new_entries = []

                # Check LLM logs
                if llm_log_file.exists():
                    current_size = llm_log_file.stat().st_size
                    if current_size > llm_position:
                        with open(llm_log_file, "r") as f:
                            f.seek(llm_position)
                            for line in f:
                                try:
                                    log_entry = json.loads(line.strip())
                                    log_entry["log_type"] = "llm"
                                    new_entries.append(log_entry)
                                except json.JSONDecodeError:
                                    pass
                            llm_position = f.tell()

                # Check execution logs
                if exec_log_file.exists():
                    current_size = exec_log_file.stat().st_size
                    if current_size > exec_position:
                        with open(exec_log_file, "r") as f:
                            f.seek(exec_position)
                            for line in f:
                                try:
                                    log_entry = json.loads(line.strip())
                                    log_entry["log_type"] = "execution"
                                    new_entries.append(log_entry)
                                except json.JSONDecodeError:
                                    pass
                            exec_position = f.tell()

                # Send new entries
                for entry in new_entries:
                    yield f"data: {json.dumps(entry)}\n\n"

                # Wait before next check
                time.sleep(1)

        return Response(generate(), mimetype="text/event-stream")

    @app.route("/api/search")
    def search_logs():
        """
        Search logs by text content.

        Query parameters:
            q: Search query
            log_type: Type of log to search (llm, execution, or all)
            limit: Maximum results
        """
        query = request.args.get("q", "").lower()
        log_type = request.args.get("log_type", "all")
        limit = int(request.args.get("limit", 50))

        if not query:
            return jsonify([])

        results = []

        # Search LLM logs
        if log_type in ["llm", "all"]:
            llm_log_file = app.config["LOG_DIR"] / "llm_calls.jsonl"
            if llm_log_file.exists():
                with open(llm_log_file, "r") as f:
                    for line in f:
                        try:
                            log = json.loads(line.strip())
                            # Search in relevant fields
                            searchable = json.dumps(log).lower()
                            if query in searchable:
                                log["log_type"] = "llm"
                                results.append(log)
                                if len(results) >= limit:
                                    break
                        except json.JSONDecodeError:
                            continue

        # Search execution logs
        if log_type in ["execution", "all"] and len(results) < limit:
            exec_log_file = app.config["LOG_DIR"] / "executions.jsonl"
            if exec_log_file.exists():
                with open(exec_log_file, "r") as f:
                    for line in f:
                        try:
                            log = json.loads(line.strip())
                            searchable = json.dumps(log).lower()
                            if query in searchable:
                                log["log_type"] = "execution"
                                results.append(log)
                                if len(results) >= limit:
                                    break
                        except json.JSONDecodeError:
                            continue

        return jsonify(results)

    return app


def run_server(log_dir: Path = Path("logs"), port: int = 5000, debug: bool = False):
    """
    Run the log viewer web server.

    Args:
        log_dir: Directory containing log files
        port: Port to run server on
        debug: Enable Flask debug mode (only affects Flask's error pages, uses Waitress regardless)
    """
    from waitress import serve

    app = create_app(log_dir)
    print(f"\n🌐 Log Viewer starting at http://localhost:{port}")
    print(f"📁 Log directory: {log_dir.absolute()}")
    print("Press Ctrl+C to quit\n")

    try:
        # Use Waitress for production-ready serving with proper signal handling
        serve(app, host="0.0.0.0", port=port, threads=4, _quiet=False)
    except KeyboardInterrupt:
        print("\n\nShutting down log viewer...")
        sys.exit(0)


if __name__ == "__main__":
    run_server()
