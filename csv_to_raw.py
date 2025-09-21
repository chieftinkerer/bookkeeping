#!/usr/bin/env python3
"""
csv_to_raw.py  (Upgraded dedupe)

This ingests a folder of manually downloaded bank/credit-card CSVs, normalizes
them to a common schema, appends them to Excel "Raw Data", and deduplicates
safely using strong identifiers.

⚡ Dedupe rules (highest priority first):
  1) If a stable transaction id exists (e.g., Transaction ID / FITID) and Account is known,
     drop true duplicates with the same (TxnId, Account).
  2) Else if (Reference, Date, Amount[, Time]) all match, drop duplicates.
  3) Else if the entire normalized-row hash matches, drop the duplicate.
  4) We DO NOT drop based only on (Date, Description, Amount). Instead, we keep
     the row and tag a "PossibleDupGroup" so you can review same-day/same-amount/same-merchant cases.

Usage:
  pip install pandas openpyxl python-dateutil
  python csv_to_raw.py --xlsx AI_Bookkeeping_Template.xlsx --input ./downloads

Options:
  --recursive
  --since YYYY-MM-DD
  --dry-run
  --assume-encoding latin1
  --source-from filename
  --clear-raw

Raw Data columns created/maintained:
  Date, Description, Amount, Source, TxnId, Reference, Time, Account, Balance, OriginalHash, PossibleDupGroup
"""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import pandas as pd
from dateutil.parser import parse as dtparse

DATE_CANDIDATES = [
    "Date","Transaction Date","Trans Date","Posted Date","Post Date","TransactionDate","Posting Date"
]
DESC_CANDIDATES = [
    "Description","Payee","Memo","Name","Details","Transaction Description","Merchant","Vendor","Narrative"
]
AMOUNT_SINGLE = ["Amount","Amount ($)","Transaction Amount","Purchase Amount","Amt"]
DEBIT_COLS = ["Debit","Withdrawal","Withdrawals","Outflow","Charges"]
CREDIT_COLS = ["Credit","Deposit","Deposits","Inflow","Payments","Payment"]
TYPE_COLS = ["Type","Transaction Type","Dr/Cr","Debit/Credit"]

TXNID_CANDIDATES = ["Transaction ID","TransactionID","FITID","FitId","Unique Id","Unique ID","Id","ID"]
REF_CANDIDATES = ["Reference Number","Ref Number","Reference","Ref","Check Number","Check #","Cheque Number"]
TIME_CANDIDATES = ["Time","Posted Time","Transaction Time","Trans Time","Time Posted"]
ACCOUNT_CANDIDATES = ["Account Number","Account","Account #","Masked Account Number","Card Number","Last 4","Acct #","Acct"]
BALANCE_CANDIDATES = ["Balance","Running Balance","Account Balance"]

def clean_amount(series: pd.Series) -> pd.Series:
    print(f"      Raw amount values: {series.head(5).tolist()}")
    s = series.astype(str).str.strip()
    print(f"      After string conversion: {s.head(5).tolist()}")
    s = s.str.replace(r"[,$]", "", regex=True)
    print(f"      After removing $,: {s.head(5).tolist()}")
    neg = s.str.contains(r"^\(.*\)$")
    print(f"      Negative mask: {neg.head(5).tolist()}")
    s = s.str.replace(r"[\(\)]", "", regex=True)
    print(f"      After removing (): {s.head(5).tolist()}")
    out = pd.to_numeric(s, errors="coerce")
    print(f"      After to_numeric: {out.head(5).tolist()}")
    out[neg] = -out[neg].abs()
    print(f"      Final amounts: {out.head(5).tolist()}")
    return out

def pick_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None

def parse_amount_series(df: pd.DataFrame) -> Optional[pd.Series]:
    print(f"    Looking for amount columns...")
    
    # Case A: single Amount
    for c in AMOUNT_SINGLE:
        if c in df.columns:
            print(f"    Found single amount column: {c}")
            print(f"    Sample values: {df[c].head(3).tolist()}")
            result = clean_amount(df[c])
            print(f"    After cleaning: {result.head(3).tolist()}")
            return result
    
    # Case B: debit/credit pair
    debit = None; credit = None
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
    
    # Case C: type-based sign (this is likely what we need for Chase)
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
    # First try pandas built-in parsing
    dt = pd.to_datetime(s, errors="coerce")
    mask = dt.isna()
    
    # If that fails, try dateutil for the failed ones
    if mask.any():
        print(f"    Trying dateutil parsing for {mask.sum()} failed dates")
        dt.loc[mask] = s[mask].astype(str).map(lambda x: _try_parse_date(x))
    
    # Convert to date strings, handling NA values properly
    result = dt.dt.date.astype(str)
    result = result.replace('NaT', '')  # Replace NaT with empty string
    return result

def _try_parse_date(x: str):
    x = x.strip()
    if not x: return pd.NaT
    try:
        return dtparse(x, dayfirst=False, yearfirst=False)
    except Exception:
        return pd.NaT

def normalize_account(val: str) -> str:
    if val is None: return ""
    s = str(val).strip()
    last4 = "".join([ch for ch in s if ch.isdigit()])[-4:]
    return last4 if last4 else s[:12]

def row_content_hash(row: dict) -> str:
    # Hash stable normalized content, excluding Source so duplicates across files match
    # Handle NA/empty values properly
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
    # Group rows that share Date+Description+Amount to review manually
    date_val = row.get('Date', '')
    if pd.isna(date_val) or date_val == "NaT":
        date_val = ''
    
    amount_val = row.get('Amount', 0.0)
    if pd.isna(amount_val):
        amount_val = 0.0
    
    key = f"{date_val}|{str(row.get('Description', '')).strip()}|{float(amount_val):.2f}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]

def load_csv(path: Path, encoding_hint: Optional[str]) -> pd.DataFrame:
    try:
        # Try reading with explicit header detection
        df = pd.read_csv(path, dtype=str, encoding=encoding_hint or "utf-8", engine="python")
        print(f"      Successfully loaded with UTF-8")
    except Exception:
        df = pd.read_csv(path, dtype=str, encoding=encoding_hint or "latin1", engine="python")
        print(f"      Fell back to latin1 encoding")
    
    # Clean column names to remove any hidden characters
    df.columns = [c.strip() for c in df.columns]
    
    print(f"      Raw column names: {list(df.columns)}")
    print(f"      DataFrame shape: {df.shape}")
    
    # Check if data appears to be shifted (first column contains dates instead of Details)
    if len(df) > 0:
        first_row = df.iloc[0]
        print(f"      First row values: {first_row.tolist()}")
        
        # Check if the first column looks like a date (indicating shift)
        first_col_val = str(first_row.iloc[0])
        if '/' in first_col_val and len(first_col_val.split('/')) == 3:
            print(f"      DETECTED: Data appears shifted - first column contains date: {first_col_val}")
            
            # The CSV appears to have the data shifted. Let's manually fix the column mapping
            if len(df.columns) >= 7:
                print(f"      Remapping columns to correct Chase CSV format")
                # Rename columns to match the actual data positions
                df.columns = ['Posting Date', 'Description', 'Amount', 'Type', 'Balance', 'Check or Slip #', 'Extra'][:len(df.columns)]
                # Add the missing Details column by inferring from Type column
                if 'Type' in df.columns:
                    # Map transaction types back to Details
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
    
    print(f"      Final column names: {list(df.columns)}")
    if len(df) > 0:
        print(f"      Sample of corrected data from first row:")
        for i, col in enumerate(df.columns[:6]):  # Show first 6 columns
            print(f"        Column {i} '{col}': '{df.iloc[0, i]}'")
    
    return df

def normalize_csv(path: Path, encoding_hint: Optional[str], source_mode: Optional[str]) -> pd.DataFrame:
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
    """Remove duplicates using the priority rules described in the docstring."""
    if df.empty:
        return df
    
    print(f"  Starting deduplication with {len(df)} rows")
    original_count = len(df)
    
    # Rule 1: TxnId + Account (strongest dedupe) - ONLY if we have actual values
    mask1 = (df["TxnId"] != "") & (df["Account"] != "")
    if mask1.any():
        before_count = len(df)
        # Only dedupe the subset that has TxnId and Account, leave others alone
        has_txnid_account = df[mask1]
        no_txnid_account = df[~mask1]
        
        deduped_with_txnid = has_txnid_account.drop_duplicates(subset=["TxnId", "Account"], keep="first")
        df = pd.concat([deduped_with_txnid, no_txnid_account], ignore_index=True)
        print(f"  Rule 1 (TxnId + Account): {before_count} -> {len(df)} rows ({before_count - len(df)} removed)")
    else:
        print(f"  Rule 1 (TxnId + Account): Skipped - no rows have both TxnId and Account")
    
    # Rule 2: Reference + Date + Amount + Time - ONLY if we have actual Reference values
    mask2 = df["Reference"] != ""
    if mask2.any():
        before_count = len(df)
        # Only dedupe the subset that has Reference, leave others alone
        has_reference = df[mask2]
        no_reference = df[~mask2]
        
        deduped_with_ref = has_reference.drop_duplicates(subset=["Reference", "Date", "Amount", "Time"], keep="first")
        df = pd.concat([deduped_with_ref, no_reference], ignore_index=True)
        print(f"  Rule 2 (Reference + Date + Amount + Time): {before_count} -> {len(df)} rows ({before_count - len(df)} removed)")
    else:
        print(f"  Rule 2 (Reference): Skipped - no rows have Reference values")
    
    # Rule 3: Content hash (entire row) - Debug this one
    before_count = len(df)
    print(f"  Checking OriginalHash uniqueness...")
    hash_counts = df["OriginalHash"].value_counts()
    duplicate_hashes = hash_counts[hash_counts > 1]
    if len(duplicate_hashes) > 0:
        print(f"  Found {len(duplicate_hashes)} hash values with duplicates:")
        for hash_val, count in duplicate_hashes.head(5).items():
            print(f"    Hash {hash_val}: {count} occurrences")
            # Show sample rows with this hash
            sample_rows = df[df["OriginalHash"] == hash_val][["Date", "Description", "Amount"]].head(2)
            print(f"    Sample rows:")
            for idx, row in sample_rows.iterrows():
                print(f"      {row['Date']} | {row['Description'][:50]}... | {row['Amount']}")
    
    df = df.drop_duplicates(subset=["OriginalHash"], keep="first")
    print(f"  Rule 3 (Content hash): {before_count} -> {len(df)} rows ({before_count - len(df)} removed)")
    
    print(f"  Final deduplication: {original_count} -> {len(df)} rows ({original_count - len(df)} total removed)")
    return df

def main():
    parser = argparse.ArgumentParser(description="Import CSV files to Excel Raw Data")
    parser.add_argument("--xlsx", required=True, help="Path to Excel workbook")
    parser.add_argument("--input", required=True, help="Input directory with CSV files")
    parser.add_argument("--recursive", action="store_true", help="Search subdirectories")
    parser.add_argument("--since", help="Only import rows after this date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--assume-encoding", help="Encoding hint for CSV files")
    parser.add_argument("--source-from", help="Source column name or 'filename'")
    parser.add_argument("--clear-raw", action="store_true", help="Clear Raw Data sheet first")
    
    args = parser.parse_args()
    
    print(f"Starting CSV import...")
    print(f"Excel file: {args.xlsx}")
    print(f"Input directory: {args.input}")
    
    # Check if Excel file exists
    excel_path = Path(args.xlsx)
    print(f"Checking Excel file: {excel_path}")
    print(f"Excel file exists: {excel_path.exists()}")
    print(f"Excel file is file: {excel_path.is_file()}")
    
    if not excel_path.exists():
        print(f"ERROR: Excel file not found: {excel_path}")
        return
    
    # Test if we can access the file
    try:
        import os
        print(f"File permissions: {oct(os.stat(excel_path).st_mode)}")
        with open(excel_path, 'rb') as f:
            print("Successfully opened file for reading")
    except PermissionError as e:
        print(f"PERMISSION ERROR: {e}")
        print("Possible solutions:")
        print("1. Close Excel if the file is open")
        print("2. Run as administrator")
        print("3. Check file/folder permissions")
        return
    except Exception as e:
        print(f"ERROR accessing file: {e}")
        return
    
    # Check if input directory exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input directory not found: {input_path}")
        return
    
    # Find CSV files
    pattern = "**/*.csv" if args.recursive else "*.csv"
    csv_files = list(input_path.glob(pattern))
    
    if not csv_files:
        print(f"No CSV files found in {input_path}")
        return
    
    print(f"Found {len(csv_files)} CSV files")
    
    if args.dry_run:
        print("DRY RUN - would process these files:")
        for f in csv_files:
            print(f"  {f}")
        return
    
    # Process CSV files
    all_data = []
    for csv_file in csv_files:
        try:
            print(f"Processing {csv_file.name}...")
            df = normalize_csv(csv_file, args.assume_encoding, args.source_from)
            
            # Apply date filter if specified
            if args.since:
                since_date = pd.to_datetime(args.since).date()
                df = df[pd.to_datetime(df["Date"]).dt.date >= since_date]
            
            all_data.append(df)
            print(f"  Added {len(df)} rows")
            
        except Exception as e:
            print(f"ERROR processing {csv_file.name}: {e}")
    
    if not all_data:
        print("No data to import")
        return
    
    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)
    print(f"Combined: {len(combined_df)} total rows")
    
    # Deduplicate
    deduped_df = deduplicate_dataframe(combined_df)
    print(f"After deduplication: {len(deduped_df)} rows")
    
    # Load existing Excel data
    try:
        with pd.ExcelFile(excel_path) as xls:
            if "Raw Data" in xls.sheet_names and not args.clear_raw:
                existing_df = pd.read_excel(xls, sheet_name="Raw Data")
                print(f"Existing Raw Data: {len(existing_df)} rows")
                
                # Combine with existing and dedupe again
                combined_with_existing = pd.concat([existing_df, deduped_df], ignore_index=True)
                final_df = deduplicate_dataframe(combined_with_existing)
                print(f"Final after merge and dedupe: {len(final_df)} rows")
            else:
                final_df = deduped_df
                if args.clear_raw:
                    print("Cleared existing Raw Data")
    except Exception as e:
        print(f"ERROR reading Excel file: {e}")
        return
    
    # Write to Excel
    try:
        with pd.ExcelWriter(excel_path, mode="a", if_sheet_exists="replace") as writer:
            final_df.to_excel(writer, sheet_name="Raw Data", index=False)
        print(f"Successfully wrote {len(final_df)} rows to Raw Data sheet")
    except Exception as e:
        print(f"ERROR writing to Excel: {e}")

if __name__ == "__main__":
    main()
