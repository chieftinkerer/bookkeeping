#!/usr/bin/env python3
"""
build_dup_review.py

Scans the "Raw Data" sheet for potential duplicates (using PossibleDupGroup)
and creates/updates "Dup Review" with:
- Decision, Reason (editable)
- GroupCount, PossibleDupGroup
- Date, Time, Description, Amount, Account, Source, TxnId, Reference, Balance, OriginalHash

Usage:
  python build_dup_review.py --file AI_Bookkeeping_Template.xlsx
"""
import argparse
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
    if raw is None or raw.empty or "PossibleDupGroup" not in raw.columns:
        dup_df = pd.DataFrame({
            "Instructions":[
                "No Raw Data with PossibleDupGroup found.",
                "Run csv_to_raw.py to import CSVs first.",
                "Then re-run build_dup_review.py."
            ]
        })
        with pd.ExcelWriter(xlsx, engine="openpyxl", mode="w") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
            dup_df.to_excel(writer, sheet_name="Dup Review", index=False)
        print("Created placeholder 'Dup Review' sheet (no data yet).")
        return

    for col in ["Date","Description","Amount","Source","TxnId","Reference","Time","Account","Balance","OriginalHash","PossibleDupGroup"]:
        if col not in raw.columns:
            raw[col] = "" if col not in ["Amount","Balance"] else 0.0

    grp = (raw.groupby("PossibleDupGroup").size().reset_index(name="GroupCount"))
    review = raw.merge(grp, on="PossibleDupGroup", how="left")

    cols = ["GroupCount","PossibleDupGroup","Date","Time","Description","Amount","Account","Source","TxnId","Reference","Balance","OriginalHash"]
    review = review[cols]
    review.insert(0, "Decision", "")
    review.insert(1, "Reason", "")
    review = review.sort_values(["GroupCount","PossibleDupGroup","Date","Amount"], ascending=[False, True, True, True])

    with pd.ExcelWriter(xlsx, engine="openpyxl", mode="w") as writer:
        for name, df in sheets.items():
            if name == "Dup Review":
                continue
            df.to_excel(writer, sheet_name=name, index=False)
        review.to_excel(writer, sheet_name="Dup Review", index=False)

    print(f"Built 'Dup Review' with {len(review)} rows. Groups with 2+ will be at the top.")

if __name__ == "__main__":
    main()
