"""
Package entry point for running as a module.

Usage: python -m src
"""

from .main import main
import sys

if __name__ == '__main__':
    sys.exit(main())
