"""
Crawl4AI connector tools initialization
"""

from .adapter import Crawl4AICrawlTool


def get_tools():
    """Get all Crawl4AI connector tools."""
    return [
        Crawl4AICrawlTool(),
    ]


def register():
    """Register Crawl4AI connector tools."""
    # This can be expanded if needed for future registration logic
    pass