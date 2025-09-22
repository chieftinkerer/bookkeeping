"""
MCP Bookkeeping Server Package

FastMCP-based AI bookkeeping server with PostgreSQL backend.
"""

__version__ = "1.0.0"
__author__ = "AI Assistant"
__description__ = "AI Bookkeeping MCP Server with PostgreSQL Backend"

from .server import BookkeepingMCPServer
from .config import get_config, ServerConfig, DatabaseConfig

__all__ = [
    "BookkeepingMCPServer",
    "get_config", 
    "ServerConfig",
    "DatabaseConfig"
]