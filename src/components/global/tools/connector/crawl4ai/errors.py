"""
Error classes for Crawl4AI connector
"""


class Crawl4AIConnectorError(Exception):
    """Base exception for Crawl4AI connector errors"""
    pass


class Crawl4AIHTTPError(Crawl4AIConnectorError):
    """Exception for HTTP-related errors"""
    
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code