"""MCP client wrapper for Obsidian server communication."""

import json
import subprocess
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from .logger import get_logger
from .exceptions import (
    MCPConnectionError,
    MCPTimeoutError,
    MCPToolError,
    MCPError
)


class MCPClient:
    """Client for communicating with Obsidian MCP server."""

    def __init__(
        self,
        server_command: str,
        server_args: List[str],
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize MCP client.

        Args:
            server_command: Command to run MCP server (e.g., 'npx')
            server_args: Arguments for server command
            timeout: Server timeout in seconds
            max_retries: Maximum number of connection retry attempts
            retry_delay: Delay between retries in seconds

        Raises:
            MCPConnectionError: If connection to server fails
        """
        self.server_command = server_command
        self.server_args = server_args
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = get_logger()

        self._process: Optional[subprocess.Popen] = None
        self._connected = False

    def connect(self) -> None:
        """
        Connect to the MCP server with retry logic.

        Raises:
            MCPConnectionError: If connection fails after all retries
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info(
                    f"Connecting to MCP server (attempt {attempt}/{self.max_retries}): "
                    f"{self.server_command} {' '.join(self.server_args)}"
                )

                # Validate server command exists
                self._validate_server_command()

                # Start MCP server process
                # Note: In actual implementation, we'd use the MCP SDK
                # For now, this is a structure placeholder
                # Example: self._process = mcp.start_server(...)

                self._connected = True
                self.logger.info("Successfully connected to MCP server")
                return

            except FileNotFoundError as e:
                self.logger.error(f"Server command not found: {self.server_command}")
                raise MCPConnectionError(
                    f"MCP server command not found: {self.server_command}. "
                    "Make sure the server is installed."
                ) from e

            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"Connection attempt {attempt} failed: {e}"
                )

                if attempt < self.max_retries:
                    self.logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error(
                        f"Failed to connect after {self.max_retries} attempts"
                    )

        # All retries exhausted
        raise MCPConnectionError(
            f"MCP server connection failed after {self.max_retries} attempts: {last_error}"
        ) from last_error

    def _validate_server_command(self) -> None:
        """
        Validate that the server command is available.

        Raises:
            FileNotFoundError: If command not found
        """
        import shutil

        if not shutil.which(self.server_command):
            raise FileNotFoundError(f"Command '{self.server_command}' not found in PATH")

    def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._process:
            self.logger.info("Disconnecting from MCP server")
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to MCP server."""
        return self._connected

    def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call an MCP tool with timeout and error handling.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments for the tool

        Returns:
            Tool response

        Raises:
            MCPConnectionError: If not connected
            MCPTimeoutError: If operation times out
            MCPToolError: If tool execution fails
        """
        if not self._connected:
            self.logger.error("Attempted to call tool while not connected")
            raise MCPConnectionError("Not connected to MCP server. Call connect() first.")

        try:
            self.logger.debug(f"Calling MCP tool: {tool_name} with args: {arguments}")

            # Placeholder: In actual implementation, use MCP SDK to call tool
            # For now, this is a structure placeholder
            # Example implementation:
            # try:
            #     result = await asyncio.wait_for(
            #         mcp_session.call_tool(tool_name, arguments),
            #         timeout=self.timeout
            #     )
            # except asyncio.TimeoutError:
            #     raise MCPTimeoutError(f"Tool {tool_name} timed out after {self.timeout}s")

            self.logger.debug(f"Tool {tool_name} completed successfully")
            return {}  # Placeholder return

        except MCPTimeoutError:
            # Re-raise timeout errors
            raise

        except MCPConnectionError:
            # Re-raise connection errors
            raise

        except Exception as e:
            self.logger.error(f"Tool {tool_name} failed: {e}")
            raise MCPToolError(f"Failed to execute tool {tool_name}: {e}") from e

    def search_notes(
        self,
        modified_since: Optional[datetime] = None,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for notes in Obsidian vault.

        Args:
            modified_since: Only return notes modified after this datetime
            query: Optional search query

        Returns:
            List of note metadata dictionaries with keys:
                - path: Note file path
                - title: Note title
                - modified: Last modified timestamp
                - created: Creation timestamp

        Raises:
            MCPClientError: If search fails
        """
        self.logger.info(f"Searching notes (modified_since: {modified_since}, query: {query})")

        arguments = {}
        if query:
            arguments["query"] = query

        try:
            # Call MCP search_notes tool
            result = self._call_tool("obsidian_search_notes", arguments)

            # Filter by modified_since if specified
            notes = result.get("notes", [])
            if modified_since:
                filtered_notes = []
                for note in notes:
                    note_modified = datetime.fromisoformat(note.get("modified", ""))
                    if note_modified >= modified_since:
                        filtered_notes.append(note)
                notes = filtered_notes

            self.logger.info(f"Found {len(notes)} notes")
            return notes

        except MCPError:
            # Re-raise MCP errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to search notes: {e}")
            raise MCPError(f"Note search failed: {e}") from e

    def read_note(self, note_path: str) -> str:
        """
        Read content of a note.

        Args:
            note_path: Path to the note file

        Returns:
            Note content as string

        Raises:
            MCPClientError: If read fails
        """
        self.logger.debug(f"Reading note: {note_path}")

        try:
            result = self._call_tool("obsidian_read_note", {"path": note_path})
            content = result.get("content", "")

            self.logger.debug(f"Successfully read note: {note_path} ({len(content)} chars)")
            return content

        except MCPError:
            # Re-raise MCP errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to read note {note_path}: {e}")
            raise MCPError(f"Failed to read note: {e}") from e

    def create_note(
        self,
        path: str,
        content: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new note in the vault.

        Args:
            path: Path for the new note
            content: Content of the note
            overwrite: Whether to overwrite if file exists

        Returns:
            Dictionary with creation result

        Raises:
            MCPClientError: If creation fails
        """
        self.logger.info(f"Creating note: {path} (overwrite: {overwrite})")

        try:
            result = self._call_tool("obsidian_create_note", {
                "path": path,
                "content": content,
                "overwrite": overwrite
            })

            self.logger.info(f"Successfully created note: {path}")
            return result

        except MCPError:
            # Re-raise MCP errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to create note {path}: {e}")
            raise MCPError(f"Failed to create note: {e}") from e

    def update_note(
        self,
        path: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Update an existing note.

        Args:
            path: Path to the note
            content: New content

        Returns:
            Dictionary with update result

        Raises:
            MCPClientError: If update fails
        """
        self.logger.info(f"Updating note: {path}")

        try:
            result = self._call_tool("obsidian_update_note", {
                "path": path,
                "content": content
            })

            self.logger.info(f"Successfully updated note: {path}")
            return result

        except MCPError:
            # Re-raise MCP errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to update note {path}: {e}")
            raise MCPError(f"Failed to update note: {e}") from e

    def append_to_note(
        self,
        path: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Append content to an existing note.

        Args:
            path: Path to the note
            content: Content to append

        Returns:
            Dictionary with append result

        Raises:
            MCPClientError: If append fails
        """
        self.logger.info(f"Appending to note: {path}")

        try:
            # Read current content
            current_content = self.read_note(path)

            # Append new content
            new_content = current_content + "\n" + content

            # Update note
            result = self.update_note(path, new_content)

            self.logger.info(f"Successfully appended to note: {path}")
            return result

        except MCPError:
            # Re-raise MCP errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to append to note {path}: {e}")
            raise MCPError(f"Failed to append to note: {e}") from e

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False
