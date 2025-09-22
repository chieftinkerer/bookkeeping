#!/usr/bin/env python3
"""
FastMCP Bookkeeping Server

Main server implementation using FastMCP framework for AI bookkeeping capabilities.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastmcp import FastMCP
from mcp.utils.database_manager import DatabaseManager
from mcp.tools.transaction_tools import TransactionTools
from mcp.tools.analysis_tools import AnalysisTools
from mcp.tools.management_tools import ManagementTools
from mcp.config import ServerConfig, get_config


class BookkeepingMCPServer:
    """FastMCP server for AI bookkeeping operations."""
    
    def __init__(self, config: ServerConfig = None):
        """Initialize the MCP server with configuration."""
        self.config = config or get_config()
        
        # Initialize FastMCP server
        self.app = FastMCP(
            name=self.config.name,
            version=self.config.version,
            description=self.config.description
        )
        
        # Initialize database manager
        self.db_manager = DatabaseManager(self.config.database.connection_string)
        
        # Initialize tool modules
        self.transaction_tools = TransactionTools(self.db_manager)
        self.analysis_tools = AnalysisTools(self.db_manager)
        self.management_tools = ManagementTools(self.db_manager)
        
        # Register tools
        self._register_tools()
    
    def _register_tools(self):
        """Register all MCP tools with the FastMCP server."""
        
        # Transaction tools
        self.app.tool("query_transactions")(
            self.transaction_tools.query_transactions
        )
        self.app.tool("add_transaction")(
            self.transaction_tools.add_transaction
        )
        self.app.tool("find_duplicates")(
            self.transaction_tools.find_duplicates
        )
        
        # Analysis tools
        self.app.tool("monthly_summary")(
            self.analysis_tools.monthly_summary
        )
        self.app.tool("spending_analysis")(
            self.analysis_tools.spending_analysis
        )
        self.app.tool("category_breakdown")(
            self.analysis_tools.category_breakdown
        )
        self.app.tool("vendor_analysis")(
            self.analysis_tools.vendor_analysis
        )
        
        # Management tools
        self.app.tool("get_categories")(
            self.management_tools.get_categories
        )
        self.app.tool("update_vendor_mapping")(
            self.management_tools.update_vendor_mapping
        )
        self.app.tool("get_vendor_mappings")(
            self.management_tools.get_vendor_mappings
        )
        self.app.tool("database_stats")(
            self.management_tools.database_stats
        )
        
        # Duplicate review tools
        self.app.tool("stage_duplicates_for_review")(
            self.management_tools.stage_duplicates_for_review
        )
        self.app.tool("get_duplicate_review_queue")(
            self.management_tools.get_duplicate_review_queue
        )
        self.app.tool("review_duplicate")(
            self.management_tools.review_duplicate
        )
        self.app.tool("delete_transaction")(
            self.management_tools.delete_transaction
        )
        
        # Categorization review tools
        self.app.tool("get_uncategorized_transactions")(
            self.management_tools.get_uncategorized_transactions
        )
        self.app.tool("get_vendor_mapping_suggestions")(
            self.management_tools.get_vendor_mapping_suggestions
        )
    
    def run(self):
        """Start the MCP server."""
        return self.app.run()


# For direct execution
if __name__ == "__main__":
    import dotenv
    
    # Load environment variables
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        dotenv.load_dotenv(env_file)
    
    # Create and run server
    config = get_config()
    server = BookkeepingMCPServer(config)
    
    print(f"🚀 Starting {config.name} v{config.version}")
    print(f"📝 {config.description}")
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")

import sys
import os
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastmcp import FastMCP
from mcp.utils.database_manager import DatabaseManager
from mcp.tools.transaction_tools import TransactionTools
from mcp.tools.analysis_tools import AnalysisTools
from mcp.tools.management_tools import ManagementTools
from mcp.config import ServerConfig, get_config

import logging
from typing import Dict, Any
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from fastmcp import FastMCP
from dotenv import load_dotenv

# Import our tool modules
from tools.transaction_tools import TransactionTools
from tools.analysis_tools import AnalysisTools
from tools.management_tools import ManagementTools
from utils.database_manager import DatabaseManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BookkeepingMCPServer:
    """FastMCP-based server for AI bookkeeping operations."""
    
    def __init__(self):
        """Initialize the MCP server with all tools."""
        self.mcp = FastMCP("AI Bookkeeping Server")
        
        # Initialize database manager
        try:
            self.db_manager = DatabaseManager()
            logger.info("Database connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
        
        # Initialize tool modules
        self.transaction_tools = TransactionTools(self.db_manager)
        self.analysis_tools = AnalysisTools(self.db_manager)
        self.management_tools = ManagementTools(self.db_manager)
        
        # Register all tools
        self._register_tools()
        
        logger.info("BookkeepingMCPServer initialized with FastMCP")
    
    def _register_tools(self):
        """Register all MCP tools with the FastMCP server."""
        
        # Register transaction tools
        self.mcp.tool()(self.transaction_tools.query_transactions)
        self.mcp.tool()(self.transaction_tools.add_transaction)
        self.mcp.tool()(self.transaction_tools.find_duplicates)
        
        # Register analysis tools
        self.mcp.tool()(self.analysis_tools.monthly_summary)
        self.mcp.tool()(self.analysis_tools.spending_analysis)
        self.mcp.tool()(self.analysis_tools.category_breakdown)
        self.mcp.tool()(self.analysis_tools.vendor_analysis)
        
        # Register management tools
        self.mcp.tool()(self.management_tools.get_categories)
        self.mcp.tool()(self.management_tools.update_vendor_mapping)
        self.mcp.tool()(self.management_tools.database_stats)
        self.mcp.tool()(self.management_tools.get_vendor_mappings)
        
        logger.info(f"Registered {len(self.mcp._tools)} MCP tools")
    
    def run(self):
        """Run the MCP server."""
        logger.info("Starting AI Bookkeeping MCP Server...")
        
        # Validate database connection and schema
        try:
            stats = self.management_tools.database_stats()
            logger.info(f"Database ready: {stats}")
        except Exception as e:
            logger.error(f"Database validation failed: {e}")
            raise
        
        # Start the FastMCP server
        try:
            self.mcp.run()
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise

def main():
    """Main entry point for the MCP server."""
    try:
        server = BookkeepingMCPServer()
        server.run()
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()