#!/usr/bin/env python3
"""
cleanup_dupes.py  (with audit trail)

Moves any transactions you mark as Decision == 'Delete' in 'Dup Review'
from 'Raw Data' to a 'Deleted Rows' sheet (appending), then rewrites Raw Data
without them.

Usage:
  pip install pandas openpyxl
  python cleanup_dupes.py --file AI_Bookkeeping_Template.xlsx

Behavior:
- Matches by OriginalHash (unique per normalized row).
- Creates 'Deleted Rows' sheet if it doesn't exist and appends future deletions.
- Adds DeletedAt timestamp and SourceSheet indicator to the moved rows.
- Leaves all other sheets intact.
"""
import argparse
from datetime import datetime
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="AI_Bookkeeping_Template.xlsx")
    args = ap.parse_args()

    xlsx = args.file
    try:
        sheets = pd.read_excel(xlsx, sheet_name=None, engine="openpyxl")
    except FileNotFoundError:
        raise SystemExit(f"Workbook not found: {xlsx}")

    raw = sheets.get("Raw Data")
    dup = sheets.get("Dup Review")
    deleted = sheets.get("Deleted Rows")

    if raw is None or dup is None:
        raise SystemExit("Workbook must contain 'Raw Data' and 'Dup Review' sheets.")

    if "Decision" not in dup.columns or "OriginalHash" not in dup.columns:
        raise SystemExit("Dup Review must have 'Decision' and 'OriginalHash' columns.")

    delete_hashes = set(
        dup.loc[dup["Decision"].astype(str).str.lower() == "delete", "OriginalHash"]
        .dropna().astype(str).tolist()
    )
    if not delete_hashes:
        print("No rows marked for deletion.")
        return

    raw["OriginalHash"] = raw["OriginalHash"].astype(str)
    to_move_mask = raw["OriginalHash"].isin(delete_hashes)
    rows_to_move = raw[to_move_mask].copy()
    rows_keep = raw[~to_move_mask].copy()

    if rows_to_move.empty:
        print("No matching rows found in Raw Data for the selected OriginalHash values.")
        return

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    rows_to_move["DeletedAt"] = now
    rows_to_move["SourceSheet"] = "Raw Data"

    if deleted is None or deleted.empty:
        deleted_new = rows_to_move
    else:
        for col in rows_to_move.columns:
            if col not in deleted.columns:
                deleted[col] = ""
        for col in deleted.columns:
            if col not in rows_to_move.columns:
                rows_to_move[col] = ""
        deleted_new = pd.concat([deleted, rows_to_move], ignore_index=True)

    with pd.ExcelWriter(xlsx, engine="openpyxl", mode="w") as writer:
        for name, df in sheets.items():
            if name == "Raw Data":
                rows_keep.to_excel(writer, sheet_name="Raw Data", index=False)
            elif name == "Deleted Rows":
                continue
            else:
                df.to_excel(writer, sheet_name=name, index=False)
        deleted_new.to_excel(writer, sheet_name="Deleted Rows", index=False)

    print(f"Moved {len(rows_to_move)} row(s) to 'Deleted Rows'. Raw Data now has {len(rows_keep)} row(s).")

if __name__ == "__main__":
    main()
