# Configuration for data paths
import os
from pathlib import Path

# Default paths for different environments
DEFAULT_PATHS = {
    "windows_host": {
        "csv_input": r"C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\Data",
        "excel_file": r"C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\AI_Bookkeeping.xlsx"
    },
    "devcontainer": {
        "csv_input": "/workspace/data/Data", 
        "excel_file": "/workspace/data/AI_Bookkeeping.xlsx"
    },
    "development": {
        "csv_input": "./data/csv_files",
        "excel_file": "./data/test_bookkeeping.xlsx"
    }
}

def get_data_paths():
    """Get appropriate data paths based on environment."""
    # Check environment
    if os.path.exists("/workspace/data"):
        env = "devcontainer"
    elif os.path.exists(r"C:\Users\james\Digital Storage"):
        env = "windows_host"
    else:
        env = "development"
    
    paths = DEFAULT_PATHS[env].copy()
    
    # Allow environment variable overrides
    if csv_override := os.getenv("BOOKKEEPING_CSV_PATH"):
        paths["csv_input"] = csv_override
    if excel_override := os.getenv("BOOKKEEPING_EXCEL_PATH"):
        paths["excel_file"] = excel_override
        
    return paths

# Example usage in your scripts:
if __name__ == "__main__":
    paths = get_data_paths()
    print(f"Using CSV input: {paths['csv_input']}")
    print(f"Using Excel file: {paths['excel_file']}")