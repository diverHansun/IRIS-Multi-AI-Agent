"""
AI Agent Demo - Main Program

Provides command-line interface and async demo functionality.
Simplified version using the new MCP integration architecture.
"""

import asyncio
import sys
import os

# Set console encoding
sys.stdout.reconfigure(encoding='utf-8')
# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run CLI
from src.application.cli.main import run


def main():
    """Main function"""
    # Run CLI
    asyncio.run(run())


if __name__ == "__main__":
    # Run main program
    main()
