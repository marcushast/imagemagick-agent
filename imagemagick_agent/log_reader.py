"""
Modular log reading and parsing utilities.

This module provides reusable functions for reading and analyzing logs
that can be used by both the Gradio interface and Flask web viewer.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class LogReader:
    """Read and parse log files."""

    def __init__(self, log_dir: Path = Path("logs")):
        """
        Initialize log reader.

        Args:
            log_dir: Directory containing log files
        """
        self.log_dir = Path(log_dir)
        self.llm_log_file = self.log_dir / "llm_calls.jsonl"
        self.exec_log_file = self.log_dir / "executions.jsonl"
        self.app_log_file = self.log_dir / "app.log"

    def get_llm_calls(
        self,
        limit: int = 100,
        provider: Optional[str] = None,
        success: Optional[bool] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get LLM call logs with optional filtering.

        Args:
            limit: Maximum number of entries to return
            provider: Filter by provider (anthropic, openai, google)
            success: Filter by success status
            session_id: Filter by session ID

        Returns:
            List of log entries (most recent first)
        """
        logs = []

        if not self.llm_log_file.exists():
            return logs

        with open(self.llm_log_file, "r") as f:
            for line in f:
                try:
                    log = json.loads(line.strip())

                    # Apply filters
                    if provider and log.get("provider") != provider:
                        continue
                    if success is not None and log.get("success") != success:
                        continue
                    if session_id and log.get("session_id") != session_id:
                        continue

                    logs.append(log)

                    if len(logs) >= limit:
                        break
                except json.JSONDecodeError:
                    continue

        # Return most recent first
        logs.reverse()
        return logs

    def get_executions(
        self,
        limit: int = 100,
        success: Optional[bool] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get command execution logs with optional filtering.

        Args:
            limit: Maximum number of entries to return
            success: Filter by success status
            session_id: Filter by session ID

        Returns:
            List of log entries (most recent first)
        """
        logs = []

        if not self.exec_log_file.exists():
            return logs

        with open(self.exec_log_file, "r") as f:
            for line in f:
                try:
                    log = json.loads(line.strip())

                    # Apply filters
                    if success is not None and log.get("success") != success:
                        continue
                    if session_id and log.get("session_id") != session_id:
                        continue

                    logs.append(log)

                    if len(logs) >= limit:
                        break
                except json.JSONDecodeError:
                    continue

        logs.reverse()
        return logs

    def get_stats(self) -> Dict:
        """
        Calculate summary statistics from logs.

        Returns:
            Dictionary with statistics for LLM calls and executions
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
            "feedback": {
                "total": 0,
                "liked": 0,
                "disliked": 0,
            },
        }

        # Process LLM calls
        if self.llm_log_file.exists():
            response_times = []
            with open(self.llm_log_file, "r") as f:
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

        # Process executions and feedback
        if self.exec_log_file.exists():
            execution_times = []
            with open(self.exec_log_file, "r") as f:
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
                        elif log.get("event") == "user_feedback":
                            stats["feedback"]["total"] += 1
                            if log.get("feedback") == "liked":
                                stats["feedback"]["liked"] += 1
                            elif log.get("feedback") == "disliked":
                                stats["feedback"]["disliked"] += 1
                    except json.JSONDecodeError:
                        continue

            if execution_times:
                stats["executions"]["avg_execution_time_ms"] = round(
                    sum(execution_times) / len(execution_times), 2
                )

        return stats

    def format_llm_calls_for_display(
        self, logs: List[Dict]
    ) -> Tuple[List[List], List[str]]:
        """
        Format LLM call logs for display in a table.

        Args:
            logs: List of log entries

        Returns:
            Tuple of (table_data, headers)
        """
        headers = [
            "Time",
            "Event",
            "Provider",
            "User Input",
            "Command/Error",
            "Response Time (ms)",
            "Tokens",
            "Status",
        ]

        table_data = []
        for log in logs:
            event = log.get("event", "")
            timestamp = log.get("timestamp", "")

            # Format timestamp
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = timestamp[:19] if len(timestamp) >= 19 else timestamp

            if event == "llm_request":
                table_data.append(
                    [
                        time_str,
                        "Request",
                        log.get("provider", ""),
                        log.get("user_input", "")[:50] + "...",
                        "-",
                        "-",
                        "-",
                        "⏳",
                    ]
                )
            elif event == "llm_response":
                success = log.get("success", False)
                status = "✅" if success else "❌"

                command_or_error = (
                    log.get("generated_command", "")[:50]
                    if success
                    else log.get("error", "")[:50]
                )

                token_usage = log.get("token_usage", {})
                tokens_str = (
                    f"{token_usage.get('input_tokens', 0)}→{token_usage.get('output_tokens', 0)}"
                    if token_usage
                    else "-"
                )

                table_data.append(
                    [
                        time_str,
                        "Response",
                        "-",
                        "-",
                        command_or_error,
                        f"{log.get('response_time_ms', 0):.0f}",
                        tokens_str,
                        status,
                    ]
                )

        return table_data, headers

    def format_executions_for_display(
        self, logs: List[Dict]
    ) -> Tuple[List[List], List[str]]:
        """
        Format execution logs for display in a table.

        Args:
            logs: List of log entries

        Returns:
            Tuple of (table_data, headers)
        """
        headers = [
            "Time",
            "Event",
            "Command",
            "Result",
            "Execution Time (ms)",
            "Output File",
            "Status",
        ]

        table_data = []
        for log in logs:
            event = log.get("event", "")
            timestamp = log.get("timestamp", "")

            # Format timestamp
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = timestamp[:19] if len(timestamp) >= 19 else timestamp

            if event == "command_validation":
                result = log.get("validation_result", "")
                status = "✅" if result == "passed" else "❌"

                table_data.append(
                    [
                        time_str,
                        "Validation",
                        log.get("command", "")[:50] + "...",
                        result,
                        "-",
                        "-",
                        status,
                    ]
                )
            elif event == "command_execution":
                success = log.get("success", False)
                status = "✅" if success else "❌"

                result = "Success" if success else log.get("error_message", "Failed")

                output_file = log.get("output_file", "-")
                if output_file and output_file != "-":
                    output_file = Path(output_file).name

                table_data.append(
                    [
                        time_str,
                        "Execution",
                        log.get("command", "")[:50] + "...",
                        result[:30],
                        f"{log.get('execution_time_ms', 0):.0f}",
                        output_file,
                        status,
                    ]
                )
            elif event == "user_feedback":
                feedback = log.get("feedback", "")
                status = "👍" if feedback == "liked" else "👎"

                output_file = log.get("output_file", "-")
                if output_file and output_file != "-":
                    output_file = Path(output_file).name

                table_data.append(
                    [
                        time_str,
                        "Feedback",
                        log.get("command", "")[:50] + "...",
                        feedback.capitalize(),
                        "-",
                        output_file,
                        status,
                    ]
                )

        return table_data, headers

    def get_sessions(self) -> List[Dict]:
        """
        Get all unique sessions from execution logs.

        Returns:
            List of session dictionaries with metadata (session_id, start_time, command_count)
            Sorted by most recent first
        """
        sessions = {}

        if not self.exec_log_file.exists():
            return []

        with open(self.exec_log_file, "r") as f:
            for line in f:
                try:
                    log = json.loads(line.strip())
                    session_id = log.get("session_id")

                    if not session_id:
                        continue

                    # Track session metadata
                    if session_id not in sessions:
                        sessions[session_id] = {
                            "session_id": session_id,
                            "start_time": log.get("timestamp"),
                            "command_count": 0,
                        }

                    # Count command executions (not validations or feedback)
                    if log.get("event") == "command_execution":
                        sessions[session_id]["command_count"] += 1

                    # Update to latest timestamp
                    sessions[session_id]["last_activity"] = log.get("timestamp")

                except json.JSONDecodeError:
                    continue

        # Convert to list and sort by start time (most recent first)
        session_list = list(sessions.values())
        session_list.sort(key=lambda x: x.get("start_time", ""), reverse=True)

        return session_list

    def get_unified_logs(
        self,
        limit: int = 100,
        session_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get unified logs combining LLM calls and command executions.

        Args:
            limit: Maximum number of entries to return
            session_id: Filter by session ID

        Returns:
            List of log entries (most recent first), sorted by timestamp
        """
        all_logs = []

        # Get LLM call logs
        if self.llm_log_file.exists():
            with open(self.llm_log_file, "r") as f:
                for line in f:
                    try:
                        log = json.loads(line.strip())
                        # Apply session filter
                        if session_id and log.get("session_id") != session_id:
                            continue
                        log["log_type"] = "llm"
                        all_logs.append(log)
                    except json.JSONDecodeError:
                        continue

        # Get execution logs
        if self.exec_log_file.exists():
            with open(self.exec_log_file, "r") as f:
                for line in f:
                    try:
                        log = json.loads(line.strip())
                        # Apply session filter
                        if session_id and log.get("session_id") != session_id:
                            continue
                        log["log_type"] = "execution"
                        all_logs.append(log)
                    except json.JSONDecodeError:
                        continue

        # Sort by timestamp (most recent first)
        all_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Apply limit
        return all_logs[:limit]

    def format_unified_logs_for_display(
        self, logs: List[Dict]
    ) -> Tuple[List[List], List[str]]:
        """
        Format unified logs for display in a table with session grouping.

        Args:
            logs: List of log entries (already sorted)

        Returns:
            Tuple of (table_data, headers)
        """
        headers = [
            "Session",
            "Time",
            "Type",
            "Event",
            "Details",
            "Status",
        ]

        table_data = []
        current_session = None

        for log in logs:
            event = log.get("event", "")
            timestamp = log.get("timestamp", "")
            session_id = log.get("session_id", "unknown")
            log_type = log.get("log_type", "")

            # Format timestamp
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = timestamp[:19] if len(timestamp) >= 19 else timestamp

            # Session display (show first 8 chars of UUID)
            session_display = session_id[:8] if session_id != "unknown" else "unknown"

            # Add session separator if session changed
            if session_id != current_session:
                current_session = session_id
                # Add a separator row
                if table_data:  # Don't add separator before first session
                    table_data.append(["════════", "════════", "════════", "════════", "════════", "════════"])

            # Format based on log type and event
            if log_type == "llm":
                if event == "llm_request":
                    user_input = log.get('user_input', '')
                    table_data.append([
                        session_display,
                        time_str,
                        "LLM",
                        "Request",
                        f"Provider: {log.get('provider', '')} | Input: {user_input}",
                        "⏳",
                    ])
                elif event == "llm_response":
                    success = log.get("success", False)
                    status = "✅" if success else "❌"
                    command = log.get("generated_command", log.get("error", ""))
                    tokens = log.get("token_usage", {})
                    token_str = f"{tokens.get('input_tokens', 0)}→{tokens.get('output_tokens', 0)}" if tokens else ""

                    table_data.append([
                        session_display,
                        time_str,
                        "LLM",
                        "Response",
                        f"Command: {command} | Tokens: {token_str} | {log.get('response_time_ms', 0):.0f}ms",
                        status,
                    ])

            elif log_type == "execution":
                if event == "command_validation":
                    result = log.get("validation_result", "")
                    status = "✅" if result == "passed" else "❌"
                    command = log.get('command', '')
                    error_msg = log.get("error_message", "")
                    details = f"Command: {command}"
                    if error_msg:
                        details += f" | Error: {error_msg}"

                    table_data.append([
                        session_display,
                        time_str,
                        "Exec",
                        "Validation",
                        details,
                        status,
                    ])
                elif event == "command_execution":
                    success = log.get("success", False)
                    status = "✅" if success else "❌"
                    output_file = log.get("output_file", "")
                    if output_file:
                        output_file = Path(output_file).name

                    command = log.get('command', '')
                    details = f"Command: {command} | Output: {output_file or 'N/A'} | {log.get('execution_time_ms', 0):.0f}ms"

                    if not success:
                        error_msg = log.get("error_message", "")
                        if error_msg:
                            details += f" | Error: {error_msg}"

                    table_data.append([
                        session_display,
                        time_str,
                        "Exec",
                        "Execution",
                        details,
                        status,
                    ])
                elif event == "user_feedback":
                    feedback = log.get("feedback", "")
                    status = "👍" if feedback == "liked" else "👎"
                    output_file = log.get("output_file", "")
                    if output_file:
                        output_file = Path(output_file).name

                    command = log.get('command', '')
                    table_data.append([
                        session_display,
                        time_str,
                        "Feedback",
                        feedback.capitalize(),
                        f"Command: {command} | Output: {output_file or 'N/A'}",
                        status,
                    ])

        return table_data, headers
