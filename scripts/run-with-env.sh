#!/bin/bash
#
# Environment Wrapper for Cron Execution
#
# This script ensures the Obsidian-Claude agent runs with proper environment
# variables and working directory when invoked by cron.
#
# Usage: /path/to/run-with-env.sh

# Exit on error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

# Load environment variables from .env file if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Loading environment from .env file"
    # Export variables from .env (skip comments and empty lines)
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Warning: .env file not found at $PROJECT_ROOT/.env"
fi

# Check if ANTHROPIC_API_KEY is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: ANTHROPIC_API_KEY not set"
    exit 1
fi

# Find Python 3
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v $cmd >/dev/null 2>&1; then
        if $cmd -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null; then
            PYTHON_CMD=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Python 3.9+ not found"
    exit 1
fi

# Log execution
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Obsidian-Claude agent"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Python: $($PYTHON_CMD --version)"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Working directory: $PROJECT_ROOT"

# Run the agent
$PYTHON_CMD -m src run

# Log completion
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Agent completed successfully"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Agent exited with code $EXIT_CODE"
fi

exit $EXIT_CODE
