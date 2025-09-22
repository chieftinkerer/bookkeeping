#!/usr/bin/env python3
"""
csv_to_postgres.py  (PostgreSQL version of csv_to_raw.py)

This ingests a folder of manually downloaded bank/credit-card CSVs, normalizes
them to a common schema, and imports them directly to PostgreSQL transactions table
with the same robust deduplication logic as the original Excel version.

⚡ Dedupe rules (highest priority first):
  1) If a stable transaction id exists (e.g., Transaction ID / FITID) and Account is known,
     drop true duplicates with the same (TxnId, Account).
  2) Else if (Reference, Date, Amount[, Time]) all match, drop duplicates.
  3) Else if the entire normalized-row hash matches, drop the duplicate.
  4) We DO NOT drop based only on (Date, Description, Amount). Instead, we keep
     the row and tag a "PossibleDupGroup" so you can review same-day/same-amount/same-merchant cases.

Usage:
  pip install pandas psycopg2-binary python-dateutil
  python csv_to_postgres.py --input ./downloads [--dry-run] [--since YYYY-MM-DD]

Options:
  --recursive
  --since YYYY-MM-DD
  --dry-run
  --assume-encoding latin1
  --source-from filename
  --clear-transactions (⚠️ DANGEROUS - clears all transactions!)

Transaction columns created/maintained:
  date, description, amount, source, txn_id, reference, time_part, account, balance, 
  original_hash, possible_dup_group, row_hash, category, vendor
"""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import pandas as pd
from dateutil.parser import parse as dtparse
from dotenv import load_dotenv

# Import our database utilities
from database import DatabaseManager, TransactionOperations, ProcessingLogOperations
from config import get_data_paths

# Load environment variables
load_dotenv()

# Column detection constants (same as original)
DATE_CANDIDATES = [
    "Date","Transaction Date","Trans Date","Posted Date","Post Date","TransactionDate","Posting Date"
]
DESC_CANDIDATES = [
    "Description","Payee","Memo","Name","Details","Transaction Description","Merchant","Vendor","Narrative"
]
AMOUNT_SINGLE = ["Amount","Amount ($)","Transaction Amount","Purchase Amount","Amt"]
DEBIT_COLS = ["Debit","Withdrawal","Withdrawals","Outflow","Charges"]
CREDIT_COLS = ["Credit","Deposit","Deposits","Inflow","Income"]
TYPE_COLS = ["Type","Transaction Type","Category","Debit/Credit"]
TXNID_CANDIDATES = ["Transaction ID","FITID","ID","TxnId","Confirmation Number"]
REF_CANDIDATES = ["Reference","Ref","Check Number","Check #","Reference Number"]
TIME_CANDIDATES = ["Time","Transaction Time","Posted Time"]
ACCOUNT_CANDIDATES = ["Account","Account Number","Acct","Account #"]
BALANCE_CANDIDATES = ["Balance","Running Balance","Current Balance","Bal"]

def pick_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Pick the first matching column from candidates."""
    for col in candidates:
        if col in df.columns:
            return col
    return None

def clean_amount(s: pd.Series) -> pd.Series:
    """Clean and convert amount column to numeric."""
    cleaned = s.astype(str).str.replace(r'[,$\s]', '', regex=True).str.replace(r'[()]', '-', regex=True)
    return pd.to_numeric(cleaned, errors="coerce")

def parse_amount_series(df: pd.DataFrame) -> Optional[pd.Series]:
    """Parse amount from various column formats (same logic as original)."""
    # Case A: Single amount column
    for amtcol in AMOUNT_SINGLE:
        if amtcol in df.columns:
            print(f"    Found amount column: {amtcol}")
            return clean_amount(df[amtcol])
    
    # Case B: Separate debit/credit columns
    debit = None
    credit = None
    for dc in DEBIT_COLS:
        if dc in df.columns: 
            debit = clean_amount(df[dc])
            print(f"    Found debit column: {dc}")
            break
    for cc in CREDIT_COLS:
        if cc in df.columns: 
            credit = clean_amount(df[cc])
            print(f"    Found credit column: {cc}")
            break
    if debit is not None or credit is not None:
        d = debit if debit is not None else pd.Series([0.0]*len(df))
        c = credit if credit is not None else pd.Series([0.0]*len(df))
        return (c.fillna(0) - d.fillna(0))
    
    # Case C: type-based sign (for Chase format)
    for tcol in TYPE_COLS:
        if tcol in df.columns:
            print(f"    Found type column: {tcol}")
            print(f"    Type values sample: {df[tcol].head(5).tolist()}")
            for c in df.columns:
                if c == tcol: continue
                if "amount" in c.lower() or "value" in c.lower():
                    print(f"    Using amount column: {c} with type column: {tcol}")
                    s = clean_amount(df[c])
                    print(f"    Amount values sample: {s.head(3).tolist()}")
                    sign = df[tcol].astype(str).str.lower().map(lambda x: -1.0 if ("debit" in x or x in ["dr","withdrawal","charge"]) else 1.0)
                    print(f"    Sign values sample: {sign.head(3).tolist()}")
                    result = s * sign
                    print(f"    Final signed amounts: {result.head(3).tolist()}")
                    return result
    
    print(f"    No amount parsing method worked!")
    return None

def parse_date_col(s: pd.Series) -> pd.Series:
    """Parse date column with fallback to dateutil."""
    dt = pd.to_datetime(s, errors="coerce")
    mask = dt.isna()
    
    if mask.any():
        print(f"    Trying dateutil parsing for {mask.sum()} failed dates")
        dt.loc[mask] = s[mask].astype(str).map(lambda x: _try_parse_date(x))
    
    result = dt.dt.date.astype(str)
    result = result.replace('NaT', '')
    return result

def _try_parse_date(x: str):
    """Try to parse date string with dateutil."""
    x = x.strip()
    if not x: return pd.NaT
    try:
        return dtparse(x, dayfirst=False, yearfirst=False)
    except Exception:
        return pd.NaT

def normalize_account(val: str) -> str:
    """Normalize account number to last 4 digits."""
    if val is None: return ""
    s = str(val).strip()
    last4 = "".join([ch for ch in s if ch.isdigit()])[-4:]
    return last4 if last4 else s[:12]

def row_content_hash(row: dict) -> str:
    """Generate content hash for deduplication (same as original)."""
    date_val = row.get("Date", "")
    if pd.isna(date_val) or date_val == "NaT":
        date_val = ""
    
    amount_val = row.get("Amount", 0.0)
    if pd.isna(amount_val):
        amount_val = 0.0
    
    balance_val = row.get("Balance", "")
    if pd.isna(balance_val) or balance_val == "":
        balance_val = ""
    else:
        balance_val = float(balance_val)
    
    payload = {
        "date": str(date_val),
        "desc": str(row.get("Description", "")),
        "amount": float(amount_val),
        "txn": str(row.get("TxnId", "")),
        "ref": str(row.get("Reference", "")),
        "time": str(row.get("Time", "")),
        "acct": str(row.get("Account", "")),
        "bal": balance_val
    }
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

def possible_dup_group(row: dict) -> str:
    """Generate possible duplicate group ID."""
    date_val = row.get('Date', '')
    if pd.isna(date_val) or date_val == "NaT":
        date_val = ''
    
    amount_val = row.get('Amount', 0.0)
    if pd.isna(amount_val):
        amount_val = 0.0
    
    key = f"{date_val}|{str(row.get('Description', '')).strip()}|{float(amount_val):.2f}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]

def stable_rowhash(date, description, amount):
    """Generate a stable hash for a transaction row (for PostgreSQL row_hash)."""
    s = f"{date}|{description}|{amount}"
    return hashlib.md5(s.encode()).hexdigest()

def load_csv(path: Path, encoding_hint: Optional[str]) -> pd.DataFrame:
    """Load CSV with encoding detection and column shift correction."""
    try:
        df = pd.read_csv(path, dtype=str, encoding=encoding_hint or "utf-8", engine="python")
        print(f"      Successfully loaded with UTF-8")
    except Exception:
        df = pd.read_csv(path, dtype=str, encoding=encoding_hint or "latin1", engine="python")
        print(f"      Fell back to latin1 encoding")
    
    # Clean column names
    df.columns = [c.strip() for c in df.columns]
    
    print(f"      Raw column names: {list(df.columns)}")
    print(f"      DataFrame shape: {df.shape}")
    
    # Check for Chase CSV column shift issue
    if len(df) > 0:
        first_row = df.iloc[0]
        print(f"      First row values: {first_row.tolist()}")
        
        first_col_val = str(first_row.iloc[0])
        if '/' in first_col_val and len(first_col_val.split('/')) == 3:
            print(f"      DETECTED: Data appears shifted - first column contains date: {first_col_val}")
            
            if len(df.columns) >= 7:
                print(f"      Remapping columns to correct Chase CSV format")
                df.columns = ['Posting Date', 'Description', 'Amount', 'Type', 'Balance', 'Check or Slip #', 'Extra'][:len(df.columns)]
                if 'Type' in df.columns:
                    type_to_details = {
                        'ACH_CREDIT': 'CREDIT',
                        'ACH_DEBIT': 'DEBIT', 
                        'QUICKPAY_DEBIT': 'DEBIT',
                        'QUICKPAY_CREDIT': 'CREDIT',
                        'DEBIT_CARD': 'DEBIT',
                        'CHECK_PAID': 'CHECK',
                        'CHECK_DEPOSIT': 'DSLIP',
                        'ATM': 'DEBIT',
                        'MISC_CREDIT': 'CREDIT',
                        'MISC_DEBIT': 'DEBIT'
                    }
                    df.insert(0, 'Details', df['Type'].map(type_to_details).fillna('DEBIT'))
                print(f"      Corrected column names: {list(df.columns)}")
    
    return df

def normalize_csv(path: Path, encoding_hint: Optional[str], source_mode: Optional[str]) -> pd.DataFrame:
    """Normalize CSV to standard format (same logic as original)."""
    df = load_csv(path, encoding_hint)
    df.columns = [c.strip() for c in df.columns]
    
    print(f"  CSV columns: {list(df.columns)}")
    print(f"  CSV shape: {df.shape}")

    date_col = pick_column(df, DATE_CANDIDATES)
    desc_col = pick_column(df, DESC_CANDIDATES)
    amt_series = parse_amount_series(df)
    
    print(f"  Detected date column: {date_col}")
    print(f"  Detected description column: {desc_col}")
    print(f"  Amount series detected: {amt_series is not None}")
    
    if date_col is None:
        raise ValueError(f"{path.name}: Could not detect a Date column. Columns: {list(df.columns)}")
    if desc_col is None:
        desc_col = df.columns[0]
        print(f"  Using first column as description: {desc_col}")
    if amt_series is None:
        raise ValueError(f"{path.name}: Could not detect an Amount column.")

    # Optional metadata columns
    txnid_col = pick_column(df, TXNID_CANDIDATES)
    ref_col = pick_column(df, REF_CANDIDATES)
    time_col = pick_column(df, TIME_CANDIDATES)
    acct_col = pick_column(df, ACCOUNT_CANDIDATES)
    bal_col = pick_column(df, BALANCE_CANDIDATES)

    out = pd.DataFrame({
        "Date": parse_date_col(df[date_col]),
        "Description": df[desc_col].astype(str).fillna("").str.strip(),
        "Amount": pd.to_numeric(amt_series, errors="coerce")
    })
    
    print(f"  Before validation - rows: {len(out)}")
    print(f"  Date column sample: {out['Date'].head(3).tolist()}")
    print(f"  Amount column sample: {out['Amount'].head(3).tolist()}")

    # Remove rows with invalid dates or amounts
    valid_mask = ~(out["Date"].isna() | out["Amount"].isna())
    print(f"  Valid dates: {(~out['Date'].isna()).sum()}")
    print(f"  Valid amounts: {(~out['Amount'].isna()).sum()}")
    print(f"  Valid rows after filtering: {valid_mask.sum()}")
    
    out = out[valid_mask].copy()

    if source_mode == "filename":
        out["Source"] = path.stem
    elif source_mode and source_mode in df.columns:
        out["Source"] = df[source_mode].astype(str)
    else:
        out["Source"] = ""

    out["TxnId"] = df[txnid_col].astype(str).str.strip() if txnid_col else ""
    out["Reference"] = df[ref_col].astype(str).str.strip() if ref_col else ""
    out["Time"] = df[time_col].astype(str).str.strip() if time_col else ""
    out["Account"] = df[acct_col].astype(str).apply(normalize_account) if acct_col else ""
    out["Balance"] = pd.to_numeric(df[bal_col], errors="coerce") if bal_col else ""

    # Add metadata columns
    out["OriginalHash"] = [row_content_hash(row) for _, row in out.iterrows()]
    out["PossibleDupGroup"] = [possible_dup_group(row) for _, row in out.iterrows()]

    return out

def deduplicate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicates using the same priority rules as original."""
    if df.empty:
        return df
    
    print(f"  Starting deduplication with {len(df)} rows")
    original_count = len(df)
    
    # Rule 1: TxnId + Account (strongest dedupe)
    mask1 = (df["TxnId"] != "") & (df["Account"] != "")
    if mask1.any():
        before_count = len(df)
        has_txnid_account = df[mask1]
        no_txnid_account = df[~mask1]
        
        deduped_with_txnid = has_txnid_account.drop_duplicates(subset=["TxnId", "Account"], keep="first")
        df = pd.concat([deduped_with_txnid, no_txnid_account], ignore_index=True)
        print(f"  Rule 1 (TxnId + Account): {before_count} -> {len(df)} rows ({before_count - len(df)} removed)")
    else:
        print(f"  Rule 1 (TxnId + Account): Skipped - no rows have both TxnId and Account")
    
    # Rule 2: Reference + Date + Amount + Time
    mask2 = df["Reference"] != ""
    if mask2.any():
        before_count = len(df)
        has_reference = df[mask2]
        no_reference = df[~mask2]
        
        deduped_with_ref = has_reference.drop_duplicates(subset=["Reference", "Date", "Amount", "Time"], keep="first")
        df = pd.concat([deduped_with_ref, no_reference], ignore_index=True)
        print(f"  Rule 2 (Reference + Date + Amount + Time): {before_count} -> {len(df)} rows ({before_count - len(df)} removed)")
    else:
        print(f"  Rule 2 (Reference): Skipped - no rows have Reference values")
    
    # Rule 3: Content hash (entire row)
    before_count = len(df)
    hash_counts = df["OriginalHash"].value_counts()
    duplicate_hashes = hash_counts[hash_counts > 1]
    if len(duplicate_hashes) > 0:
        print(f"  Found {len(duplicate_hashes)} hash values with duplicates:")
        for hash_val, count in duplicate_hashes.head(5).items():
            print(f"    Hash {hash_val}: {count} occurrences")
    
    df = df.drop_duplicates(subset=["OriginalHash"], keep="first")
    print(f"  Rule 3 (Content hash): {before_count} -> {len(df)} rows ({before_count - len(df)} removed)")
    
    print(f"  Final deduplication: {original_count} -> {len(df)} rows ({original_count - len(df)} total removed)")
    return df

def prepare_transactions_for_db(df: pd.DataFrame) -> List[dict]:
    """Convert DataFrame to list of transaction dictionaries for database insertion."""
    transactions = []
    
    for _, row in df.iterrows():
        # Convert date string back to date object
        date_val = pd.to_datetime(row['Date']).date()
        
        # Generate the PostgreSQL row_hash (using same logic as existing scripts)
        row_hash = stable_rowhash(date_val, row['Description'], row['Amount'])
        
        transaction_data = {
            'date': date_val,
            'description': str(row['Description']),
            'amount': float(row['Amount']),
            'category': None,  # Will be filled by AI categorization later
            'vendor': None,    # Will be filled by AI categorization later
            'source': str(row['Source']) if row['Source'] else None,
            'txn_id': str(row['TxnId']) if row['TxnId'] else None,
            'reference': str(row['Reference']) if row['Reference'] else None,
            'account': str(row['Account']) if row['Account'] else None,
            'balance': float(row['Balance']) if pd.notna(row['Balance']) else None,
            'original_hash': str(row['OriginalHash']),
            'possible_dup_group': str(row['PossibleDupGroup']) if row['PossibleDupGroup'] else None,
            'row_hash': row_hash,
            'time_part': str(row['Time']) if row['Time'] else None
        }
        
        transactions.append(transaction_data)
    
    return transactions

def main():
    """Main function for CSV to PostgreSQL import."""
    parser = argparse.ArgumentParser(description="Import CSV files to PostgreSQL transactions table")
    parser.add_argument("--input", help="Input directory with CSV files (defaults to config)")
    parser.add_argument("--recursive", action="store_true", help="Search subdirectories")
    parser.add_argument("--since", help="Only import rows after this date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--assume-encoding", help="Encoding hint for CSV files")
    parser.add_argument("--source-from", help="Source column name or 'filename'")
    parser.add_argument("--clear-transactions", action="store_true", 
                       help="⚠️ DANGEROUS: Clear all existing transactions first")
    
    args = parser.parse_args()
    
    print(f"🚀 Starting CSV to PostgreSQL import...")
    
    # Get input directory
    input_dir = args.input
    if not input_dir:
        paths = get_data_paths()
        input_dir = paths.get('csv_input')
        if not input_dir:
            print("❌ No input directory specified and none found in config")
            print("Usage: python csv_to_postgres.py --input ./csv_files")
            return 1
    
    input_path = Path(input_dir)
    if not input_path.exists():
        print(f"❌ Input directory not found: {input_path}")
        return 1
    
    print(f"📁 Input directory: {input_path}")
    
    # Test database connection
    try:
        db = DatabaseManager()
        tx_ops = TransactionOperations(db)
        log_ops = ProcessingLogOperations(db)
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("💡 Make sure PostgreSQL is running and check your environment variables")
        return 1
    
    # Check if transactions table exists
    if not db.table_exists('transactions'):
        print("❌ Transactions table not found")
        print("💡 Run: python -m database --migrate")
        return 1
    
    # Clear transactions if requested
    if args.clear_transactions:
        print("⚠️  CLEARING ALL EXISTING TRANSACTIONS...")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            db.execute_update("DELETE FROM transactions;")
            print("✅ All transactions cleared")
        else:
            print("❌ Operation cancelled")
            return 1
    
    # Find CSV files
    pattern = "**/*.csv" if args.recursive else "*.csv"
    csv_files = list(input_path.glob(pattern))
    
    if not csv_files:
        print(f"❌ No CSV files found in {input_path}")
        return 1
    
    print(f"📊 Found {len(csv_files)} CSV files")
    
    if args.dry_run:
        print("🔍 DRY RUN - would process these files:")
        for f in csv_files:
            print(f"  📄 {f}")
        return 0
    
    # Start processing log
    log_id = log_ops.start_operation(
        operation_type='csv_import_postgres',
        source_file=str(input_path),
        details={'files': [str(f) for f in csv_files]}
    )
    
    # Process CSV files
    all_data = []
    processed_files = 0
    error_files = 0
    
    for csv_file in csv_files:
        try:
            print(f"📄 Processing {csv_file.name}...")
            df = normalize_csv(csv_file, args.assume_encoding, args.source_from)
            
            # Apply date filter if specified
            if args.since:
                since_date = pd.to_datetime(args.since).date()
                df = df[pd.to_datetime(df["Date"]).dt.date >= since_date]
                print(f"  📅 Filtered to {len(df)} rows since {args.since}")
            
            all_data.append(df)
            processed_files += 1
            print(f"  ✅ Added {len(df)} rows")
            
        except Exception as e:
            print(f"  ❌ Error processing {csv_file.name}: {e}")
            error_files += 1
    
    if not all_data:
        print("❌ No data to import")
        log_ops.complete_operation(log_id, status='failed', 
                                  details={'error': 'No data processed'})
        return 1
    
    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)
    print(f"📊 Combined: {len(combined_df)} total rows")
    
    # Deduplicate within the new data
    deduped_df = deduplicate_dataframe(combined_df)
    print(f"🔄 After deduplication: {len(deduped_df)} rows")
    
    # Prepare transactions for database
    transactions = prepare_transactions_for_db(deduped_df)
    print(f"💾 Prepared {len(transactions)} transactions for database")
    
    # Check for existing transactions (by row_hash)
    row_hashes = [t['row_hash'] for t in transactions]
    existing_hashes = tx_ops.get_existing_row_hashes(row_hashes)
    print(f"📋 Found {len(existing_hashes)} existing transactions")
    
    # Filter out existing transactions
    new_transactions = [t for t in transactions if t['row_hash'] not in existing_hashes]
    skipped_count = len(transactions) - len(new_transactions)
    
    print(f"➕ New transactions to insert: {len(new_transactions)}")
    print(f"⏭️  Skipped (already exist): {skipped_count}")
    
    # Insert new transactions
    inserted_count = 0
    if new_transactions:
        try:
            inserted_count = tx_ops.insert_transactions_batch(new_transactions)
            print(f"✅ Successfully inserted {len(new_transactions)} transactions")
        except Exception as e:
            print(f"❌ Error inserting transactions: {e}")
            log_ops.complete_operation(log_id, 
                                     records_processed=len(transactions),
                                     records_skipped=skipped_count,
                                     error_count=error_files,
                                     status='failed',
                                     details={'error': str(e)})
            return 1
    
    # Complete processing log
    log_ops.complete_operation(log_id,
                             records_processed=len(transactions),
                             records_inserted=len(new_transactions),
                             records_skipped=skipped_count,
                             error_count=error_files,
                             status='completed')
    
    print(f"\n🎉 Import completed successfully!")
    print(f"📁 Files processed: {processed_files}")
    print(f"❌ Files with errors: {error_files}")
    print(f"📊 Total records processed: {len(transactions)}")
    print(f"➕ New records inserted: {len(new_transactions)}")
    print(f"⏭️  Records skipped (duplicates): {skipped_count}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())