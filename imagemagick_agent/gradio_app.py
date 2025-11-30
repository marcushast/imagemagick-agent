"""Gradio web interface for ImageMagick Agent."""

import os
import signal
import sys
import time
import gradio as gr
from pathlib import Path
from typing import List, Tuple, Optional

from .config import load_settings
from .agent import ImageMagickAgent
from .storage import FileStorage
from .logging_config import setup_logging
from .log_reader import LogReader
from .llm_logger import ExecutionLogger


class GradioInterface:
    """Gradio web interface for the ImageMagick agent."""

    def __init__(self):
        """Initialize the Gradio interface."""
        self.settings = load_settings()
        self.agent = ImageMagickAgent(self.settings)
        self.storage = FileStorage()
        self.log_reader = LogReader(log_dir=self.settings.log_dir)
        self.execution_logger = ExecutionLogger(enabled=self.settings.enable_execution_logging)
        self.last_command: Optional[str] = None
        # Track commands by message index for feedback logging
        self.command_map = {}  # {message_index: {"command": str, "output_file": str}}
        self.last_command_index: Optional[int] = None
        # Track last uploaded image path to avoid duplicate upload messages
        self.last_uploaded_path: Optional[str] = None

    def process_message(
        self,
        message: str,
        chat_history: List[dict],
        uploaded_image: Optional[str],
    ) -> Tuple[List[dict], gr.update, gr.update]:
        """Process a user message and return updated chat history with inline images.

        Args:
            message: User's message
            chat_history: Current chat history
            uploaded_image: Path to uploaded image (if any)

        Returns:
            Tuple of (updated chat history, accept button update, refine button update)
        """
        if not message.strip():
            return chat_history, gr.update(visible=False), gr.update(visible=False)

        # Handle file upload - start a new session (only if it's a NEW upload)
        if uploaded_image and uploaded_image != self.last_uploaded_path:
            try:
                saved_path = self.storage.save_uploaded_file(
                    uploaded_image, original_name=Path(uploaded_image).name
                )
                # Track this upload to avoid duplicate messages
                self.last_uploaded_path = uploaded_image

                # Start a new session when a new image is uploaded
                self.agent.start_new_session()
                upload_msg = f"(Image uploaded: {saved_path.name})"
                message = f"{message} {upload_msg}"
            except Exception as e:
                error_msg = f"Error uploading file: {str(e)}"
                chat_history.append({"role": "user", "content": message})
                chat_history.append({"role": "assistant", "content": error_msg})
                return chat_history, gr.update(visible=False), gr.update(visible=False)

        # Add user message to chat
        chat_history.append({"role": "user", "content": message})

        # Process request through agent
        try:
            result = self.agent.process_request(message)

            # Handle clarification requests
            if "clarification" in result:
                response = result["clarification"]
                chat_history.append({"role": "assistant", "content": response})
                return chat_history, gr.update(visible=False), gr.update(visible=False)

            # Handle errors
            if result.get("error"):
                response = f"Error: {result['error']}"
                chat_history.append({"role": "assistant", "content": response})
                return chat_history, gr.update(visible=False), gr.update(visible=False)

            # Get the command
            command = result.get("command")
            if not command:
                response = "I couldn't generate a command. Please try rephrasing your request."
                chat_history.append({"role": "assistant", "content": response})
                return chat_history, gr.update(visible=False), gr.update(visible=False)

            # Substitute file paths with current working image
            working_command = command
            working_image = self.storage.get_current_working_image()
            original_upload = self.storage.original_upload

            if working_image:
                # Replace common placeholders with actual file path
                for placeholder in ["input.jpg", "input.png", "image.jpg", "image.png"]:
                    working_command = working_command.replace(placeholder, str(working_image))

                # Replace references to the original uploaded file with current working image
                # This is crucial for chaining - after accepting, commands should use the new image
                if original_upload and working_image != original_upload:
                    # Replace the original filename (with or without path) with current working image
                    original_name = original_upload.name
                    if original_name in working_command:
                        working_command = working_command.replace(original_name, str(working_image))
                    # Also try with full path
                    if str(original_upload) in working_command:
                        working_command = working_command.replace(str(original_upload), str(working_image))

                # Also replace the current working image filename (without path) with full path
                filename_only = working_image.name
                if filename_only in working_command:
                    working_command = working_command.replace(filename_only, str(working_image))

            # Always auto-execute the command
            execution_result = self.agent.execute_command(working_command)
            response_text = self._format_execution_result(execution_result)

            # Show the command that was executed
            command_text = f"**Generated Command:**\n```bash\n{working_command}\n```\n\n{response_text}"
            chat_history.append({"role": "assistant", "content": command_text})

            # Track this command for feedback (message index is current length - 1)
            message_index = len(chat_history) - 1
            self.command_map[message_index] = {
                "command": working_command,
                "output_file": str(execution_result.output_file) if execution_result.output_file else None,
                "session_id": self.agent.session_id,
            }
            self.last_command_index = message_index

            # If successful and there's an output file, show it inline as a separate message
            if execution_result.success and execution_result.output_file:
                self.storage.add_output_file(execution_result.output_file)
                # Set as pending output (awaiting user acceptance)
                self.storage.set_pending_output(execution_result.output_file)
                # Add the image as a file message
                chat_history.append({
                    "role": "assistant",
                    "content": {"path": str(execution_result.output_file)}
                })
                # Show accept/refine buttons
                return chat_history, gr.update(visible=True), gr.update(visible=True)

            # No output file or execution failed - hide buttons
            return chat_history, gr.update(visible=False), gr.update(visible=False)

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            chat_history.append({"role": "assistant", "content": error_msg})
            return chat_history, gr.update(visible=False), gr.update(visible=False)


    def _format_execution_result(self, result) -> str:
        """Format execution result for display.

        Args:
            result: ExecutionResult object

        Returns:
            Formatted string
        """
        if result.success:
            msg = f"Command executed successfully!\n\n"
            if result.output_file:
                msg += f"Output: `{result.output_file}`"
            if result.stdout:
                msg += f"\n\nOutput:\n```\n{result.stdout}\n```"
            return msg
        else:
            msg = f"Command failed: {result.error_message}"
            if result.stderr:
                msg += f"\n\nError details:\n```\n{result.stderr}\n```"
            return msg

    def reset_conversation(self) -> List:
        """Reset the conversation and storage.

        Returns:
            Empty chat history
        """
        self.agent.reset_conversation()
        self.storage.reset()
        self.last_command = None
        self.command_map.clear()
        self.last_uploaded_path = None
        return []

    def handle_feedback(self, feedback_type: str, chat_history: List[dict]) -> List[dict]:
        """Handle user feedback (thumbs up/down) on the last command.

        Args:
            feedback_type: "liked" or "disliked"
            chat_history: Current chat history

        Returns:
            Updated chat history with feedback confirmation
        """
        if self.last_command_index is None:
            chat_history.append({
                "role": "assistant",
                "content": "⚠️ No command to rate yet!"
            })
            return chat_history

        # Look up the command associated with the last message
        if self.last_command_index in self.command_map:
            cmd_info = self.command_map[self.last_command_index]
            self.execution_logger.log_feedback(
                command=cmd_info["command"],
                feedback=feedback_type,
                message_index=self.last_command_index,
                output_file=cmd_info["output_file"],
                session_id=cmd_info["session_id"],
            )
            emoji = "👍" if feedback_type == "liked" else "👎"
            feedback_msg = f"{emoji} Feedback recorded! You rated this command as {feedback_type}."
            chat_history.append({
                "role": "assistant",
                "content": feedback_msg
            })
        else:
            chat_history.append({
                "role": "assistant",
                "content": "⚠️ Could not find command to rate."
            })

        return chat_history

    def accept_result(self, chat_history: List[dict]) -> Tuple[List[dict], gr.update, gr.update]:
        """Accept the current result and use it as input for next transformation.

        Args:
            chat_history: Current chat history

        Returns:
            Tuple of (updated chat history, accept button update, refine button update)
        """
        if not self.storage.has_pending_output():
            chat_history.append({
                "role": "assistant",
                "content": "⚠️ No result to accept. Please run a transformation first."
            })
            return chat_history, gr.update(visible=False), gr.update(visible=False)

        # Get the pending output filename before accepting
        pending_file = self.storage.pending_output.name if self.storage.pending_output else "output"

        # Accept the output as the new working image
        self.storage.accept_output()

        # Update the agent's conversation context to use the new input
        # This tells the LLM that future commands should operate on this file
        current_working = self.storage.get_current_working_image()
        if current_working:
            # Add a system-like message to inform about the new input
            context_msg = f"[System: The current input image is now {current_working.name}. All future commands will use this as the input.]"
            self.agent.conversation_history.append({
                "role": "user",
                "content": context_msg
            })

        # Add confirmation message
        chat_history.append({
            "role": "assistant",
            "content": f"✅ Result accepted! The image `{pending_file}` will be used as input for the next transformation."
        })

        # Hide the accept/refine buttons
        return chat_history, gr.update(visible=False), gr.update(visible=False)

    def refine_result(self, chat_history: List[dict]) -> Tuple[List[dict], gr.update, gr.update]:
        """Refine the current result (keep same input for next transformation).

        Args:
            chat_history: Current chat history

        Returns:
            Tuple of (updated chat history, accept button update, refine button update)
        """
        if not self.storage.has_pending_output():
            chat_history.append({
                "role": "assistant",
                "content": "⚠️ No result to refine. Please run a transformation first."
            })
            return chat_history, gr.update(visible=False), gr.update(visible=False)

        # Clear the pending output (keep current working image)
        self.storage.pending_output = None

        # Add confirmation message
        chat_history.append({
            "role": "assistant",
            "content": "🔄 Ready to refine! Enter a new command to try again with the same input image."
        })

        # Hide the accept/refine buttons
        return chat_history, gr.update(visible=False), gr.update(visible=False)

    def load_log_stats(self):
        """Load and format log statistics for display."""
        stats = self.log_reader.get_stats()

        stats_md = f"""
## 📊 Statistics

### LLM Calls
- **Total:** {stats['llm_calls']['total']}
- **Successful:** {stats['llm_calls']['successful']} ✅
- **Failed:** {stats['llm_calls']['failed']} ❌
- **Avg Response Time:** {stats['llm_calls']['avg_response_time_ms']:.0f} ms
- **Total Tokens:** {stats['llm_calls']['total_tokens']['input'] + stats['llm_calls']['total_tokens']['output']:,} ({stats['llm_calls']['total_tokens']['input']:,} in / {stats['llm_calls']['total_tokens']['output']:,} out)

### Command Executions
- **Total:** {stats['executions']['total']}
- **Successful:** {stats['executions']['successful']} ✅
- **Failed:** {stats['executions']['failed']} ❌
- **Avg Execution Time:** {stats['executions']['avg_execution_time_ms']:.0f} ms

### User Feedback
- **Total:** {stats['feedback']['total']}
- **Liked:** {stats['feedback']['liked']} 👍
- **Disliked:** {stats['feedback']['disliked']} 👎
"""
        return stats_md

    def load_sessions(self):
        """Load available sessions for the dropdown."""
        sessions = self.log_reader.get_sessions()
        if not sessions:
            return gr.Dropdown(choices=["All"])

        # Format session choices: "All" plus session IDs with metadata
        # Use tuples of (label, value) for display
        choices = [("All Sessions", "All")]
        for session in sessions:
            session_id_short = session["session_id"][:8]  # Show first 8 chars of UUID
            count = session["command_count"]
            start_time = session.get("start_time", "")[:19]  # YYYY-MM-DD HH:MM:SS
            label = f"{session_id_short}... ({count} cmds, {start_time})"
            choices.append((label, session["session_id"]))  # (display, value)

        return gr.Dropdown(choices=choices)

    def load_llm_logs(self, limit: int = 50, provider: str = "All", session: str = "All"):
        """Load and format LLM logs for display."""
        provider_filter = None if provider == "All" else provider.lower()
        session_filter = None if session == "All" else session
        logs = self.log_reader.get_llm_calls(
            limit=limit, provider=provider_filter, session_id=session_filter
        )

        if not logs:
            return [], ["No logs available"]

        table_data, headers = self.log_reader.format_llm_calls_for_display(logs)
        return table_data, headers

    def load_execution_logs(self, limit: int = 50, session: str = "All"):
        """Load and format execution logs for display."""
        session_filter = None if session == "All" else session
        logs = self.log_reader.get_executions(limit=limit, session_id=session_filter)

        if not logs:
            return [], ["No logs available"]

        table_data, headers = self.log_reader.format_executions_for_display(logs)
        return table_data, headers

    def load_unified_logs(self, limit: int = 100, session: str = "All"):
        """Load and format unified logs (LLM calls + executions) for display."""
        session_filter = None if session == "All" else session
        logs = self.log_reader.get_unified_logs(limit=limit, session_id=session_filter)

        if not logs:
            return [], ["No logs available"]

        table_data, headers = self.log_reader.format_unified_logs_for_display(logs)
        return table_data, headers

    def build_interface(self) -> gr.Blocks:
        """Build and return the Gradio interface.

        Returns:
            Gradio Blocks interface
        """
        with gr.Blocks(title="ImageMagick Agent") as interface:
            gr.Markdown("# 🎨 ImageMagick Agent")

            with gr.Tabs():
                # ===== CHAT TAB =====
                with gr.Tab("💬 Chat"):
                    gr.Markdown(
                        """
                        Upload an image and describe transformations in natural language.
                        The agent will generate and execute ImageMagick commands automatically.

                        **Transformation Chaining:**
                        - After each transformation, choose **Accept & Continue** to use the result as input for the next command
                        - Or choose **Refine (Try Again)** to keep the same input and try a different transformation

                        **Examples:**
                        - "Resize this image to 800x600"
                        - "Add a 10px red border"
                        - "Rotate 45 degrees clockwise"
                        - "Convert to grayscale and add a blue tint"
                        """
                    )

                    # Single column layout
                    # Image upload
                    image_input = gr.Image(
                        label="Upload Image",
                        type="filepath",
                        height=300,
                    )

                    # Chat interface
                    chatbot = gr.Chatbot(
                        label="Conversation",
                        height=500,
                    )

                    # Accept/Refine buttons (hidden initially)
                    with gr.Row(visible=True) as action_row:
                        accept_btn = gr.Button(
                            "✅ Accept & Continue",
                            variant="primary",
                            size="sm",
                            visible=False,
                        )
                        refine_btn = gr.Button(
                            "🔄 Refine (Try Again)",
                            variant="secondary",
                            size="sm",
                            visible=False,
                        )

                    # Feedback buttons
                    with gr.Row():
                        gr.Markdown("**Rate the last command:**")
                        thumbs_up_btn = gr.Button("👍 Good", size="sm")
                        thumbs_down_btn = gr.Button("👎 Bad", size="sm")

                    # Message input
                    msg_input = gr.Textbox(
                        label="Your request",
                        placeholder="Describe the transformation you want... (Press Enter to send)",
                        lines=1,
                        max_lines=5,
                    )

                    with gr.Row():
                        reset_btn = gr.Button("Reset Conversation", variant="secondary")

                    # Event handlers
                    # Submit on Enter key
                    msg_input.submit(
                        fn=self.process_message,
                        inputs=[msg_input, chatbot, image_input],
                        outputs=[chatbot, accept_btn, refine_btn],
                    ).then(
                        lambda: "",  # Clear input after submit
                        outputs=[msg_input],
                    )

                    # Reset button
                    reset_btn.click(
                        fn=self.reset_conversation,
                        outputs=[chatbot],
                    )

                    # Feedback button handlers
                    thumbs_up_btn.click(
                        fn=lambda history: self.handle_feedback("liked", history),
                        inputs=[chatbot],
                        outputs=[chatbot],
                    )

                    thumbs_down_btn.click(
                        fn=lambda history: self.handle_feedback("disliked", history),
                        inputs=[chatbot],
                        outputs=[chatbot],
                    )

                    # Accept/Refine button handlers
                    accept_btn.click(
                        fn=self.accept_result,
                        inputs=[chatbot],
                        outputs=[chatbot, accept_btn, refine_btn],
                    )

                    refine_btn.click(
                        fn=self.refine_result,
                        inputs=[chatbot],
                        outputs=[chatbot, accept_btn, refine_btn],
                    )

                # ===== LOGS TAB =====
                with gr.Tab("📊 Logs"):
                    gr.Markdown("View all events chronologically, grouped by session.")

                    # Session filter
                    with gr.Row():
                        # Get initial session choices
                        initial_sessions = self.log_reader.get_sessions()
                        session_choices = [("All Sessions", "All")]
                        for session in initial_sessions:
                            session_id_short = session["session_id"][:8]
                            count = session["command_count"]
                            start_time = session.get("start_time", "")[:19]
                            label = f"{session_id_short}... ({count} cmds, {start_time})"
                            session_choices.append((label, session["session_id"]))

                        session_filter = gr.Dropdown(
                            choices=session_choices,
                            value="All",
                            label="Filter by Session",
                            scale=2,
                        )
                        refresh_sessions_btn = gr.Button("🔄 Refresh Sessions", size="sm", scale=0)

                    # Refresh sessions button
                    refresh_sessions_btn.click(
                        fn=self.load_sessions,
                        outputs=[session_filter],
                    )

                    # Unified log viewer
                    gr.Markdown("### Event Log (grouped by session)")

                    with gr.Row():
                        log_limit = gr.Slider(
                            minimum=20,
                            maximum=500,
                            value=100,
                            step=20,
                            label="Max Entries",
                            scale=2,
                        )
                        refresh_log_btn = gr.Button("🔄 Refresh", size="sm", scale=0)

                    # Initialize with empty data
                    initial_log_data, initial_log_headers = self.load_unified_logs()
                    unified_table = gr.Dataframe(
                        value=initial_log_data,
                        headers=initial_log_headers,
                        label="All Events (LLM Calls, Executions, Feedback)",
                        wrap=True,
                        column_widths=["8%", "8%", "8%", "10%", "60%", "6%"],
                        max_height=700,
                    )

                    # Helper function to return only data
                    def refresh_unified_table(limit, session):
                        data, _ = self.load_unified_logs(limit, session)
                        return data

                    # Refresh button
                    refresh_log_btn.click(
                        fn=refresh_unified_table,
                        inputs=[log_limit, session_filter],
                        outputs=[unified_table],
                    )

                    # Auto-refresh on slider change
                    log_limit.change(
                        fn=refresh_unified_table,
                        inputs=[log_limit, session_filter],
                        outputs=[unified_table],
                    )

                    # Auto-refresh on session filter change
                    session_filter.change(
                        fn=refresh_unified_table,
                        inputs=[log_limit, session_filter],
                        outputs=[unified_table],
                    )

                # ===== STATISTICS TAB =====
                with gr.Tab("📈 Statistics"):
                    gr.Markdown("Summary statistics for LLM calls, executions, and feedback.")

                    # Statistics section
                    with gr.Row():
                        stats_display = gr.Markdown(value=self.load_log_stats())
                        refresh_stats_btn = gr.Button("🔄 Refresh Stats", size="sm")

                    # Refresh stats button
                    refresh_stats_btn.click(
                        fn=self.load_log_stats,
                        outputs=[stats_display],
                    )

        return interface


def launch(share: bool = False, server_port: int = 7860):
    """Launch the Gradio web interface.

    Args:
        share: Whether to create a public sharing link
        server_port: Port to run the server on
    """
    # Load settings
    settings = load_settings()

    # Setup logging if enabled
    if settings.enable_logging:
        try:
            setup_logging(
                log_dir=settings.log_dir,
                app_log_level=settings.log_level,
                enable_llm_logging=settings.enable_llm_logging,
                enable_execution_logging=settings.enable_execution_logging,
                max_bytes=settings.log_max_bytes,
                backup_count=settings.log_backup_count,
            )
            print(f"✓ Logging enabled - logs directory: {settings.log_dir.absolute()}")
        except Exception as e:
            print(f"Warning: Could not initialize logging: {e}")

    app = GradioInterface()
    interface = app.build_interface()

    # Set up aggressive signal handlers that force immediate exit
    # These will override any handlers Gradio sets up
    shutdown_flag = {"triggered": False}

    def signal_handler(sig, frame):
        if shutdown_flag["triggered"]:
            # Second Ctrl-C - force kill
            print("\nForce quitting...")
            os._exit(1)
        else:
            shutdown_flag["triggered"] = True
            print("\nShutting down server...")
            os._exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Launch server without blocking the thread
    # This allows our signal handlers to stay active
    interface.launch(
        share=share,
        server_port=server_port,
        show_error=True,
        quiet=False,
        prevent_thread_lock=True,
    )

    print("Server is running. Press Ctrl+C to quit.\n")
    sys.stdout.flush()

    # Keep the main thread alive so our signal handlers work
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        os._exit(0)


if __name__ == "__main__":
    launch()
