"""Tests for MCP client."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_client import MCPClient
from exceptions import MCPConnectionError, MCPError


class TestMCPClient:
    """Test MCP client functionality."""

    def test_init(self):
        """Test MCP client initialization."""
        client = MCPClient(
            server_command="npx",
            server_args=["-y", "@modelcontextprotocol/server-obsidian", "/vault"],
            timeout=30
        )

        assert client.server_command == "npx"
        assert len(client.server_args) == 3
        assert client.timeout == 30
        assert not client.is_connected()

    def test_init_with_custom_retries(self):
        """Test initialization with custom retry parameters."""
        client = MCPClient(
            server_command="npx",
            server_args=[],
            timeout=30,
            max_retries=5,
            retry_delay=2.0
        )

        assert client.max_retries == 5
        assert client.retry_delay == 2.0

    def test_not_connected_by_default(self):
        """Test that client is not connected by default."""
        client = MCPClient("npx", [], 30)
        assert not client.is_connected()

    def test_call_tool_without_connection_raises_error(self):
        """Test that calling tool without connection raises error."""
        client = MCPClient("npx", [], 30)

        with pytest.raises(MCPConnectionError) as exc_info:
            client._call_tool("test_tool", {})

        assert "Not connected" in str(exc_info.value)

    def test_validate_server_command_nonexistent(self):
        """Test validation of non-existent server command."""
        client = MCPClient("nonexistent_command_12345", [], 30)

        with pytest.raises(FileNotFoundError):
            client._validate_server_command()

    def test_validate_server_command_existing(self):
        """Test validation of existing server command."""
        # Use a command that should exist on most systems
        client = MCPClient("ls", [], 30)

        # Should not raise
        client._validate_server_command()

    def test_search_notes_not_connected(self):
        """Test search_notes raises error when not connected."""
        client = MCPClient("npx", [], 30)

        with pytest.raises(MCPConnectionError):
            client.search_notes()

    def test_read_note_not_connected(self):
        """Test read_note raises error when not connected."""
        client = MCPClient("npx", [], 30)

        with pytest.raises(MCPConnectionError):
            client.read_note("test.md")

    def test_create_note_not_connected(self):
        """Test create_note raises error when not connected."""
        client = MCPClient("npx", [], 30)

        with pytest.raises(MCPConnectionError):
            client.create_note("test.md", "content")

    def test_context_manager_structure(self):
        """Test that context manager methods exist."""
        client = MCPClient("npx", [], 30)

        # Check that __enter__ and __exit__ exist
        assert hasattr(client, '__enter__')
        assert hasattr(client, '__exit__')

    def test_disconnect_when_not_connected(self):
        """Test that disconnect works even when not connected."""
        client = MCPClient("npx", [], 30)

        # Should not raise
        client.disconnect()
        assert not client.is_connected()
