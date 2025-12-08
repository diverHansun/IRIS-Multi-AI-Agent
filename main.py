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
    """Configure logging with proper module hierarchy and third-party filtering"""
    # Set base logging level
    base_level = logging.DEBUG if debug else logging.WARNING

    logging.basicConfig(
        level=base_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Always suppress verbose third-party library logging
    # These libraries are too chatty even in debug mode
    suppressed_loggers = {
        'langchain': logging.WARNING,
        'langchain_core': logging.WARNING,
        'langgraph': logging.WARNING,
        'openai': logging.WARNING,
        'httpx': logging.WARNING,
        'aiohttp': logging.WARNING,
        'ollama': logging.WARNING,
        'mcp': logging.WARNING,
        'urllib3': logging.WARNING,
        'requests': logging.WARNING,
    }

    for logger_name, level in suppressed_loggers.items():
        logging.getLogger(logger_name).setLevel(level)

    # If debug is enabled, enable debug logging for project code only
    if debug:
        # Set project code to DEBUG level
        logging.getLogger('src').setLevel(logging.DEBUG)
        # Optionally allow INFO level for third-party libs in debug mode
        for logger_name in suppressed_loggers:
            logging.getLogger(logger_name).setLevel(logging.INFO)


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
