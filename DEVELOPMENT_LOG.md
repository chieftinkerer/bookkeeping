# Development Log

## Current Status (Sept 20, 2025)

### ✅ Working Scripts
- `csv_to_raw.py` - Fixed column shift detection for Chase CSV format, imports 387 transactions successfully
- `bookkeeping_helper.py` - Fixed OpenAI API integration, batch processing, timeout handling
- Both scripts use file path: `C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx`

### 🔧 Key Fixes Applied
1. **CSV Import Issues Fixed:**
   - Column shift detection for Chase CSV format
   - Deduplication logic corrected (was removing all data)
   - Amount parsing working correctly

2. **AI Categorization Issues Fixed:**
   - OpenAI API endpoint corrected (was using wrong URL)
   - Batch size reduced to 50 for timeout prevention
   - Retry logic added for API timeouts
   - Model name corrected to "gpt-4o-mini"

### 🎯 Next Planned Features
- [ ] PostgreSQL migration (to solve Excel file locking)
- [ ] MCP server for AI chat interface
- [ ] Streamlit dashboard for interactive charts
- [ ] Hybrid approach: PostgreSQL + Excel exports

### 💡 Architecture Vision
```
CSV Files → PostgreSQL ← MCP Server ← Claude/AI Chat
                ↓
        Streamlit Dashboard (charts)
                +
        Excel Export (reports)
```

### 🐛 Known Issues
- Excel file locking prevents concurrent access
- FutureWarning from pandas (fixed but may reappear)

### 🔄 Commands That Work
```bash
# Import CSV data
python csv_to_raw.py --xlsx "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx" --input "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\Data"

# Categorize with AI (requires OPENAI_API_KEY)
python bookkeeping_helper.py --file "C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx"
```