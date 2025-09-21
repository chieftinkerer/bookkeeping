# AI-Assisted Personal Bookkeeping

This repo contains a **local, privacy-friendly bookkeeping workflow** that combines:

- **Manual CSV exports** from your bank/credit card accounts  
- **Python scripts** to normalize, deduplicate, and import into Excel  
- **OpenAI API** to automatically categorize expenses  
- **Excel pivot tables & review sheets** for summaries and duplicate management  

You keep **all data local** — only anonymized rows (Date, Description, Amount) are sent to the AI for categorization.

---

## 🎯 NEXT PHASE: PostgreSQL + MCP Server Migration Plan

### Current Pain Points (Sept 20, 2025)
- ❌ **Excel file locking** - can't access data while scripts run
- ❌ **No AI chat interface** - want to query data naturally  
- ❌ **Manual workflow** - want real-time interaction with financial data

### 🏗️ Planned Architecture
```
CSV Files → PostgreSQL ← MCP Server ← Claude/AI Chat
                ↓
        Streamlit Dashboard (interactive charts)
                +
        Excel Export (on-demand reports)
```

### 📋 Implementation Roadmap

#### Phase 1: Database Migration
- [ ] **PostgreSQL Setup**
  - Create database schema for transactions
  - Tables: `transactions`, `categories`, `vendor_mappings`, `processing_log`
- [ ] **Data Migration**
  - Migrate existing Excel data to PostgreSQL
  - Preserve all 388+ transactions from Chase CSV
- [ ] **Script Updates**
  - Modify `csv_to_raw.py` to write to PostgreSQL instead of Excel
  - Update `bookkeeping_helper.py` for database operations

#### Phase 2: MCP Server
- [ ] **MCP Server Creation**
  - Tool: `query_transactions` - natural language queries
  - Tool: `categorize_spending` - spending analysis
  - Tool: `monthly_summary` - automated reporting  
  - Tool: `find_duplicates` - duplicate detection
  - Tool: `add_transaction` - manual entry
  - Tool: `generate_chart` - create visualizations
- [ ] **AI Chat Interface**
  - Enable queries like: *"How much did I spend on groceries in August?"*
  - Support commands: *"Show me a chart of dining vs grocery spending"*
  - Generate insights: *"What are my top 5 expense categories?"*

#### Phase 3: Visualization & Reporting
- [ ] **Streamlit Dashboard**
  - Interactive charts and graphs
  - Filtering by date, category, amount
  - Trend analysis and comparisons
- [ ] **Excel Export**
  - On-demand Excel reports with charts
  - Preserve familiar reporting format
  - Automated monthly/quarterly exports

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

### 🔄 Migration Strategy

#### Step 1: Parallel Systems
1. Keep existing Excel workflow working
2. Build PostgreSQL system alongside
3. Validate data consistency between both

#### Step 2: Gradual Migration  
1. New CSV imports go to PostgreSQL
2. Historical data migrated in batches
3. Excel becomes export-only

#### Step 3: Full Migration
1. MCP server operational
2. Streamlit dashboard deployed
3. Excel workflow deprecated

### 📊 Expected Benefits

#### Solved Problems
- ✅ **No file locking** - concurrent access to data
- ✅ **Real-time queries** - chat with your financial data
- ✅ **Better performance** - handles 10k+ transactions easily
- ✅ **Advanced analytics** - complex SQL queries
- ✅ **Automated processing** - background CSV imports

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
│   └── devcontainer.json           # VS Code devcontainer configuration with volume mounts
├── bookkeeping_helper.py           # Call OpenAI API to categorize transactions & build summary
├── build_dup_review.py             # Generate a Dup Review sheet for spotting potential duplicates
├── cleanup_dupes.py                # Move rows marked Delete → Deleted Rows, remove from Raw Data
├── config.py                       # Environment-aware path configuration for CSV/Excel files
├── csv_to_raw.py                   # Import & normalize manually downloaded CSVs
├── DEVELOPMENT_LOG.md              # Technical fixes and current status
├── README.md                       # This file
├── s3_backup_sync.sh               # S3 backup script
├── S3_README.md                    # S3 configuration documentation
├── s3_restore_sync.sh              # S3 restore script
└── s3_secure_setup.py              # S3 secure bucket setup
```

**Current Data Location (Windows Host):**
- Excel workbook: `C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx`
- CSV files: `C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\Data`

**Data Location in Devcontainer:**
- Excel workbook: `/workspace/data/AI_Bookkeeping.xlsx`
- CSV files: `/workspace/data/Data`
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
2. When prompted, click "Reopen in Container"
3. Your CSV files will be automatically mounted at `/workspace/data/Data`
4. Scripts will automatically detect the container environment

### Container Commands
```bash
# Test data access
python -c "from config import get_data_paths; print(get_data_paths())"

# Import CSVs (uses mounted data)
python csv_to_raw.py --input /workspace/data/Data --excel /workspace/data/AI_Bookkeeping.xlsx

# Categorize with AI
python bookkeeping_helper.py --file /workspace/data/AI_Bookkeeping.xlsx
```

---

## 🛠 Prerequisites for Migration

- Python 3.9+
- PostgreSQL 13+
- Dependencies: `pandas`, `psycopg2`, `streamlit`, `plotly`, `mcp`

```bash
pip install pandas psycopg2-binary streamlit plotly requests python-dateutil openpyxl
```

---

## 🚀 Current Working Workflow (Pre-Migration)

### 1. Export CSVs from your accounts
- Log into each bank/credit card portal (about 10 accounts, or as many as you have).
- Download CSV statements (monthly or quarterly).
- Save them into `C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\Data`.

### 2. Load CSVs into Excel

```bash
python csv_to_raw.py --xlsx "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx" --input "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\Data"
```

This script:
- Normalizes different CSV formats → unified columns:
  `Date, Description, Amount, Source, TxnId, Reference, Time, Account, Balance`
- Computes a **content hash** per row (`OriginalHash`)
- Tags rows with **PossibleDupGroup** if they share Date + Description + Amount
- Appends rows into the **Raw Data** sheet of your workbook
- Applies **strong dedupe** rules (TxnId > Reference+Date+Amount > Hash)

Options:
- `--since YYYY-MM-DD` → skip older rows  
- `--clear-raw` → start Raw Data fresh  
- `--recursive` → scan subfolders for CSVs  

---

### 3. Categorize with AI

```bash
python bookkeeping_helper.py --file "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx"
```

This script:
- Looks at **Raw Data**
- Skips rows already categorized (using `RowHash`)
- Applies any **VendorMap** rules you maintain in the workbook
- Sends uncategorized rows to the **OpenAI Responses API**
- Writes results to **Clean Data** with:
  - Vendor (cleaned name)
  - Suggested Category
  - Notes
- Builds a **Summary** pivot: monthly totals by category

Options:
- `--batch 150` → adjust rows per API call  
- `--model gpt-4.1-mini` (default) or upgrade to `gpt-4.1`  
- `--dry-run` → test without calling API  

---

### 4. Review possible duplicates

```bash
python build_dup_review.py --file "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx"
```

This script:
- Scans **Raw Data**
- Groups rows by **PossibleDupGroup**
- Creates/updates a **Dup Review** sheet:
  - `Decision` (blank — fill in `Keep`, `Delete`, or `Investigate`)
  - `Reason` (notes for why you chose that action)
  - GroupCount (≥2 = potential duplicates)
- Sorts so groups with multiples float to the top

---

### 5. Clean up duplicates

In Excel → set `Decision = Delete` for true dupes.

Then run:

```bash
python cleanup_dupes.py --file "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx"
```

This script:
- Finds rows marked `Delete` in **Dup Review**
- Moves them to a new **Deleted Rows** sheet (audit trail)
  - Adds `DeletedAt` timestamp
  - Adds `SourceSheet` = "Raw Data"
- Rewrites Raw Data without those rows

You keep a full audit trail — nothing is lost permanently.

---

## 📊 Excel Sheets Overview

- **Raw Data** → unified imports, deduped, with all metadata  
- **Clean Data** → AI-categorized transactions  
- **Summary** → pivot of monthly spend by category  
- **VendorMap** → manual vendor → category rules (applied before AI)  
- **Dup Review** → potential duplicates, review and mark Decision  
- **Deleted Rows** → audit trail of rows you removed  

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
4. **Create basic MCP server** with core tools
5. **Test MCP integration** with Claude
6. **Build Streamlit dashboard** prototype
7. **Implement Excel export** functionality

---

## 💡 Tips for Development

- **Test with small data sets** before migrating all 388 transactions
- **Keep Excel backup** during transition period  
- **Use transaction-safe imports** to prevent data loss
- **Implement comprehensive logging** for debugging
- **Design for extensibility** - more banks, more features

---

## 🔒 Security & Privacy Notes

- All data processing remains local
- Only anonymized transaction data sent to OpenAI
- PostgreSQL credentials stored in environment variables
- MCP server runs locally, no external data transmission
- Excel exports contain full financial data (handle securely)

---

## 📝 References

- [Model Context Protocol Documentation](https://spec.modelcontextprotocol.io/)
- [Streamlit Financial Dashboard Examples](https://streamlit.io/)
- [PostgreSQL Financial Data Best Practices](https://www.postgresql.org/)
- Original requirements captured in `DEVELOPMENT_LOG.md`
