"""MCP client wrapper for Obsidian server communication."""

import asyncio
import json
import subprocess
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

try:
    from .logger import get_logger
    from .exceptions import (
        MCPConnectionError,
        MCPTimeoutError,
        MCPToolError,
        MCPError
    )
except ImportError:
    from logger import get_logger
    from exceptions import (
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

        self._session: Optional[ClientSession] = None
        self._read_stream = None
        self._write_stream = None
        self._connected = False

    async def connect(self) -> None:
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

                # Create server parameters
                server_params = StdioServerParameters(
                    command=self.server_command,
                    args=self.server_args,
                    env=None
                )

                # Start MCP server and create session
                self._read_stream, self._write_stream = await stdio_client(server_params)
                self._session = ClientSession(self._read_stream, self._write_stream)

                # Initialize the session
                await self._session.initialize()

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
                    await asyncio.sleep(self.retry_delay)
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

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._session:
            self.logger.info("Disconnecting from MCP server")
            try:
                # Close the session gracefully
                await self._session.__aexit__(None, None, None)
            except Exception as e:
                self.logger.warning(f"Error during session cleanup: {e}")
            self._session = None

        self._read_stream = None
        self._write_stream = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to MCP server."""
        return self._connected

    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
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
        if not self._connected or not self._session:
            self.logger.error("Attempted to call tool while not connected")
            raise MCPConnectionError("Not connected to MCP server. Call connect() first.")

        try:
            self.logger.debug(f"Calling MCP tool: {tool_name} with args: {arguments}")

            # Call the tool with timeout
            try:
                result = await asyncio.wait_for(
                    self._session.call_tool(tool_name, arguments),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                raise MCPTimeoutError(f"Tool {tool_name} timed out after {self.timeout}s")

            self.logger.debug(f"Tool {tool_name} completed successfully")
            return result

        except MCPTimeoutError:
            # Re-raise timeout errors
            raise

        except MCPConnectionError:
            # Re-raise connection errors
            raise

        except Exception as e:
            self.logger.error(f"Tool {tool_name} failed: {e}")
            raise MCPToolError(f"Failed to execute tool {tool_name}: {e}") from e

    async def search_notes(
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
            result = await self._call_tool("search_notes", arguments)

            # Extract results from the tool response
            # MCP tool responses have content array with text content
            notes = []
            if hasattr(result, 'content') and result.content:
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        # Parse the JSON response
                        import json
                        notes_data = json.loads(content_item.text)
                        if isinstance(notes_data, list):
                            notes = notes_data
                        elif isinstance(notes_data, dict) and 'notes' in notes_data:
                            notes = notes_data['notes']

            # Filter by modified_since if specified
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

    async def read_note(self, note_path: str) -> str:
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
            result = await self._call_tool("read_note", {"path": note_path})

            # Extract content from MCP tool response
            content = ""
            if hasattr(result, 'content') and result.content:
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        # Parse the JSON response
                        note_data = json.loads(content_item.text)
                        content = note_data.get("content", "")
                        break

            self.logger.debug(f"Successfully read note: {note_path} ({len(content)} chars)")
            return content

        except MCPError:
            # Re-raise MCP errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to read note {note_path}: {e}")
            raise MCPError(f"Failed to read note: {e}") from e

    async def create_note(
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
            # Use write_note tool with mode 'overwrite' if overwrite is True
            mode = "overwrite" if overwrite else "overwrite"  # Default is overwrite
            result = await self._call_tool("write_note", {
                "path": path,
                "content": content,
                "mode": mode
            })

            self.logger.info(f"Successfully created note: {path}")
            return {"success": True}

        except MCPError:
            # Re-raise MCP errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to create note {path}: {e}")
            raise MCPError(f"Failed to create note: {e}") from e

    async def update_note(
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
            result = await self._call_tool("write_note", {
                "path": path,
                "content": content,
                "mode": "overwrite"
            })

            self.logger.info(f"Successfully updated note: {path}")
            return {"success": True}

        except MCPError:
            # Re-raise MCP errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to update note {path}: {e}")
            raise MCPError(f"Failed to update note: {e}") from e

    async def append_to_note(
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
            # Use append mode in write_note tool
            result = await self._call_tool("write_note", {
                "path": path,
                "content": content,
                "mode": "append"
            })

            self.logger.info(f"Successfully appended to note: {path}")
            return {"success": True}

        except MCPError:
            # Re-raise MCP errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to append to note {path}: {e}")
            raise MCPError(f"Failed to append to note: {e}") from e

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        return False
