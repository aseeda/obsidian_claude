"""Configuration management for Obsidian-Claude Agent."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


class Config:
    """Manages configuration loading and access for the agent."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Optional path to custom config file.
                        If None, uses default config location.
        """
        self.config_dir = Path(__file__).parent.parent / "config"
        self.config_path = Path(config_path) if config_path else self.config_dir / "default_config.yaml"
        self.permissions_path = self.config_dir / "vault_permissions.yaml"

        self._config: Dict[str, Any] = {}
        self._permissions: Dict[str, Any] = {}

        self._load_config()
        self._load_permissions()

    def _load_config(self) -> None:
        """Load main configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f) or {}

    def _load_permissions(self) -> None:
        """Load vault permissions from YAML file."""
        if not self.permissions_path.exists():
            # Use default empty permissions if file doesn't exist
            self._permissions = {"default": {"allowed_tools": []}}
            return

        with open(self.permissions_path, 'r') as f:
            self._permissions = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Args:
            key: Configuration key in dot notation (e.g., 'mcp.timeout')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def get_allowed_tools(self, vault_path: Optional[str] = None) -> List[str]:
        """
        Get allowed tools for a specific vault or default.

        Args:
            vault_path: Path to the vault. If None, returns default permissions.

        Returns:
            List of allowed tool names
        """
        # Check vault-specific permissions first
        if vault_path and "vaults" in self._permissions:
            vault_perms = self._permissions["vaults"].get(vault_path)
            if vault_perms and "allowed_tools" in vault_perms:
                return vault_perms["allowed_tools"]

        # Fall back to default permissions
        default_perms = self._permissions.get("default", {})
        return default_perms.get("allowed_tools", [])

    @property
    def obsidian_vault_path(self) -> str:
        """Get Obsidian vault path."""
        return self.get("obsidian.vault_path", "/path/to/vault")

    @property
    def obsidian_cli_path(self) -> Optional[str]:
        """Get Obsidian CLI binary path (None for auto-detect)."""
        return self.get("obsidian.cli_path", None)

    @property
    def obsidian_timeout(self) -> int:
        """Get Obsidian CLI timeout in seconds."""
        return self.get("obsidian.timeout", 30)

    @property
    def claude_api_key_env(self) -> str:
        """Get environment variable name for Claude API key."""
        return self.get("claude.api_key_env", "ANTHROPIC_API_KEY")

    @property
    def claude_api_key(self) -> str:
        """Get Claude API key from environment."""
        env_var = self.claude_api_key_env
        api_key = os.environ.get(env_var)
        if not api_key:
            raise ValueError(f"Claude API key not found in environment variable: {env_var}")
        return api_key

    @property
    def claude_model(self) -> str:
        """Get Claude model name."""
        return self.get("claude.model", "claude-sonnet-4-5-20250929")

    @property
    def claude_max_tokens(self) -> int:
        """Get Claude max tokens."""
        return self.get("claude.max_tokens", 4000)

    @property
    def claude_temperature(self) -> float:
        """Get Claude temperature."""
        return self.get("claude.temperature", 0.7)

    @property
    def scan_timeframe_days(self) -> int:
        """Get recent timeframe in days."""
        return self.get("scanning.recent_timeframe", 7)

    @property
    def scanning_timeframe_days(self) -> int:
        """Alias for scan_timeframe_days."""
        return self.scan_timeframe_days

    @property
    def check_interval_seconds(self) -> int:
        """Get check interval in seconds."""
        return self.get("scanning.check_interval", 300)

    @property
    def max_requests_per_hour(self) -> int:
        """Get maximum requests per hour."""
        return self.get("rate_limit.max_requests_per_hour", 5)

    @property
    def rate_limit_max_per_hour(self) -> int:
        """Alias for max_requests_per_hour."""
        return self.max_requests_per_hour

    @property
    def state_file(self) -> str:
        """Get state file path."""
        return self.get("state.file", "state/processed_requests.json")

    @property
    def response_max_length(self) -> int:
        """Get maximum response length in characters."""
        return self.get("response.max_length", 5000)

    @property
    def response_include_timestamp(self) -> bool:
        """Get whether to include timestamp in responses."""
        return self.get("response.include_timestamp", True)

    @property
    def response_note_suffix(self) -> str:
        """Get response note suffix pattern."""
        return self.get("response.note_suffix", "_response_")

    @property
    def response_suffix(self) -> str:
        """Alias for response_note_suffix."""
        return self.response_note_suffix

    @property
    def default_allowed_tools(self) -> List[str]:
        """Get default allowed tools."""
        return self.get_allowed_tools()

    @property
    def log_level(self) -> str:
        """Get logging level."""
        return self.get("logging.level", "DEBUG")

    @property
    def logging_level(self) -> str:
        """Alias for log_level."""
        return self.log_level

    @property
    def log_file(self) -> str:
        """Get log file path."""
        return self.get("logging.file", "logs/agent.log")

    @property
    def logging_file(self) -> str:
        """Alias for log_file."""
        return self.log_file

    @property
    def log_max_size(self) -> int:
        """Get log file max size in bytes."""
        return self.get("logging.max_size", 10485760)

    @property
    def logging_max_size(self) -> int:
        """Alias for log_max_size."""
        return self.log_max_size

    @property
    def log_backup_count(self) -> int:
        """Get number of log backup files to keep."""
        return self.get("logging.backup_count", 5)

    @property
    def logging_backup_count(self) -> int:
        """Alias for log_backup_count."""
        return self.log_backup_count

    @property
    def dry_run(self) -> bool:
        """Get whether dry run mode is enabled."""
        return self.get("dry_run", False)

    def reload(self) -> None:
        """Reload configuration from files."""
        self._load_config()
        self._load_permissions()
