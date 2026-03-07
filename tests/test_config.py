"""Tests for configuration management."""

import os
import tempfile
from pathlib import Path
import pytest
import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import Config


class TestConfig:
    """Test configuration loading and access."""

    def test_config_loads_default_file(self):
        """Test that default config file loads successfully."""
        config = Config()
        assert config._config is not None
        assert isinstance(config._config, dict)

    def test_get_with_dot_notation(self):
        """Test getting values with dot notation."""
        config = Config()

        # Test existing keys
        obsidian_timeout = config.get("obsidian.timeout")
        assert obsidian_timeout is not None

        # Test non-existing keys with default
        assert config.get("nonexistent.key", "default") == "default"

    def test_obsidian_properties(self):
        """Test Obsidian CLI-related properties."""
        config = Config()

        assert isinstance(config.obsidian_vault_path, str)
        assert config.obsidian_cli_path is None or isinstance(config.obsidian_cli_path, str)
        assert isinstance(config.obsidian_timeout, int)
        assert config.obsidian_timeout > 0

    def test_claude_properties(self):
        """Test Claude API properties."""
        config = Config()

        assert isinstance(config.claude_api_key_env, str)
        assert isinstance(config.claude_model, str)
        assert isinstance(config.claude_max_tokens, int)
        assert isinstance(config.claude_temperature, float)

    def test_scanning_properties(self):
        """Test scanning configuration properties."""
        config = Config()

        assert isinstance(config.scan_timeframe_days, int)
        assert config.scan_timeframe_days == 7
        assert isinstance(config.check_interval_seconds, int)

    def test_rate_limit_properties(self):
        """Test rate limiting properties."""
        config = Config()

        assert isinstance(config.max_requests_per_hour, int)
        assert config.max_requests_per_hour > 0

    def test_response_properties(self):
        """Test response configuration properties."""
        config = Config()

        assert isinstance(config.response_max_length, int)
        assert config.response_max_length == 5000
        assert isinstance(config.response_include_timestamp, bool)
        assert isinstance(config.response_note_suffix, str)

    def test_logging_properties(self):
        """Test logging properties."""
        config = Config()

        assert isinstance(config.log_level, str)
        assert isinstance(config.log_file, str)
        assert isinstance(config.log_max_size, int)
        assert isinstance(config.log_backup_count, int)

    def test_dry_run_property(self):
        """Test dry run property."""
        config = Config()

        assert isinstance(config.dry_run, bool)

    def test_get_allowed_tools_default(self):
        """Test getting default allowed tools."""
        config = Config()

        tools = config.get_allowed_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert "obsidian_read_note" in tools

    def test_get_allowed_tools_vault_specific(self):
        """Test getting vault-specific allowed tools."""
        config = Config()

        # Test with non-existent vault (should return default)
        tools = config.get_allowed_tools("/nonexistent/vault")
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_custom_config_file(self):
        """Test loading a custom config file."""
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_config = {
                "obsidian": {"timeout": 99, "vault_path": "/tmp/test"},
                "claude": {"model": "test-model"},
                "scanning": {"recent_timeframe": 14}
            }
            yaml.dump(temp_config, f)
            temp_path = f.name

        try:
            config = Config(config_path=temp_path)
            assert config.get("obsidian.timeout") == 99
            assert config.get("claude.model") == "test-model"
            assert config.get("scanning.recent_timeframe") == 14
        finally:
            os.unlink(temp_path)

    def test_missing_config_file_raises_error(self):
        """Test that missing config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            Config(config_path="/nonexistent/config.yaml")

    def test_reload_config(self):
        """Test reloading configuration."""
        config = Config()
        original_timeout = config.get("obsidian.timeout")

        # Reload should not fail
        config.reload()

        # Values should still be accessible
        assert config.get("obsidian.timeout") == original_timeout
