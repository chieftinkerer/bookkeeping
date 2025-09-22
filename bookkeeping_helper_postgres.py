#!/usr/bin/env python3
"""
bookkeeping_helper_postgres.py (PostgreSQL version of bookkeeping_helper.py)

Use:
  1) Import transactions using csv_to_postgres.py
  2) (Optional) Define vendor mapping rules in vendor_mappings table
  3) Set OPENAI_API_KEY in your environment.
  4) Run:
       python bookkeeping_helper_postgres.py [--batch 50] [--limit 100]

What it does:
  - Loads uncategorized transactions from PostgreSQL.
  - Applies vendor mapping rules first.
  - Sends remaining rows to OpenAI API for vendor cleanup + category.
  - Updates transactions in PostgreSQL with categories and cleaned vendor names.
  - Generates summary statistics.

Dependencies:
  pip install psycopg2-binary requests python-dateutil python-dotenv
"""

import os
import json
import time
import argparse
import hashlib
from datetime import datetime, date
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv

# Import our database utilities
from database import DatabaseManager, TransactionOperations, VendorMappingOperations, ProcessingLogOperations

# Load environment variables
load_dotenv()

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

class BookkeepingHelperPostgres:
    """PostgreSQL-based bookkeeping assistant for AI categorization."""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.tx_ops = TransactionOperations(self.db)
        self.vendor_ops = VendorMappingOperations(self.db)
        self.log_ops = ProcessingLogOperations(self.db)
        
        # OpenAI configuration
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o-mini"
    
    def apply_vendor_mappings(self, transactions: List[Dict]) -> List[Dict]:
        """Apply vendor mapping rules to transactions."""
        print(f"🏪 Applying vendor mapping rules...")
        
        # Get all vendor mappings
        mappings = self.vendor_ops.get_vendor_mappings()
        print(f"📋 Found {len(mappings)} vendor mapping rules")
        
        updated_count = 0
        for transaction in transactions:
            description = transaction.get('description', '')
            if not description:
                continue
            
            # Find matching category
            category = self.vendor_ops.find_category_for_vendor(description)
            if category:
                transaction['suggested_category'] = category
                transaction['vendor'] = self._clean_vendor_name(description)
                transaction['notes'] = 'Auto-categorized by vendor mapping'
                updated_count += 1
        
        print(f"✅ Applied vendor mappings to {updated_count} transactions")
        return transactions
    
    def _clean_vendor_name(self, description: str) -> str:
        """Clean vendor name by removing common suffixes and store numbers."""
        vendor = description.strip()
        
        # Remove common suffixes
        suffixes_to_remove = [
            r'#\d+', r'\d{4,}', r'STORE \d+', r'LOCATION \d+',
            r'LLC', r'INC', r'CORP', r'CO\.?$'
        ]
        
        import re
        for suffix in suffixes_to_remove:
            vendor = re.sub(suffix, '', vendor, flags=re.IGNORECASE).strip()
        
        return vendor[:100]  # Limit length for database
    
    def prepare_batch_for_openai(self, transactions: List[Dict]) -> List[Dict]:
        """Prepare transaction batch for OpenAI API."""
        batch = []
        for tx in transactions:
            # Skip if already has category from vendor mapping
            if tx.get('suggested_category'):
                continue
                
            batch_item = {
                'date': str(tx['date']),
                'description': tx['description'],
                'amount': float(tx['amount']),
                'rowhash': tx['row_hash']
            }
            batch.append(batch_item)
        
        return batch
    
    def call_openai_api(self, batch: List[Dict]) -> List[Dict]:
        """Call OpenAI API to categorize transactions."""
        if not batch:
            return []
        
        print(f"🤖 Sending {len(batch)} transactions to OpenAI...")
        
        user_prompt = f"Categorize these {len(batch)} transactions:\\n"
        for i, row in enumerate(batch, 1):
            user_prompt += f"{i}. {row['date']} | {row['description']} | ${row['amount']:.2f} | {row['rowhash']}\\n"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 2000
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            
            print(f"✅ Received response from OpenAI")
            
            # Parse JSON response
            try:
                parsed = json.loads(content)
                return parsed.get("rows", [])
            except json.JSONDecodeError as e:
                print(f"⚠️  Failed to parse OpenAI response as JSON: {e}")
                print(f"Raw response: {content[:200]}...")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"❌ OpenAI API request failed: {e}")
            return []
        except Exception as e:
            print(f"❌ Unexpected error calling OpenAI: {e}")
            return []
    
    def process_openai_response(self, transactions: List[Dict], openai_results: List[Dict]) -> List[Dict]:
        """Process OpenAI response and update transactions."""
        if not openai_results:
            return transactions
        
        # Create a lookup by rowhash
        openai_lookup = {result.get('rowhash'): result for result in openai_results}
        
        updated_count = 0
        for transaction in transactions:
            row_hash = transaction['row_hash']
            
            # Skip if already categorized by vendor mapping
            if transaction.get('suggested_category'):
                continue
            
            openai_result = openai_lookup.get(row_hash)
            if openai_result:
                transaction['suggested_category'] = openai_result.get('suggested_category', 'Misc')
                transaction['vendor'] = openai_result.get('vendor', self._clean_vendor_name(transaction['description']))
                transaction['notes'] = openai_result.get('notes', 'AI categorized')
                updated_count += 1
        
        print(f"✅ Applied OpenAI categorization to {updated_count} transactions")
        return transactions
    
    def update_transactions_in_db(self, transactions: List[Dict]) -> int:
        """Update transactions in database with categories and vendor names."""
        print(f"💾 Updating {len(transactions)} transactions in database...")
        
        updated_count = 0
        for transaction in transactions:
            if not transaction.get('suggested_category'):
                continue
            
            success = self.tx_ops.update_transaction_category(
                transaction_id=transaction['id'],
                category=transaction['suggested_category'],
                vendor=transaction.get('vendor')
            )
            
            if success:
                updated_count += 1
        
        print(f"✅ Updated {updated_count} transactions in database")
        return updated_count
    
    def generate_summary_stats(self) -> Dict[str, Any]:
        """Generate summary statistics from the database."""
        print(f"📊 Generating summary statistics...")
        
        # Get monthly summary
        monthly_summary = self.tx_ops.get_monthly_summary()
        
        # Get basic counts
        total_transactions = self.db.get_table_row_count('transactions')
        uncategorized_count = len(self.tx_ops.get_uncategorized_transactions())
        
        # Get category breakdown for current month
        current_month = date.today().replace(day=1)
        current_month_transactions = self.tx_ops.get_transactions(
            start_date=current_month,
            end_date=date.today()
        )
        
        category_totals = {}
        for tx in current_month_transactions:
            category = tx.get('category', 'Uncategorized')
            amount = float(tx.get('amount', 0))
            if category not in category_totals:
                category_totals[category] = 0
            category_totals[category] += amount
        
        stats = {
            'total_transactions': total_transactions,
            'uncategorized_count': uncategorized_count,
            'categorized_count': total_transactions - uncategorized_count,
            'current_month_spending': category_totals,
            'monthly_summary_rows': len(monthly_summary)
        }
        
        return stats
    
    def run_categorization(self, batch_size: int = 50, limit: Optional[int] = None) -> Dict[str, Any]:
        """Run the complete categorization process."""
        print(f"🚀 Starting AI categorization process...")
        
        # Start processing log
        log_id = self.log_ops.start_operation(
            operation_type='ai_categorization_postgres',
            details={'batch_size': batch_size, 'limit': limit}
        )
        
        try:
            # Get uncategorized transactions
            uncategorized = self.tx_ops.get_uncategorized_transactions(limit=limit)
            print(f"📋 Found {len(uncategorized)} uncategorized transactions")
            
            if not uncategorized:
                print("✅ No uncategorized transactions found!")
                self.log_ops.complete_operation(log_id, status='completed',
                                              details={'note': 'No uncategorized transactions'})
                return {'processed': 0, 'updated': 0}
            
            # Apply vendor mappings first
            uncategorized = self.apply_vendor_mappings(uncategorized)
            
            # Process in batches
            total_processed = 0
            total_updated = 0
            
            for i in range(0, len(uncategorized), batch_size):
                batch = uncategorized[i:i + batch_size]
                print(f"\n📦 Processing batch {i//batch_size + 1} ({len(batch)} transactions)...")
                
                # Prepare batch for OpenAI (excluding already categorized ones)
                openai_batch = self.prepare_batch_for_openai(batch)
                
                if openai_batch:
                    # Call OpenAI API
                    openai_results = self.call_openai_api(openai_batch)
                    
                    # Process response
                    batch = self.process_openai_response(batch, openai_results)
                
                # Update database
                updated_count = self.update_transactions_in_db(batch)
                
                total_processed += len(batch)
                total_updated += updated_count
                
                print(f"✅ Batch {i//batch_size + 1} complete: {updated_count}/{len(batch)} updated")
                
                # Rate limiting for OpenAI API
                if openai_batch and i + batch_size < len(uncategorized):
                    print("⏳ Waiting 2 seconds to respect API rate limits...")
                    time.sleep(2)
            
            # Complete processing log
            self.log_ops.complete_operation(
                log_id,
                records_processed=total_processed,
                records_updated=total_updated,
                status='completed'
            )
            
            print(f"\n🎉 Categorization completed!")
            print(f"📊 Processed: {total_processed} transactions")
            print(f"💾 Updated: {total_updated} transactions")
            
            # Generate summary stats
            stats = self.generate_summary_stats()
            print(f"\n📈 Summary Statistics:")
            print(f"  📊 Total transactions: {stats['total_transactions']}")
            print(f"  ✅ Categorized: {stats['categorized_count']}")
            print(f"  ❓ Uncategorized: {stats['uncategorized_count']}")
            
            return {
                'processed': total_processed,
                'updated': total_updated,
                'stats': stats
            }
            
        except Exception as e:
            print(f"❌ Categorization failed: {e}")
            self.log_ops.complete_operation(log_id, status='failed',
                                          details={'error': str(e)})
            raise

def main():
    """Main function for running AI categorization."""
    parser = argparse.ArgumentParser(description="AI categorization for PostgreSQL transactions")
    parser.add_argument("--batch", type=int, default=50, 
                       help="Batch size for OpenAI API calls (default: 50)")
    parser.add_argument("--limit", type=int, 
                       help="Limit number of transactions to process")
    parser.add_argument("--stats-only", action="store_true",
                       help="Only generate and display statistics")
    parser.add_argument("--test-connection", action="store_true",
                       help="Test database and API connections")
    
    args = parser.parse_args()
    
    try:
        helper = BookkeepingHelperPostgres()
        
        if args.test_connection:
            print("✅ Database connection successful")
            print("✅ OpenAI API key configured")
            
            # Test basic queries
            uncategorized_count = len(helper.tx_ops.get_uncategorized_transactions(limit=1))
            total_count = helper.db.get_table_row_count('transactions')
            print(f"📊 Database status: {total_count} total transactions, {uncategorized_count} uncategorized")
            return 0
        
        if args.stats_only:
            stats = helper.generate_summary_stats()
            print(f"📈 Summary Statistics:")
            print(f"  📊 Total transactions: {stats['total_transactions']}")
            print(f"  ✅ Categorized: {stats['categorized_count']}")
            print(f"  ❓ Uncategorized: {stats['uncategorized_count']}")
            print(f"  📅 Current month categories:")
            for category, amount in stats['current_month_spending'].items():
                print(f"    {category}: ${amount:.2f}")
            return 0
        
        # Run categorization
        result = helper.run_categorization(
            batch_size=args.batch,
            limit=args.limit
        )
        
        if result['updated'] > 0:
            print(f"\n💡 Next steps:")
            print(f"  📊 Review categorized transactions")
            print(f"  📈 Generate reports or charts")
            print(f"  🔄 Run again to categorize remaining transactions")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())