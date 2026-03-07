"""Obsidian CLI client wrapper for vault operations."""

import json
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class ObsidianCLIClient:
    """Client for communicating with Obsidian vault using CLI or direct file access."""

    def __init__(
        self,
        vault_path: str,
        cli_path: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize Obsidian CLI client.

        Args:
            vault_path: Path to the Obsidian vault directory
            cli_path: Optional path to Obsidian CLI binary. If None, auto-detects.
            timeout: Command timeout in seconds

        Raises:
            MCPConnectionError: If vault path is invalid or CLI not found
        """
        self.vault_path = Path(vault_path).resolve()
        self.timeout = timeout
        self.logger = get_logger()

        # Validate vault path
        if not self.vault_path.exists():
            raise MCPConnectionError(f"Vault path does not exist: {self.vault_path}")
        if not self.vault_path.is_dir():
            raise MCPConnectionError(f"Vault path is not a directory: {self.vault_path}")

        # Detect or validate CLI binary
        self.cli_path = self._detect_cli_binary(cli_path)
        self._connected = False

    def _detect_cli_binary(self, cli_path: Optional[str] = None) -> Optional[str]:
        """
        Detect Obsidian CLI binary location based on platform.

        Args:
            cli_path: Optional explicit CLI path to validate

        Returns:
            Path to CLI binary if found, None otherwise
        """
        system = platform.system()

        # If explicit path provided, validate it
        if cli_path:
            cli_path_obj = Path(cli_path)
            if cli_path_obj.exists() and cli_path_obj.is_file():
                self.logger.info(f"Using provided CLI binary: {cli_path}")
                return str(cli_path_obj)
            else:
                self.logger.warning(f"Provided CLI path not found: {cli_path}")

        # Platform-specific default paths
        default_paths = []

        if system == "Darwin":  # macOS
            default_paths = [
                "/Applications/Obsidian.app/Contents/MacOS/obsidian",
                Path.home() / "Applications/Obsidian.app/Contents/MacOS/obsidian"
            ]
        elif system == "Windows":
            default_paths = [
                Path(r"C:\Program Files\Obsidian\obsidian.exe"),
                Path.home() / "AppData/Local/Obsidian/obsidian.exe"
            ]
        elif system == "Linux":
            # Try common Linux paths and check PATH
            default_paths = [
                Path("/usr/bin/obsidian"),
                Path("/usr/local/bin/obsidian"),
                Path.home() / ".local/bin/obsidian"
            ]
            # Also check if 'obsidian' is in PATH
            path_binary = shutil.which("obsidian")
            if path_binary:
                default_paths.insert(0, Path(path_binary))

        # Check default paths
        for path in default_paths:
            path_obj = Path(path)
            if path_obj.exists() and path_obj.is_file():
                self.logger.info(f"Auto-detected CLI binary: {path_obj}")
                return str(path_obj)

        # CLI not found - will fall back to direct file operations
        self.logger.warning(
            f"Obsidian CLI binary not found on {system}. "
            "Will use direct file operations instead."
        )
        return None

    def connect(self) -> None:
        """
        Validate connection to vault (synchronous, unlike MCP version).

        Raises:
            MCPConnectionError: If connection validation fails
        """
        self.logger.info(f"Connecting to vault: {self.vault_path}")

        # Verify vault has .obsidian directory
        obsidian_dir = self.vault_path / ".obsidian"
        if not obsidian_dir.exists():
            self.logger.warning(
                f"No .obsidian directory found in {self.vault_path}. "
                "This may not be a valid Obsidian vault."
            )

        self._connected = True
        self.logger.info("Successfully connected to vault")

    def disconnect(self) -> None:
        """Disconnect from vault (cleanup)."""
        self._connected = False
        self.logger.info("Disconnected from vault")

    def is_connected(self) -> bool:
        """Check if connected to vault."""
        return self._connected

    def _run_cli_command(self, args: List[str]) -> subprocess.CompletedProcess:
        """
        Run an Obsidian CLI command.

        Args:
            args: Command arguments to pass to CLI

        Returns:
            Completed process result

        Raises:
            MCPConnectionError: If CLI not available
            MCPTimeoutError: If command times out
            MCPToolError: If command fails
        """
        if not self.cli_path:
            raise MCPConnectionError(
                "Obsidian CLI not available. Install Obsidian or provide cli_path."
            )

        try:
            cmd = [self.cli_path] + args
            self.logger.debug(f"Running CLI command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.vault_path)
            )

            if result.returncode != 0:
                raise MCPToolError(
                    f"CLI command failed (exit code {result.returncode}): {result.stderr}"
                )

            return result

        except subprocess.TimeoutExpired:
            raise MCPTimeoutError(f"CLI command timed out after {self.timeout}s")
        except FileNotFoundError as e:
            raise MCPConnectionError(f"CLI binary not found: {self.cli_path}") from e
        except Exception as e:
            raise MCPToolError(f"CLI command failed: {e}") from e

    def search_notes(
        self,
        modified_since: Optional[datetime] = None,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for notes in vault.

        Args:
            modified_since: Only return notes modified after this datetime
            query: Optional search query text

        Returns:
            List of note metadata dictionaries with keys:
                - path: Note file path (relative to vault)
                - title: Note title (filename without extension)
                - modified: Last modified timestamp
                - created: Creation timestamp

        Raises:
            MCPConnectionError: If not connected
            MCPError: If search fails
        """
        if not self._connected:
            raise MCPConnectionError("Not connected to vault. Call connect() first.")

        self.logger.info(f"Searching notes (query={query}, modified_since={modified_since})")

        try:
            # Use direct file system search (more reliable than CLI)
            notes = []

            # Find all markdown files
            for md_file in self.vault_path.rglob("*.md"):
                # Skip files in .obsidian directory
                if ".obsidian" in md_file.parts:
                    continue

                # Get file stats
                stats = md_file.stat()
                modified = datetime.fromtimestamp(stats.st_mtime)
                created = datetime.fromtimestamp(stats.st_ctime)

                # Filter by modified_since
                if modified_since and modified < modified_since:
                    continue

                # Filter by query if provided
                if query:
                    # Check filename first
                    if query.lower() not in md_file.stem.lower():
                        # Check content
                        try:
                            content = md_file.read_text(encoding='utf-8')
                            if query.lower() not in content.lower():
                                continue
                        except Exception as e:
                            self.logger.warning(f"Could not read {md_file}: {e}")
                            continue

                # Add note metadata
                relative_path = md_file.relative_to(self.vault_path)
                notes.append({
                    "path": str(relative_path),
                    "title": md_file.stem,
                    "modified": modified.isoformat(),
                    "created": created.isoformat()
                })

            self.logger.info(f"Found {len(notes)} notes")
            return notes

        except Exception as e:
            self.logger.error(f"Failed to search notes: {e}")
            raise MCPError(f"Note search failed: {e}") from e

    def read_note(self, note_path: str) -> str:
        """
        Read content of a note.

        Args:
            note_path: Path to the note file (relative to vault)

        Returns:
            Note content as string

        Raises:
            MCPConnectionError: If not connected
            MCPError: If read fails
        """
        if not self._connected:
            raise MCPConnectionError("Not connected to vault. Call connect() first.")

        self.logger.debug(f"Reading note: {note_path}")

        try:
            # Use direct file read
            full_path = self.vault_path / note_path

            if not full_path.exists():
                raise MCPError(f"Note not found: {note_path}")

            content = full_path.read_text(encoding='utf-8')
            self.logger.debug(f"Successfully read note: {note_path} ({len(content)} chars)")
            return content

        except MCPError:
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
            path: Path for the new note (relative to vault)
            content: Content of the note
            overwrite: Whether to overwrite if file exists

        Returns:
            Dictionary with creation result

        Raises:
            MCPConnectionError: If not connected
            MCPError: If creation fails
        """
        if not self._connected:
            raise MCPConnectionError("Not connected to vault. Call connect() first.")

        self.logger.info(f"Creating note: {path} (overwrite={overwrite})")

        try:
            full_path = self.vault_path / path

            # Check if file exists
            if full_path.exists() and not overwrite:
                raise MCPError(f"Note already exists: {path}")

            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            full_path.write_text(content, encoding='utf-8')

            self.logger.info(f"Successfully created note: {path}")
            return {"success": True}

        except MCPError:
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
            path: Path to the note (relative to vault)
            content: New content

        Returns:
            Dictionary with update result

        Raises:
            MCPConnectionError: If not connected
            MCPError: If update fails
        """
        if not self._connected:
            raise MCPConnectionError("Not connected to vault. Call connect() first.")

        self.logger.info(f"Updating note: {path}")

        try:
            full_path = self.vault_path / path

            if not full_path.exists():
                raise MCPError(f"Note not found: {path}")

            # Write content
            full_path.write_text(content, encoding='utf-8')

            self.logger.info(f"Successfully updated note: {path}")
            return {"success": True}

        except MCPError:
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
            path: Path to the note (relative to vault)
            content: Content to append

        Returns:
            Dictionary with append result

        Raises:
            MCPConnectionError: If not connected
            MCPError: If append fails
        """
        if not self._connected:
            raise MCPConnectionError("Not connected to vault. Call connect() first.")

        self.logger.info(f"Appending to note: {path}")

        try:
            full_path = self.vault_path / path

            if not full_path.exists():
                raise MCPError(f"Note not found: {path}")

            # Read existing content
            existing_content = full_path.read_text(encoding='utf-8')

            # Append new content
            new_content = existing_content + content
            full_path.write_text(new_content, encoding='utf-8')

            self.logger.info(f"Successfully appended to note: {path}")
            return {"success": True}

        except MCPError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to append to note {path}: {e}")
            raise MCPError(f"Failed to append to note: {e}") from e

    def __enter__(self):
        """Context manager entry (synchronous)."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (synchronous)."""
        self.disconnect()
        return False
