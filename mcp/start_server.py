#!/usr/bin/env python3
"""
MCP Bookkeeping Server Startup Script

This script starts the FastMCP bookkeeping server with proper configuration
and database connectivity.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from mcp.server import BookkeepingMCPServer
    from mcp.config import get_config
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running from the project root and have installed dependencies.")
    sys.exit(1)

def main():
    """Main entry point for the MCP server."""
    try:
        # Load configuration
        config = get_config()
        
        print(f"🚀 Starting {config.name} v{config.version}")
        print(f"📝 {config.description}")
        print(f"🔗 Database: {config.database.host}:{config.database.port}/{config.database.database}")
        
        # Create and start server
        server = BookkeepingMCPServer(config)
        
        print("✅ MCP Server started successfully!")
        print("💡 The server is now ready to handle MCP requests.")
        print("🔌 Connect your AI client to start using the bookkeeping tools.")
        
        # Start the server (this will run indefinitely)
        server.run()
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down MCP server...")
    except Exception as e:
        print(f"❌ Error starting MCP server: {e}")
        if config.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()