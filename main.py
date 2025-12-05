"""
AI Agent Demo - Main Program

Provides command-line interface and async demo functionality.
Simplified version using the new MCP integration architecture.
"""

import asyncio
import sys
import os
import logging
import argparse

# Set console encoding
sys.stdout.reconfigure(encoding='utf-8')
# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def setup_logging(debug: bool = False):
    """Configure logging based on debug flag"""
    # Set base logging level
    base_level = logging.DEBUG if debug else logging.WARNING

    logging.basicConfig(
        level=base_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # If debug is enabled, set all loggers to DEBUG level
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)


# Import and run CLI
from src.application.cli.main import run


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Multi-LLM Agent Demo',
        add_help=True
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode to show detailed logging information'
    )
    return parser.parse_args()


def main():
    """Main function"""
    # Parse command line arguments
    args = parse_arguments()

    # Setup logging based on debug flag
    setup_logging(debug=args.debug)

    # Run CLI
    asyncio.run(run())


if __name__ == "__main__":
    # Run main program
    main()
