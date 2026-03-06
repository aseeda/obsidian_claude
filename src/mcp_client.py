"""MCP client wrapper for Obsidian server communication using JSON-RPC over subprocess."""

import asyncio
import json
import subprocess
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

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
    """Client for communicating with Obsidian MCP server via JSON-RPC."""

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
        self._request_id = 0
        self._initialized = False

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

                # Start the MCP server subprocess
                self._process = subprocess.Popen(
                    [self.server_command] + self.server_args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )

                # Initialize the MCP session
                await self._initialize_session()

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

                # Clean up failed process
                if self._process:
                    try:
                        self._process.terminate()
                        self._process.wait(timeout=2)
                    except:
                        pass
                    self._process = None

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

    async def _initialize_session(self) -> None:
        """
        Initialize the MCP session by sending initialize request.

        Raises:
            MCPError: If initialization fails
        """
        try:
            # Send initialize request (required by MCP protocol)
            response = await self._send_request(
                method="initialize",
                params={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "obsidian-claude-agent",
                        "version": "1.0.0"
                    }
                }
            )

            if "error" in response:
                raise MCPError(f"Initialization failed: {response['error']}")

            self._initialized = True
            self.logger.debug("MCP session initialized")

        except Exception as e:
            raise MCPError(f"Failed to initialize MCP session: {e}") from e

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
        if self._process:
            self.logger.info("Disconnecting from MCP server")
            try:
                # Send shutdown notification if initialized
                if self._initialized:
                    try:
                        await self._send_notification("notifications/cancelled")
                    except:
                        pass

                # Terminate the process
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.logger.warning("Process did not terminate, killing it")
                    self._process.kill()
                    self._process.wait()

            except Exception as e:
                self.logger.warning(f"Error during disconnect: {e}")

            self._process = None

        self._connected = False
        self._initialized = False

    def is_connected(self) -> bool:
        """Check if connected to MCP server."""
        return self._connected and self._process is not None and self._process.poll() is None

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a JSON-RPC request to the MCP server.

        Args:
            method: JSON-RPC method name
            params: Method parameters

        Returns:
            JSON-RPC response

        Raises:
            MCPConnectionError: If not connected
            MCPTimeoutError: If request times out
            MCPError: If request fails
        """
        if not self._process or self._process.poll() is not None:
            raise MCPConnectionError("Not connected to MCP server")

        self._request_id += 1
        request_id = self._request_id

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        self.logger.debug(f"Sending JSON-RPC request: {json.dumps(request)}")

        try:
            # Send request
            request_line = json.dumps(request) + "\n"
            self._process.stdin.write(request_line)
            self._process.stdin.flush()

            # Read response with timeout
            response = await asyncio.wait_for(
                self._read_response(request_id),
                timeout=self.timeout
            )

            return response

        except asyncio.TimeoutError:
            raise MCPTimeoutError(f"Request {method} timed out after {self.timeout}s")
        except Exception as e:
            raise MCPError(f"Request {method} failed: {e}") from e

    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a JSON-RPC notification (no response expected).

        Args:
            method: Notification method
            params: Optional parameters
        """
        if not self._process:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params:
            notification["params"] = params

        try:
            notification_line = json.dumps(notification) + "\n"
            self._process.stdin.write(notification_line)
            self._process.stdin.flush()
        except:
            pass

    async def _read_response(self, expected_id: int) -> Dict[str, Any]:
        """
        Read JSON-RPC response from server.

        Args:
            expected_id: Expected request ID

        Returns:
            Response dictionary

        Raises:
            MCPError: If response is invalid
        """
        loop = asyncio.get_event_loop()

        # Read line from stdout in executor to avoid blocking
        line = await loop.run_in_executor(None, self._process.stdout.readline)

        if not line:
            raise MCPError("Server closed connection")

        try:
            response = json.loads(line.strip())
        except json.JSONDecodeError as e:
            raise MCPError(f"Invalid JSON response: {line}") from e

        # Validate JSON-RPC response
        if response.get("jsonrpc") != "2.0":
            raise MCPError(f"Invalid JSON-RPC version: {response.get('jsonrpc')}")

        if response.get("id") != expected_id:
            raise MCPError(f"Response ID mismatch: expected {expected_id}, got {response.get('id')}")

        self.logger.debug(f"Received JSON-RPC response: {json.dumps(response)}")

        return response

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
        if not self.is_connected():
            self.logger.error("Attempted to call tool while not connected")
            raise MCPConnectionError("Not connected to MCP server. Call connect() first.")

        try:
            self.logger.debug(f"Calling MCP tool: {tool_name} with args: {arguments}")

            # Call tools/call method per MCP spec
            response = await self._send_request(
                method="tools/call",
                params={
                    "name": tool_name,
                    "arguments": arguments
                }
            )

            # Check for error
            if "error" in response:
                error = response["error"]
                raise MCPToolError(f"Tool {tool_name} failed: {error.get('message', error)}")

            # Extract result
            result = response.get("result", {})
            self.logger.debug(f"Tool {tool_name} completed successfully")
            return result

        except MCPTimeoutError:
            raise
        except MCPConnectionError:
            raise
        except MCPToolError:
            raise
        except Exception as e:
            self.logger.error(f"Tool {tool_name} failed: {e}")
            raise MCPToolError(f"Failed to execute tool {tool_name}: {e}") from e

    async def search_notes(
        self,
        modified_since: Optional[datetime] = None,
        query: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for notes in Obsidian vault.

        Args:
            modified_since: Only return notes modified after this datetime
            query: Optional search query
            limit: Maximum number of results

        Returns:
            List of note paths

        Raises:
            MCPError: If search fails
        """
        self.logger.info(f"Searching notes (query: {query}, limit: {limit})")

        arguments = {"limit": limit}
        if query:
            arguments["query"] = query

        try:
            result = await self._call_tool("search_notes", arguments)

            # Parse result - MCP returns structured data
            notes = []
            if isinstance(result, dict):
                # Handle different response formats
                if "content" in result:
                    # MCP tool result format
                    for content_item in result["content"]:
                        if content_item.get("type") == "text":
                            text_data = content_item.get("text", "")
                            try:
                                parsed = json.loads(text_data)
                                if isinstance(parsed, list):
                                    notes = parsed
                                elif isinstance(parsed, dict) and "results" in parsed:
                                    notes = parsed["results"]
                            except:
                                # Text might be plain list
                                notes = [{"path": text_data}]
                elif "results" in result:
                    notes = result["results"]
                elif "notes" in result:
                    notes = result["notes"]
            elif isinstance(result, list):
                notes = result

            # Convert to standard format
            formatted_notes = []
            for note in notes:
                if isinstance(note, str):
                    formatted_notes.append({"path": note})
                elif isinstance(note, dict):
                    formatted_notes.append(note)

            self.logger.info(f"Found {len(formatted_notes)} notes")
            return formatted_notes

        except MCPError:
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
            MCPError: If read fails
        """
        self.logger.debug(f"Reading note: {note_path}")

        try:
            result = await self._call_tool("read_note", {"path": note_path})

            # Extract content from result
            content = ""
            if isinstance(result, dict):
                if "content" in result:
                    # MCP tool result format
                    for content_item in result["content"]:
                        if content_item.get("type") == "text":
                            text_data = content_item.get("text", "")
                            # The text might be a JSON string with {fm, content} structure
                            try:
                                parsed = json.loads(text_data)
                                if isinstance(parsed, dict) and "content" in parsed:
                                    content = parsed["content"]
                                else:
                                    content = text_data
                            except (json.JSONDecodeError, TypeError):
                                content = text_data
                            break
                elif "text" in result:
                    content = result["text"]
            elif isinstance(result, str):
                content = result

            self.logger.debug(f"Successfully read note: {note_path} ({len(content)} chars)")
            return content

        except MCPError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to read note {note_path}: {e}")
            raise MCPError(f"Failed to read note: {e}") from e

    async def create_note(
        self,
        path: str,
        content: str,
        overwrite: bool = True
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
            MCPError: If creation fails
        """
        self.logger.info(f"Creating note: {path}")

        try:
            mode = "overwrite" if overwrite else "overwrite"
            result = await self._call_tool("write_note", {
                "path": path,
                "content": content,
                "mode": mode
            })

            self.logger.info(f"Successfully created note: {path}")
            return {"success": True, "result": result}

        except MCPError:
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
            MCPError: If update fails
        """
        self.logger.info(f"Updating note: {path}")

        try:
            result = await self._call_tool("write_note", {
                "path": path,
                "content": content,
                "mode": "overwrite"
            })

            self.logger.info(f"Successfully updated note: {path}")
            return {"success": True, "result": result}

        except MCPError:
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
            MCPError: If append fails
        """
        self.logger.info(f"Appending to note: {path}")

        try:
            result = await self._call_tool("write_note", {
                "path": path,
                "content": content,
                "mode": "append"
            })

            self.logger.info(f"Successfully appended to note: {path}")
            return {"success": True, "result": result}

        except MCPError:
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
