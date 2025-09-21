#!/usr/bin/env python3
"""
bookkeeping_helper.py

Use:
  1) Put transactions in "Raw Data" (Date, Description, Amount [+optional metadata])
  2) (Optional) Define "VendorMap" with rules: VendorPattern, Category
  3) Set OPENAI_API_KEY in your environment.
  4) Run:
       python bookkeeping_helper.py --file AI_Bookkeeping_Template.xlsx --batch 150

What it does:
  - Loads Raw Data, computes RowHash per row.
  - Skips rows already present in Clean Data (by RowHash).
  - Applies VendorMap rules first.
  - Sends remaining rows to OpenAI Responses API for vendor cleanup + category.
  - Writes results to Clean Data and generates a Summary pivot by Month x Category.

Dependencies:
  pip install pandas openpyxl requests python-dateutil
"""

import os
import json
import time
import argparse
import hashlib
from datetime import datetime
from dateutil.parser import parse as dtparse

import pandas as pd
import requests

CATEGORIES = [
    "Groceries","Dining","Utilities","Subscriptions","Transportation",
    "Housing","Healthcare","Insurance","Income","Shopping","Misc"
]

SYSTEM_PROMPT = (
    "You are a bookkeeping assistant.\n"
    "- For each row, standardize vendor names (strip store numbers/codes).\n"
    f"- Map each row to one of: {', '.join(CATEGORIES)}.\n"
    "- Flag duplicates or unusual charges in 'notes' with a short reason.\n"
    "Return ONLY a compact JSON object with key 'rows':\n"
    "  {\"rows\": [{date, vendor, amount, suggested_category, notes, rowhash}]}\n"
    "Do not include markdown, code fences, or explanations."
)

def stable_rowhash(date, description, amount):
    """Generate a stable hash for a transaction row."""
    key = f"{date}|{description}|{amount:.2f}".encode("utf-8", errors="ignore")
    return hashlib.sha256(key).hexdigest()[:16]

def normalize_date(x):
    if pd.isna(x) or str(x).strip() == "":
        return ""
    try:
        return dtparse(str(x)).date().isoformat()
    except Exception:
        return str(x)

def apply_vendor_map(df, vendor_map):
    if vendor_map is None or vendor_map.empty:
        df["Vendor_ai"] = None
        df["Category_ai"] = None
        return df
    patterns = [(str(pat).strip().lower(), str(cat).strip()) for pat, cat in vendor_map[["VendorPattern","Category"]].itertuples(index=False)]
    vendors, cats = [], []
    for desc in df["Description"].astype(str):
        dlow = desc.lower()
        chosen_cat, vendor_clean = None, None
        for pat, cat in patterns:
            if pat and pat in dlow:
                chosen_cat = cat
                vendor_clean = " ".join(w.capitalize() for w in pat.split())
                break
        vendors.append(vendor_clean)
        cats.append(chosen_cat)
    df["Vendor_ai"] = vendors
    df["Category_ai"] = cats
    return df

def call_openai_chat(api_key, rows, model):
    """Call OpenAI Chat Completions API to categorize transactions."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    user_payload = {"rows": rows}
    
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
        ],
        "temperature": 0.1
    }
    
    # Retry logic for timeout errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"  Making API call (attempt {attempt + 1}/{max_retries}) for {len(rows)} transactions...")
            resp = requests.post(url, headers=headers, json=body, timeout=120)  # Increased timeout
            resp.raise_for_status()
            data = resp.json()
            
            # Extract the response content
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            result = parsed.get("rows", [])
            if not isinstance(result, list):
                result = []
            print(f"  ✅ Successfully processed {len(result)} transactions")
            return result
            
        except requests.exceptions.ReadTimeout:
            print(f"  ⚠️ API call timed out (attempt {attempt + 1}/{max_retries})")
            if attempt == max_retries - 1:
                print(f"  ❌ All {max_retries} attempts failed. Falling back to default categorization.")
                return []
            print(f"  🔄 Retrying in 5 seconds...")
            time.sleep(5)
        except requests.HTTPError as e:
            print(f"  ❌ HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            raise
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"  ⚠️ Failed to parse API response: {e}")
            return []
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            raise
    
    return []

def write_clean_and_summary(xlsx_path, clean_rows):
    try:
        # Read all sheets once
        sheets = pd.read_excel(xlsx_path, sheet_name=None, engine="openpyxl")
    except FileNotFoundError:
        raise SystemExit(f"Workbook not found: {xlsx_path}")

    clean_df_existing = sheets.get("Clean Data", pd.DataFrame(columns=["Date","Vendor","Amount","Suggested Category","Notes","RowHash"]))
    combined = clean_df_existing.copy()

    add_df = pd.DataFrame(clean_rows)
    if not add_df.empty:
        add_df = add_df.rename(columns={
            "date":"Date","vendor":"Vendor","amount":"Amount",
            "suggested_category":"Suggested Category","notes":"Notes","rowhash":"RowHash"
        })
        add_df = add_df[["Date","Vendor","Amount","Suggested Category","Notes","RowHash"]]
        
        # Fix FutureWarning by ensuring both DataFrames have the same columns before concat
        if combined.empty:
            combined = add_df.copy()
        else:
            combined = pd.concat([combined, add_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["RowHash"], keep="first")

    # Summary pivot
    if not combined.empty:
        dates = pd.to_datetime(combined["Date"], errors="coerce")
        combined["Month"] = dates.dt.to_period("M").astype(str)
        piv = (combined.groupby(["Month","Suggested Category"], dropna=False)["Amount"].sum().reset_index())
        piv = piv.pivot(index="Suggested Category", columns="Month", values="Amount").fillna(0.0)
    else:
        piv = pd.DataFrame()

    # Write all sheets back using mode="a" with if_sheet_exists="replace"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        # Write existing sheets first
        if "Raw Data" in sheets:
            sheets["Raw Data"].to_excel(writer, sheet_name="Raw Data", index=False)
        if "VendorMap" in sheets:
            sheets["VendorMap"].to_excel(writer, sheet_name="VendorMap", index=False)
        if "Dup Review" in sheets:
            sheets["Dup Review"].to_excel(writer, sheet_name="Dup Review", index=False)
        if "Deleted Rows" in sheets:
            sheets["Deleted Rows"].to_excel(writer, sheet_name="Deleted Rows", index=False)

        # Write new/updated sheets
        combined.to_excel(writer, sheet_name="Clean Data", index=False)
        if piv.empty:
            pd.DataFrame({"Note":["Add data to see the summary."]}).to_excel(writer, sheet_name="Summary", index=False)
        else:
            piv.to_excel(writer, sheet_name="Summary")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="AI_Bookkeeping_Template.xlsx")
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not args.dry_run and not api_key:
        raise SystemExit("Set OPENAI_API_KEY (or use --dry-run)." )

    sheets = pd.read_excel(args.file, sheet_name=None, engine="openpyxl")
    raw = sheets.get("Raw Data")
    if raw is None or raw.empty:
        raise SystemExit("Raw Data sheet is empty or missing.")

    req_cols = ["Date","Description","Amount"]
    for c in req_cols:
        if c not in raw.columns:
            raise SystemExit(f"Raw Data must include column: {c}")

    df = raw.copy()
    df["Date"] = df["Date"].apply(lambda x: normalize_date(x))
    df["Description"] = df["Description"].astype(str).fillna("")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    df["RowHash"] = df.apply(lambda r: stable_rowhash(r["Date"], r["Description"], float(r["Amount"])), axis=1)

    clean_existing = sheets.get("Clean Data", pd.DataFrame(columns=["RowHash"]))
    existing_hashes = set(clean_existing.get("RowHash", pd.Series(dtype=str)).dropna().astype(str).tolist())

    df_new = df[~df["RowHash"].isin(existing_hashes)].reset_index(drop=True)
    if df_new.empty:
        print("No new rows to process. Clean Data is up to date.")
        return

    vendor_map = sheets.get("VendorMap", pd.DataFrame(columns=["VendorPattern","Category"]))    
    df_new = apply_vendor_map(df_new, vendor_map)

    mapped_mask = df_new["Category_ai"].notna() & (df_new["Category_ai"].astype(str).str.len() > 0)
    df_mapped = df_new[mapped_mask].copy()
    df_ai = df_new[~mapped_mask].copy()

    out_rows = []
    for _, r in df_mapped.iterrows():
        out_rows.append({
            "date": r["Date"],
            "vendor": (r["Vendor_ai"] if pd.notna(r["Vendor_ai"]) and r["Vendor_ai"] else r["Description"])[:120],
            "amount": float(r["Amount"]),
            "suggested_category": str(r["Category_ai"]),
            "notes": "Mapped by VendorMap",
            "rowhash": r["RowHash"]
        })

    if not args.dry_run and not df_ai.empty:
        records = df_ai[["Date","Description","Amount","RowHash"]].to_dict(orient="records")
        for i in range(0, len(records), args.batch):
            chunk = records[i:i+args.batch]
            input_rows = [{
                "date": r["Date"],
                "description": r["Description"],
                "amount": float(r["Amount"]),
                "rowhash": r["RowHash"]
            } for r in chunk]

            try:
                result = call_openai_chat(api_key, input_rows, args.model)
            except requests.HTTPError as e:
                print("API error:", e.response.text[:500])
                raise
            except Exception as e:
                print("API error:", repr(e))
                raise

            by_hash = {x.get("rowhash"): x for x in result if isinstance(x, dict) and x.get("rowhash")}
            for r in input_rows:
                x = by_hash.get(r["rowhash"])
                if not x:
                    x = {
                        "date": r["date"],
                        "vendor": r["description"][:60],
                        "amount": r["amount"],
                        "suggested_category": "Misc",
                        "notes": "AI fallback: unmatched row",
                        "rowhash": r["rowhash"]
                    }
                sc = str(x.get("suggested_category","Misc"))
                if sc not in CATEGORIES:
                    sc = "Misc"
                out_rows.append({
                    "date": x.get("date", r["date"]),
                    "vendor": x.get("vendor", r["description"])[:120],
                    "amount": float(x.get("amount", r["amount"])),
                    "suggested_category": sc,
                    "notes": x.get("notes", ""),
                    "rowhash": r["rowhash"]
                })
            time.sleep(0.5)
    else:
        for _, r in df_ai.iterrows():
            out_rows.append({
                "date": r["Date"],
                "vendor": r["Description"][:120],
                "amount": float(r["Amount"]),
                "suggested_category": "Misc",
                "notes": "Dry-run (no API call)",
                "rowhash": r["RowHash"]
            })

    write_clean_and_summary(args.file, out_rows)
    print(f"Processed {len(out_rows)} rows. Wrote Clean Data and Summary.")

if __name__ == "__main__":
    main()
