# MCP Bookkeeping Server

FastMCP-based server providing AI bookkeeping capabilities with PostgreSQL backend.

## Features

- 📊 **Transaction Management**: Add, query, and analyze financial transactions
- 🤖 **AI Categorization**: Automatically categorize transactions using AI
- 🔍 **Smart Search**: Find transactions by amount, date, vendor, or category
- 📈 **Financial Analysis**: Monthly summaries, spending analysis, category breakdowns
- 🏪 **Vendor Mapping**: Automatic categorization rules for recurring vendors
- 🔄 **Duplicate Detection**: Identify and handle duplicate transactions
- 🗄️ **Database Management**: PostgreSQL backend with comprehensive schema

## Quick Start

1. **Setup Environment**:
   ```bash
   # Copy environment configuration
   cp mcp/.env.example mcp/.env
   
   # Edit with your database settings
   nano mcp/.env
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup Database**:
   ```bash
   # Create PostgreSQL database and user
   sudo -u postgres psql -c "CREATE DATABASE bookkeeping;"
   sudo -u postgres psql -c "CREATE USER bookkeeper WITH PASSWORD 'your_password';"
   sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE bookkeeping TO bookkeeper;"
   
   # Initialize schema
   psql -h localhost -U bookkeeper -d bookkeeping -f db_schema.sql
   ```

4. **Start Server**:
   ```bash
   python mcp/start_server.py
   ```

## Directory Structure

```
mcp/
├── server.py              # Main FastMCP server implementation
├── config.py              # Configuration management
├── start_server.py        # Server startup script
├── .env.example           # Environment configuration template
├── utils/
│   └── database_manager.py # Database connection and operations
└── tools/
    ├── transaction_tools.py # Transaction management tools
    ├── analysis_tools.py   # Financial analysis tools
    └── management_tools.py  # Database and system management tools
```

## Available Tools

### Transaction Tools
- `query_transactions` - Search and filter transactions
- `add_transaction` - Add new transactions to database
- `find_duplicates` - Detect potential duplicate transactions

### Analysis Tools
- `monthly_summary` - Get monthly spending summaries
- `spending_analysis` - Analyze spending patterns and trends
- `category_breakdown` - Breakdown spending by categories
- `vendor_analysis` - Analyze spending by vendors

### Management Tools
- `get_categories` - List all available categories
- `update_vendor_mapping` - Configure automatic categorization rules
- `get_vendor_mappings` - View current vendor mapping rules
- `database_stats` - Get database health and statistics

## Configuration

The server uses environment variables for configuration. Key settings:

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - Database connection
- `DEBUG` - Enable debug mode for detailed error information
- `ENABLE_AI_CATEGORIZATION` - Enable AI-powered transaction categorization
- `ENABLE_DUPLICATE_DETECTION` - Enable automatic duplicate detection

## Usage with AI Clients

Once running, the MCP server can be connected to AI clients like Claude Desktop:

1. Add server configuration to your AI client
2. Use natural language to interact with your bookkeeping data
3. Ask questions like:
   - "Show me my spending for last month"
   - "Add a $50 grocery transaction from Whole Foods"
   - "What are my top spending categories?"
   - "Find any duplicate transactions"

## Database Schema

The PostgreSQL database includes:

- `transactions` - Main transaction records with deduplication support
- `categories` - Spending categories with descriptions
- `vendor_mappings` - Rules for automatic categorization
- `processing_log` - Audit trail for data processing operations
- Views and triggers for data integrity and automation

## Troubleshooting

1. **Import Errors**: Make sure you're running from the project root directory
2. **Database Connection**: Check your PostgreSQL service and credentials
3. **FastMCP Issues**: Ensure you have the latest fastmcp package installed
4. **Permission Errors**: Check database user permissions and file access

For detailed logs, enable debug mode in your `.env` file.