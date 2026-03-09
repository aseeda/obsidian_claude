#!/bin/bash
#
# Crontab Setup Helper for Obsidian-Claude Agent
#
# This script helps install, uninstall, and manage crontab entries for
# automated agent execution.
#
# Usage:
#   ./setup-cron.sh install   - Install crontab entry
#   ./setup-cron.sh uninstall - Remove crontab entry
#   ./setup-cron.sh status    - Check if crontab entry exists
#   ./setup-cron.sh show      - Display the crontab entry that would be created

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config/default_config.yaml"
WRAPPER_SCRIPT="$SCRIPT_DIR/run-with-env.sh"
LOG_FILE="$PROJECT_ROOT/logs/cron.log"

# Marker to identify our crontab entry
CRON_MARKER="# Obsidian-Claude Agent"

# Function to read check_interval from config
get_check_interval() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "${RED}Error: Config file not found at $CONFIG_FILE${NC}" >&2
        exit 1
    fi

    # Try to read check_interval using python
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "import yaml; config=yaml.safe_load(open('$CONFIG_FILE')); print(config['scanning']['check_interval'])" 2>/dev/null || echo "300"
    else
        # Fallback: grep and parse (assumes simple YAML structure)
        grep "check_interval:" "$CONFIG_FILE" | awk '{print $2}' | head -1 || echo "300"
    fi
}

# Function to convert seconds to cron expression
seconds_to_cron() {
    local seconds=$1
    local minutes=$((seconds / 60))

    if [ $minutes -lt 1 ]; then
        echo "* * * * *"  # Every minute (minimum cron granularity)
    elif [ $minutes -lt 60 ]; then
        echo "*/$minutes * * * *"  # Every N minutes
    else
        local hours=$((minutes / 60))
        echo "0 */$hours * * *"  # Every N hours
    fi
}

# Function to generate crontab entry
generate_cron_entry() {
    local interval=$(get_check_interval)
    local cron_expr=$(seconds_to_cron $interval)

    echo "$CRON_MARKER (every $interval seconds)"
    echo "$cron_expr $WRAPPER_SCRIPT >> $LOG_FILE 2>&1"
}

# Function to check if crontab entry exists
entry_exists() {
    crontab -l 2>/dev/null | grep -q "$CRON_MARKER"
}

# Function to install crontab entry
install() {
    echo "Installing Obsidian-Claude crontab entry..."

    # Verify wrapper script exists
    if [ ! -f "$WRAPPER_SCRIPT" ]; then
        echo "${RED}Error: Wrapper script not found at $WRAPPER_SCRIPT${NC}"
        exit 1
    fi

    # Make sure wrapper is executable
    chmod +x "$WRAPPER_SCRIPT"

    # Create logs directory if it doesn't exist
    mkdir -p "$PROJECT_ROOT/logs"

    # Check if entry already exists
    if entry_exists; then
        echo "${YELLOW}Warning: Crontab entry already exists${NC}"
        echo "Run '$0 uninstall' first to remove the old entry"
        exit 1
    fi

    # Get current crontab
    local current_crontab=$(crontab -l 2>/dev/null || echo "")

    # Generate new entry
    local new_entry=$(generate_cron_entry)

    # Add new entry to crontab
    (
        echo "$current_crontab"
        echo ""
        echo "$new_entry"
    ) | crontab -

    echo "${GREEN}✓ Crontab entry installed successfully${NC}"
    echo ""
    echo "The agent will run according to this schedule:"
    echo "$new_entry"
    echo ""
    echo "Logs will be written to: $LOG_FILE"
    echo ""
    echo "To verify: crontab -l"
    echo "To check logs: tail -f $LOG_FILE"
}

# Function to uninstall crontab entry
uninstall() {
    echo "Uninstalling Obsidian-Claude crontab entry..."

    if ! entry_exists; then
        echo "${YELLOW}No crontab entry found${NC}"
        exit 0
    fi

    # Remove our entry from crontab
    crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | grep -v "^$WRAPPER_SCRIPT" | crontab -

    echo "${GREEN}✓ Crontab entry removed successfully${NC}"
}

# Function to show status
status() {
    if entry_exists; then
        echo "${GREEN}✓ Crontab entry is installed${NC}"
        echo ""
        echo "Current entry:"
        crontab -l 2>/dev/null | grep -A1 "$CRON_MARKER"
        echo ""
        echo "Logs location: $LOG_FILE"
        if [ -f "$LOG_FILE" ]; then
            echo "Log file size: $(du -h "$LOG_FILE" | cut -f1)"
            echo ""
            echo "Recent log entries:"
            tail -5 "$LOG_FILE"
        fi
    else
        echo "${YELLOW}✗ Crontab entry is not installed${NC}"
        echo ""
        echo "Run '$0 install' to install"
    fi
}

# Function to show what would be created
show() {
    echo "Crontab entry that would be created:"
    echo ""
    generate_cron_entry
    echo ""
    echo "This will run: $WRAPPER_SCRIPT"
    echo "Logs will go to: $LOG_FILE"
}

# Main command dispatcher
case "${1:-}" in
    install)
        install
        ;;
    uninstall)
        uninstall
        ;;
    status)
        status
        ;;
    show)
        show
        ;;
    *)
        echo "Obsidian-Claude Crontab Setup Helper"
        echo ""
        echo "Usage: $0 {install|uninstall|status|show}"
        echo ""
        echo "Commands:"
        echo "  install    - Install crontab entry for automated execution"
        echo "  uninstall  - Remove crontab entry"
        echo "  status     - Check if crontab entry is installed and show logs"
        echo "  show       - Display the crontab entry that would be created"
        echo ""
        exit 1
        ;;
esac
