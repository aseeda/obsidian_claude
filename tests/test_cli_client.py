"""Tests for Obsidian CLI client."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import subprocess

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cli_client import ObsidianCLIClient
from exceptions import MCPConnectionError, MCPError


class TestObsidianCLIClient:
    """Test Obsidian CLI client functionality."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)

            # Create .obsidian directory to make it look like a valid vault
            obsidian_dir = vault_path / ".obsidian"
            obsidian_dir.mkdir()

            # Create some test notes
            (vault_path / "test_note.md").write_text("# Test Note\n\nThis is a test.")
            (vault_path / "another_note.md").write_text("# Another Note\n\n@claude test")

            # Create a subdirectory with a note
            subdir = vault_path / "subfolder"
            subdir.mkdir()
            (subdir / "nested_note.md").write_text("# Nested Note\n\nNested content")

            yield vault_path

    def test_init_valid_vault(self, temp_vault):
        """Test initialization with valid vault path."""
        client = ObsidianCLIClient(
            vault_path=str(temp_vault),
            timeout=30
        )

        # Use resolve() to handle /var vs /private/var on macOS
        assert client.vault_path.resolve() == temp_vault.resolve()
        assert client.timeout == 30
        assert not client.is_connected()

    def test_init_invalid_vault_path(self):
        """Test initialization with invalid vault path."""
        with pytest.raises(MCPConnectionError) as exc_info:
            ObsidianCLIClient(vault_path="/nonexistent/path")

        assert "does not exist" in str(exc_info.value)

    def test_init_vault_path_is_file(self, temp_vault):
        """Test initialization with file instead of directory."""
        test_file = temp_vault / "test.txt"
        test_file.write_text("test")

        with pytest.raises(MCPConnectionError) as exc_info:
            ObsidianCLIClient(vault_path=str(test_file))

        assert "not a directory" in str(exc_info.value)

    def test_connect(self, temp_vault):
        """Test connecting to vault."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))

        assert not client.is_connected()
        client.connect()
        assert client.is_connected()

    def test_disconnect(self, temp_vault):
        """Test disconnecting from vault."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        assert client.is_connected()
        client.disconnect()
        assert not client.is_connected()

    def test_context_manager(self, temp_vault):
        """Test using client as context manager."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))

        assert not client.is_connected()

        with client:
            assert client.is_connected()

        assert not client.is_connected()

    def test_search_notes_not_connected(self, temp_vault):
        """Test search_notes raises error when not connected."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))

        with pytest.raises(MCPConnectionError) as exc_info:
            client.search_notes()

        assert "Not connected" in str(exc_info.value)

    def test_search_notes_all(self, temp_vault):
        """Test searching for all notes."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        notes = client.search_notes()

        # Should find 3 notes (excluding files in .obsidian)
        assert len(notes) == 3

        # Check note structure
        for note in notes:
            assert "path" in note
            assert "title" in note
            assert "modified" in note
            assert "created" in note

    def test_search_notes_with_query(self, temp_vault):
        """Test searching notes with query."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        # Search for "@claude"
        notes = client.search_notes(query="@claude")

        assert len(notes) == 1
        assert notes[0]["title"] == "another_note"

    def test_search_notes_with_modified_since(self, temp_vault):
        """Test searching notes with modified_since filter."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        # Search for notes modified in the last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        notes = client.search_notes(modified_since=one_hour_ago)

        # All test notes should be recent
        assert len(notes) == 3

    def test_read_note(self, temp_vault):
        """Test reading a note."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        content = client.read_note("test_note.md")

        assert "# Test Note" in content
        assert "This is a test" in content

    def test_read_note_not_connected(self, temp_vault):
        """Test read_note raises error when not connected."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))

        with pytest.raises(MCPConnectionError):
            client.read_note("test_note.md")

    def test_read_note_not_found(self, temp_vault):
        """Test reading non-existent note."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        with pytest.raises(MCPError) as exc_info:
            client.read_note("nonexistent.md")

        assert "not found" in str(exc_info.value)

    def test_create_note(self, temp_vault):
        """Test creating a new note."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        result = client.create_note("new_note.md", "# New Note\n\nNew content")

        assert result["success"] is True
        assert (temp_vault / "new_note.md").exists()

        # Verify content
        content = (temp_vault / "new_note.md").read_text()
        assert "# New Note" in content

    def test_create_note_with_subdirectory(self, temp_vault):
        """Test creating note in subdirectory that doesn't exist."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        result = client.create_note("new_folder/new_note.md", "# New Note")

        assert result["success"] is True
        assert (temp_vault / "new_folder" / "new_note.md").exists()

    def test_create_note_already_exists(self, temp_vault):
        """Test creating note that already exists."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        with pytest.raises(MCPError) as exc_info:
            client.create_note("test_note.md", "New content")

        assert "already exists" in str(exc_info.value)

    def test_create_note_with_overwrite(self, temp_vault):
        """Test creating note with overwrite flag."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        result = client.create_note("test_note.md", "# Overwritten", overwrite=True)

        assert result["success"] is True
        content = (temp_vault / "test_note.md").read_text()
        assert "# Overwritten" in content

    def test_update_note(self, temp_vault):
        """Test updating an existing note."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        result = client.update_note("test_note.md", "# Updated Note")

        assert result["success"] is True
        content = (temp_vault / "test_note.md").read_text()
        assert "# Updated Note" in content

    def test_update_note_not_found(self, temp_vault):
        """Test updating non-existent note."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        with pytest.raises(MCPError) as exc_info:
            client.update_note("nonexistent.md", "New content")

        assert "not found" in str(exc_info.value)

    def test_append_to_note(self, temp_vault):
        """Test appending to an existing note."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        original_content = client.read_note("test_note.md")

        result = client.append_to_note("test_note.md", "\n\nAppended content")

        assert result["success"] is True

        new_content = client.read_note("test_note.md")
        assert new_content.startswith(original_content)
        assert "Appended content" in new_content

    def test_append_to_note_not_found(self, temp_vault):
        """Test appending to non-existent note."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))
        client.connect()

        with pytest.raises(MCPError) as exc_info:
            client.append_to_note("nonexistent.md", "Content")

        assert "not found" in str(exc_info.value)

    @patch('cli_client.platform.system')
    def test_cli_binary_detection_linux(self, mock_system):
        """Test CLI binary detection on Linux."""
        mock_system.return_value = 'Linux'

        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            (vault_path / ".obsidian").mkdir()

            # Create a fake obsidian binary in the temp directory
            fake_bin = vault_path / "fake_obsidian"
            fake_bin.write_text("#!/bin/bash\necho 'fake'")
            fake_bin.chmod(0o755)

            # Mock shutil.which to return our fake binary
            with patch('cli_client.shutil.which', return_value=str(fake_bin)):
                client = ObsidianCLIClient(vault_path=str(vault_path))
                assert client.cli_path == str(fake_bin)

    def test_cli_binary_explicit_path(self, temp_vault):
        """Test providing explicit CLI path."""
        # Create a fake CLI binary
        cli_path = temp_vault / "fake_obsidian"
        cli_path.write_text("#!/bin/bash\necho 'fake'")
        cli_path.chmod(0o755)

        client = ObsidianCLIClient(
            vault_path=str(temp_vault),
            cli_path=str(cli_path)
        )

        assert client.cli_path == str(cli_path)

    def test_operations_without_connection(self, temp_vault):
        """Test that operations fail without connection."""
        client = ObsidianCLIClient(vault_path=str(temp_vault))

        with pytest.raises(MCPConnectionError):
            client.read_note("test.md")

        with pytest.raises(MCPConnectionError):
            client.create_note("test.md", "content")

        with pytest.raises(MCPConnectionError):
            client.update_note("test.md", "content")

        with pytest.raises(MCPConnectionError):
            client.append_to_note("test.md", "content")
