"""
Configuration module for MCP Bookkeeping Server

Handles environment variables, database settings, and server configuration.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    host: str = "localhost"
    port: int = 5432
    database: str = "bookkeeping"
    user: str = "bookkeeper"
    password: str = ""
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create config from environment variables."""
        return cls(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'bookkeeping'),
            user=os.getenv('DB_USER', 'bookkeeper'),
            password=os.getenv('DB_PASSWORD', '')
        )
    
    @property
    def connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        return f"host={self.host} port={self.port} dbname={self.database} user={self.user} password={self.password}"

@dataclass
class ServerConfig:
    """MCP Server configuration settings."""
    name: str = "bookkeeping-mcp-server"
    version: str = "1.0.0"
    description: str = "AI Bookkeeping MCP Server with PostgreSQL Backend"
    
    # Database settings
    database: DatabaseConfig = None
    
    # Server settings
    debug: bool = False
    log_level: str = "INFO"
    
    # Features
    enable_ai_categorization: bool = True
    enable_duplicate_detection: bool = True
    
    def __post_init__(self):
        """Initialize database config if not provided."""
        if self.database is None:
            self.database = DatabaseConfig.from_env()

def get_config() -> ServerConfig:
    """Get server configuration from environment."""
    return ServerConfig(
        name=os.getenv('MCP_SERVER_NAME', 'bookkeeping-mcp-server'),
        version=os.getenv('MCP_SERVER_VERSION', '1.0.0'),
        description=os.getenv('MCP_SERVER_DESCRIPTION', 'AI Bookkeeping MCP Server with PostgreSQL Backend'),
        debug=os.getenv('DEBUG', 'false').lower() == 'true',
        log_level=os.getenv('LOG_LEVEL', 'INFO'),
        enable_ai_categorization=os.getenv('ENABLE_AI_CATEGORIZATION', 'true').lower() == 'true',
        enable_duplicate_detection=os.getenv('ENABLE_DUPLICATE_DETECTION', 'true').lower() == 'true',
        database=DatabaseConfig.from_env()
    )

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent

def get_schema_path() -> Path:
    """Get path to database schema file."""
    return get_project_root() / "database" / "db_schema.sql"

def get_env_file_path() -> Path:
    """Get path to .env file."""
    return get_project_root() / ".env"