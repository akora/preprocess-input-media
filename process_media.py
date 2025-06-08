#!/usr/bin/env python3
"""
Media File Pre-Processing System - Command Line Interface

This script provides a command-line interface to process media files.
It accepts parameters for input/output directories, timezone, and other options.
"""

import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import the main function from src.main
from src.main import main

if __name__ == "__main__":
    sys.exit(main())
