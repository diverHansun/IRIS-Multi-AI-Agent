"""
AI Agent Demo - Main Program

Provides command-line interface and async demo functionality.
Simplified version using the new MCP integration architecture.
"""

import asyncio
import sys
import os
import logging

# Set console encoding
sys.stdout.reconfigure(encoding='utf-8')
# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging for debugging memory and session management
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and errors by default
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Enable INFO for critical modules (memory, session, engine switching)
logging.getLogger('src.components.shared.memory.memory_sync').setLevel(logging.INFO)
logging.getLogger('src.application.services.agent.deep.streaming.conversation').setLevel(logging.INFO)
logging.getLogger('src.application.commands.engine_commands').setLevel(logging.INFO)
logging.getLogger('src.application.commands.agent.mode_commands').setLevel(logging.INFO)

# Import and run CLI
from src.application.cli.main import run


def main():
    """Main function"""
    # Run CLI
    asyncio.run(run())


if __name__ == "__main__":
    # Run main program
    main()
