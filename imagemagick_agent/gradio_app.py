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


class GradioInterface:
    """Gradio web interface for the ImageMagick agent."""

    def __init__(self):
        """Initialize the Gradio interface."""
        self.settings = load_settings()
        self.agent = ImageMagickAgent(self.settings)
        self.storage = FileStorage()
        self.log_reader = LogReader(log_dir=self.settings.log_dir)
        self.last_command: Optional[str] = None

    def process_message(
        self,
        message: str,
        chat_history: List[dict],
        uploaded_image: Optional[str],
    ) -> Tuple[List[dict], Optional[List[str]], str]:
        """Process a user message and return updated chat history.

        Args:
            message: User's message
            chat_history: Current chat history
            uploaded_image: Path to uploaded image (if any)

        Returns:
            Tuple of (updated_chat_history, output_images, command_display)
        """
        if not message.strip():
            return chat_history, None, ""

        # Handle file upload
        if uploaded_image:
            try:
                saved_path = self.storage.save_uploaded_file(
                    uploaded_image, original_name=Path(uploaded_image).name
                )
                upload_msg = f"(Image uploaded: {saved_path.name})"
                message = f"{message} {upload_msg}"
            except Exception as e:
                error_msg = f"Error uploading file: {str(e)}"
                chat_history.append({"role": "user", "content": message})
                chat_history.append({"role": "assistant", "content": error_msg})
                return chat_history, None, ""

        # Add user message to chat
        chat_history.append({"role": "user", "content": message})

        # Process request through agent
        try:
            result = self.agent.process_request(message)

            # Handle clarification requests
            if "clarification" in result:
                response = result["clarification"]
                chat_history.append({"role": "assistant", "content": response})
                return chat_history, None, ""

            # Handle errors
            if result.get("error"):
                response = f"Error: {result['error']}"
                chat_history.append({"role": "assistant", "content": response})
                return chat_history, None, ""

            # Get the command
            command = result.get("command")
            if not command:
                response = "I couldn't generate a command. Please try rephrasing your request."
                chat_history.append({"role": "assistant", "content": response})
                return chat_history, None, ""

            # Substitute file paths if we have an uploaded file
            working_command = command
            latest_upload = self.storage.get_latest_upload()
            if latest_upload:
                # Replace common placeholders with actual file path
                for placeholder in ["input.jpg", "input.png", "image.jpg", "image.png"]:
                    working_command = working_command.replace(placeholder, str(latest_upload))

                # Also replace the actual uploaded filename (without path) with full path
                filename_only = latest_upload.name
                if filename_only in working_command:
                    working_command = working_command.replace(filename_only, str(latest_upload))

            # Store the command with paths substituted for later execution
            self.last_command = working_command

            # Auto-execute if configured, otherwise ask for confirmation
            if self.settings.auto_execute:
                execution_result = self.agent.execute_command(working_command)
                response = self._format_execution_result(execution_result)
                chat_history.append({"role": "assistant", "content": response})

                # Track output files and prepare gallery
                output_images = []
                if execution_result.success and execution_result.output_file:
                    self.storage.add_output_file(execution_result.output_file)
                    output_images = [str(f) for f in self.storage.get_output_files()]

                return chat_history, output_images, f"Command: `{working_command}`"
            else:
                # Show command and wait for confirmation
                response = f"Generated command:\n```\n{working_command}\n```\n\nReply 'yes' to execute or 'no' to cancel."
                chat_history.append({"role": "assistant", "content": response})
                return chat_history, None, f"Command: `{working_command}`"

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            chat_history.append({"role": "assistant", "content": error_msg})
            return chat_history, None, ""

    def handle_confirmation(
        self, message: str, chat_history: List[dict]
    ) -> Tuple[List[dict], Optional[List[str]], str]:
        """Handle user confirmation for command execution.

        Args:
            message: User's response
            chat_history: Current chat history

        Returns:
            Tuple of (updated_chat_history, output_images, command_display)
        """
        if not self.last_command:
            return self.process_message(message, chat_history, None)

        if message.lower().strip() in ["yes", "y", "execute", "run"]:
            # Execute the command
            chat_history.append({"role": "user", "content": message})

            execution_result = self.agent.execute_command(self.last_command)
            response = self._format_execution_result(execution_result)
            chat_history.append({"role": "assistant", "content": response})

            # Track output files and prepare gallery
            output_images = []
            if execution_result.success and execution_result.output_file:
                self.storage.add_output_file(execution_result.output_file)
                output_images = [str(f) for f in self.storage.get_output_files()]

            self.last_command = None
            return chat_history, output_images, ""

        elif message.lower().strip() in ["no", "n", "cancel"]:
            chat_history.append({"role": "user", "content": message})
            chat_history.append({"role": "assistant", "content": "Command cancelled."})
            self.last_command = None
            return chat_history, None, ""

        # Not a confirmation, process as new message
        return self.process_message(message, chat_history, None)

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

    def reset_conversation(self) -> Tuple[List, None, str]:
        """Reset the conversation and storage.

        Returns:
            Tuple of (empty_chat_history, None, empty_command)
        """
        self.agent.reset_conversation()
        self.storage.reset()
        self.last_command = None
        return [], None, ""

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
"""
        return stats_md

    def load_llm_logs(self, limit: int = 50, provider: str = "All"):
        """Load and format LLM logs for display."""
        provider_filter = None if provider == "All" else provider.lower()
        logs = self.log_reader.get_llm_calls(limit=limit, provider=provider_filter)

        if not logs:
            return [], ["No logs available"]

        table_data, headers = self.log_reader.format_llm_calls_for_display(logs)
        return table_data, headers

    def load_execution_logs(self, limit: int = 50):
        """Load and format execution logs for display."""
        logs = self.log_reader.get_executions(limit=limit)

        if not logs:
            return [], ["No logs available"]

        table_data, headers = self.log_reader.format_executions_for_display(logs)
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
                        The agent will generate and execute ImageMagick commands for you.

                        **Examples:**
                        - "Resize this image to 800x600"
                        - "Add a 10px red border"
                        - "Rotate 45 degrees clockwise"
                        - "Convert to grayscale and add a blue tint"
                        """
                    )

                    with gr.Row():
                        with gr.Column(scale=1):
                            # Image upload
                            image_input = gr.Image(
                                label="Upload Image",
                                type="filepath",
                                height=300,
                            )

                            # Action buttons
                            with gr.Row():
                                reset_btn = gr.Button("Reset", variant="secondary")

                            # Command display
                            command_display = gr.Markdown(label="Last Command")

                        with gr.Column(scale=2):
                            # Chat interface
                            chatbot = gr.Chatbot(
                                label="Conversation",
                                height=400,
                            )

                            # Message input
                            msg_input = gr.Textbox(
                                label="Your request",
                                placeholder="Describe the transformation you want...",
                                lines=2,
                            )

                            with gr.Row():
                                submit_btn = gr.Button("Send", variant="primary")
                                clear_btn = gr.ClearButton([msg_input])

                    # Output gallery
                    output_gallery = gr.Gallery(
                        label="Output Images",
                        columns=3,
                        height=300,
                    )

                    # Event handlers
                    def submit_message(message, history, image):
                        if self.last_command and not self.settings.auto_execute:
                            return self.handle_confirmation(message, history)
                        return self.process_message(message, history, image)

                    # Submit on button click
                    submit_btn.click(
                        fn=submit_message,
                        inputs=[msg_input, chatbot, image_input],
                        outputs=[chatbot, output_gallery, command_display],
                    ).then(
                        lambda: "",  # Clear input after submit
                        outputs=[msg_input],
                    )

                    # Submit on Enter key
                    msg_input.submit(
                        fn=submit_message,
                        inputs=[msg_input, chatbot, image_input],
                        outputs=[chatbot, output_gallery, command_display],
                    ).then(
                        lambda: "",  # Clear input after submit
                        outputs=[msg_input],
                    )

                    # Reset button
                    reset_btn.click(
                        fn=self.reset_conversation,
                        outputs=[chatbot, output_gallery, command_display],
                    )

                # ===== LOGS TAB =====
                with gr.Tab("📊 Logs"):
                    gr.Markdown("Monitor LLM calls and command executions in real-time.")

                    # Statistics section
                    with gr.Row():
                        stats_display = gr.Markdown(value=self.load_log_stats())
                        refresh_stats_btn = gr.Button("🔄 Refresh Stats", size="sm")

                    # Refresh stats button
                    refresh_stats_btn.click(
                        fn=self.load_log_stats,
                        outputs=[stats_display],
                    )

                    # Log viewer tabs
                    with gr.Tabs():
                        # LLM Calls tab
                        with gr.Tab("LLM Calls"):
                            with gr.Row():
                                provider_filter = gr.Dropdown(
                                    choices=["All", "Anthropic", "OpenAI", "Google"],
                                    value="All",
                                    label="Filter by Provider",
                                    scale=1,
                                )
                                llm_limit = gr.Slider(
                                    minimum=10,
                                    maximum=200,
                                    value=50,
                                    step=10,
                                    label="Max Entries",
                                    scale=1,
                                )
                                refresh_llm_btn = gr.Button("🔄 Refresh", size="sm", scale=0)

                            # Initialize with empty data
                            initial_data, initial_headers = self.load_llm_logs()
                            llm_table = gr.Dataframe(
                                value=initial_data,
                                headers=initial_headers,
                                label="LLM Call Logs",
                                wrap=True,
                            )

                            # Helper function to return only data
                            def refresh_llm_table(limit, provider):
                                data, _ = self.load_llm_logs(limit, provider)
                                return data

                            # Refresh button
                            refresh_llm_btn.click(
                                fn=refresh_llm_table,
                                inputs=[llm_limit, provider_filter],
                                outputs=[llm_table],
                            )

                            # Auto-refresh on filter change
                            provider_filter.change(
                                fn=refresh_llm_table,
                                inputs=[llm_limit, provider_filter],
                                outputs=[llm_table],
                            )

                            llm_limit.change(
                                fn=refresh_llm_table,
                                inputs=[llm_limit, provider_filter],
                                outputs=[llm_table],
                            )

                        # Executions tab
                        with gr.Tab("Command Executions"):
                            with gr.Row():
                                exec_limit = gr.Slider(
                                    minimum=10,
                                    maximum=200,
                                    value=50,
                                    step=10,
                                    label="Max Entries",
                                    scale=1,
                                )
                                refresh_exec_btn = gr.Button("🔄 Refresh", size="sm", scale=0)

                            # Initialize with empty data
                            initial_exec_data, initial_exec_headers = self.load_execution_logs()
                            exec_table = gr.Dataframe(
                                value=initial_exec_data,
                                headers=initial_exec_headers,
                                label="Execution Logs",
                                wrap=True,
                            )

                            # Helper function to return only data
                            def refresh_exec_table(limit):
                                data, _ = self.load_execution_logs(limit)
                                return data

                            # Refresh button
                            refresh_exec_btn.click(
                                fn=refresh_exec_table,
                                inputs=[exec_limit],
                                outputs=[exec_table],
                            )

                            # Auto-refresh on slider change
                            exec_limit.change(
                                fn=refresh_exec_table,
                                inputs=[exec_limit],
                                outputs=[exec_table],
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
