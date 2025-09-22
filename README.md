# AI-Assisted Personal Bookkeeping

This repo contains a **local, privacy-friendly bookkeeping workflow** that combines:

- **Manual CSV exports** from your bank/credit card accounts  
- **Python scripts** to normalize, deduplicate, and import into PostgreSQL database
- **OpenAI API** to automatically categorize expenses  
- **MCP Server** for AI chat interface and natural language queries
- **PostgreSQL backend** for reliable data storage and concurrent access

You keep **all data local** — only anonymized rows (Date, Description, Amount) are sent to the AI for categorization.

---

## 🎯 Current Architecture (PostgreSQL + MCP Server)

### System Features (Sept 22, 2025)
- ✅ **PostgreSQL Backend** - reliable, concurrent database storage
- ✅ **AI Chat Interface** - query data naturally through MCP server
- ✅ **Real-time Interaction** - no file locking issues

### 🏗️ Current Architecture
```
CSV Files → PostgreSQL ← MCP Server ← Claude/AI Chat
                ↓
        Streamlit Dashboard (future)
                +
        Reports & Analytics (on-demand)
```

### 📋 Available Features

#### Database Operations
- ✅ **PostgreSQL Setup** - Complete database schema
- ✅ **CSV Import** - Direct CSV-to-PostgreSQL pipeline
- ✅ **AI Categorization** - Automatic expense categorization
- ✅ **Duplicate Detection** - Identify and handle duplicate transactions

#### MCP Server & AI Chat
- ✅ **Transaction Queries** - Natural language transaction searches
- ✅ **Spending Analysis** - Category breakdowns and trends
- ✅ **Monthly Summaries** - Automated reporting  
- ✅ **Duplicate Management** - Find and handle duplicates
- ✅ **Manual Entry** - Add transactions directly
- ✅ **Database Management** - Category and vendor mapping tools
- [ ] **AI Chat Interface**
  - Enable queries like: *"How much did I spend on groceries in August?"*
  - Support commands: *"Show me a chart of dining vs grocery spending"*
  - Generate insights: *"What are my top 5 expense categories?"*

#### Future Features
- [ ] **Streamlit Dashboard**
  - Interactive charts and graphs
  - Filtering by date, category, amount
  - Trend analysis and comparisons
- [ ] **Advanced Reporting**
  - Automated monthly/quarterly reports
  - Custom analytics and insights
  - Export capabilities (CSV, PDF)

### 🛠️ Technical Requirements

#### Database Schema
```sql
-- Core transactions table
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    description TEXT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    category VARCHAR(50),
    vendor VARCHAR(200),
    source VARCHAR(100),
    txn_id VARCHAR(100),
    reference VARCHAR(100),
    account VARCHAR(50),
    balance DECIMAL(12,2),
    original_hash VARCHAR(32),
    possible_dup_group VARCHAR(20),
    row_hash VARCHAR(32) UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Category mappings
CREATE TABLE vendor_mappings (
    id SERIAL PRIMARY KEY,
    vendor_pattern VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Processing log
CREATE TABLE processing_log (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(200),
    rows_processed INTEGER,
    rows_added INTEGER,
    processing_time INTERVAL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### MCP Server Tools
```python
# Example tool definitions for MCP server
tools = [
    {
        "name": "query_transactions",
        "description": "Query transactions using natural language",
        "parameters": {"query": "string", "limit": "integer"}
    },
    {
        "name": "monthly_summary", 
        "description": "Generate monthly spending summary",
        "parameters": {"month": "string", "year": "integer"}
    },
    {
        "name": "generate_chart",
        "description": "Create spending visualization",
        "parameters": {"chart_type": "string", "category": "string", "date_range": "string"}
    }
]
```

### � Current System Benefits

#### Solved Problems
- ✅ **No file locking** - concurrent access to data
- ✅ **Real-time queries** - chat with your financial data through MCP server
- ✅ **Better performance** - PostgreSQL handles large datasets efficiently
- ✅ **Advanced analytics** - complex SQL queries and aggregations
- ✅ **Automated processing** - background CSV imports and AI categorization
- ✅ **Data integrity** - ACID compliance and transaction safety
- ✅ **AI integration** - Natural language interface to your financial data

#### New Capabilities
- 🤖 **AI Chat**: *"Show me unusual spending patterns this month"*
- 📈 **Interactive Charts**: Real-time visual analysis
- 🔍 **Advanced Search**: Complex queries across all data
- 📱 **Web Access**: Access dashboard from any device
- 🔄 **API Integration**: Connect to other financial tools

---

## 📂 Current Repo Structure

```
bookkeeping/
├── .devcontainer/
│   └── devcontainer.json           # VS Code devcontainer configuration
├── database.py                     # PostgreSQL database utilities and operations
├── db_schema.sql                   # Complete PostgreSQL database schema
├── csv_to_postgres.py              # Import & normalize CSV files to PostgreSQL
├── bookkeeping_helper_postgres.py  # AI categorization with PostgreSQL backend
├── config.py                       # Environment-aware path configuration
├── mcp/                            # FastMCP server implementation
│   ├── server.py                   # Main MCP server
│   ├── tools/                      # MCP tool modules
│   └── utils/                      # Database and utility modules
├── DEVELOPMENT_LOG.md              # Technical development history
├── MIGRATION_COMPLETE.md           # Migration completion documentation
├── README.md                       # This file
├── s3_backup_sync.sh               # S3 backup script
├── S3_README.md                    # S3 configuration documentation
├── s3_restore_sync.sh              # S3 restore script
└── s3_secure_setup.py              # S3 secure bucket setup
```

**Current Data Storage:**
- PostgreSQL database (configurable connection)
- CSV files: Input directory for transaction imports
- Auto-detected via `config.py` path resolution

---

## 🐳 Devcontainer Setup

The repository includes a complete devcontainer configuration for development:

### Features
- **Volume mounting** - Direct access to your Windows financial data
- **Python 3.11** environment with all dependencies
- **PostgreSQL ready** - Port 5432 forwarded for database access
- **Streamlit ready** - Port 8501 forwarded for dashboard
- **Auto-path detection** - Scripts work in both Windows and container environments

### Getting Started
1. Open this repository in VS Code
---

## 🛠 Prerequisites

- Python 3.9+
- PostgreSQL 13+
- Dependencies installed via: `pip install -r requirements.txt`

---

## 🚀 Current Working Workflow (PostgreSQL + MCP)

### 1. Setup Database
```bash
# Setup PostgreSQL database
python database.py --create-schema
python database.py --test-connection
```

### 2. Import CSV Files
```bash
# Import CSV transaction files directly to PostgreSQL
python csv_to_postgres.py --input /path/to/csv/files

# Options:
# --since YYYY-MM-DD    Skip older transactions
# --recursive           Scan subfolders for CSVs
# --dry-run            Test without inserting data
```

This script:
- Normalizes different CSV formats into unified columns
- Computes content hashes for deduplication
- Applies strong deduplication rules automatically
- Stores transactions in PostgreSQL with full audit trail

### 3. AI Categorization
```bash
# Automatically categorize uncategorized transactions
python bookkeeping_helper_postgres.py

# Options:
# --batch 150          Adjust rows per API call
# --model gpt-4.1-mini Set AI model to use
# --dry-run           Test without updating database
```

This script:
- Identifies uncategorized transactions
- Applies vendor mapping rules automatically
- Uses OpenAI API for intelligent categorization
- Updates database with categories and cleaned vendor names

### 4. AI Chat Interface
```bash
# Start the MCP server for AI chat
python mcp/start_server.py
```

Connect your AI client to query your data naturally:
- *"How much did I spend on groceries last month?"*
- *"Show me my top 5 expense categories this year"*
- *"Find any duplicate transactions"*
- *"Add a $50 grocery transaction from Whole Foods"*

### 5. Database Management
Use the MCP server tools or direct SQL queries:
- Query transactions with flexible filters
- Analyze spending patterns and trends
- Manage categories and vendor mappings
- Generate monthly and yearly summaries

### 6. Duplicate Review & Management
Instead of Excel sheets, use MCP tools for duplicate review:

```bash
# Find and stage potential duplicates for review
# This replaces the Excel "Dup Review" sheet
AI: "Stage duplicates for review from the last 30 days"

# Review the duplicate queue
AI: "Show me the duplicate review queue"

# Make decisions on duplicates
AI: "Review duplicate group DUP_0001, delete the duplicate and keep transaction 123"
AI: "Review duplicate group DUP_0002, keep both transactions as they're not duplicates"
```

### 7. Vendor Mapping & Categorization Review
Manage uncategorized transactions and vendor mappings:

```bash
# Find uncategorized transactions that need attention
AI: "Show me uncategorized transactions"

# Get suggestions for vendor mappings
AI: "Give me vendor mapping suggestions"

# Create vendor mapping rules
AI: "Create a vendor mapping for Starbucks to map to Dining category"
```

---

## 📊 Database Schema Overview

- **transactions** → All transaction data with deduplication support
- **duplicate_review** → Staging area for manual duplicate review decisions
- **categories** → Spending categories with descriptions  
- **vendor_mappings** → Automatic categorization rules
- **processing_log** → Complete audit trail of all operations

All data operations maintain full audit trails and transaction integrity.

---

## 🎯 Getting Started

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Setup PostgreSQL**: Configure database connection in `.env`  
3. **Initialize database**: `python database.py --create-schema`
4. **Import CSV data**: `python csv_to_postgres.py --input /path/to/csv/files`
5. **Start MCP server**: `python mcp/start_server.py`
6. **Connect AI client**: Use Claude Desktop or other MCP-compatible client

---  

---

## 🔒 Security & Privacy

- Only `Date, Description, Amount` are sent to OpenAI API.  
- No account numbers, balances, or references are transmitted.  
- All data stays local in Excel; audit trail is preserved.  
- API keys are kept in your environment, not in code.

---

## 🧩 Suggested Workflow Example

```bash
# Monthly bookkeeping run
python csv_to_raw.py --xlsx "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx" --input "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\Data" --since 2025-01-01
python bookkeeping_helper.py --file "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx"
python build_dup_review.py --file "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx"
# → Open Excel, mark Delete decisions in Dup Review
python cleanup_dupes.py --file "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx"
```

---

## 📝 Roadmap / Possible Enhancements

- Script to **restore** rows from Deleted Rows back into Raw Data  
- Scheduled automation (cron / Task Scheduler)  
- Dashboard in Excel or Power BI for visualization  
- Support for PDF → CSV extraction with AI/Tabula  

---

## 💡 Tips

- **Maintain VendorMap** for recurring merchants to cut API calls.  
- Always run with `--dry-run` the first time you test a new set of CSVs.  
- Keep a copy of the workbook before large imports.  
- Use `GroupCount >= 2` filter in **Dup Review** to focus on likely duplicates.

---

## 🎯 Immediate Next Steps in Devcontainer

1. **Setup PostgreSQL** in devcontainer
2. **Create database schema** from design above
3. **Build data migration script** (Excel → PostgreSQL)
---

## 💡 Development Tips

- **Test with small data sets** when trying new features
- **Use database transactions** to ensure data integrity
- **Implement comprehensive logging** for debugging
- **Regular backups** of PostgreSQL database
- **Monitor MCP server logs** for AI chat interactions

---

## 🔒 Security & Privacy Notes

- All data processing remains local
- Only anonymized transaction data sent to OpenAI for categorization
- PostgreSQL credentials stored securely in environment variables
- MCP server runs locally, no external data transmission
- Full audit trail maintained for all operations

---

## 📝 References

- [Model Context Protocol Documentation](https://spec.modelcontextprotocol.io/)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [PostgreSQL Financial Data Best Practices](https://www.postgresql.org/)
- Development history in `DEVELOPMENT_LOG.md`
- Migration details in `MIGRATION_COMPLETE.md`
