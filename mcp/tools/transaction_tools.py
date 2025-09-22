"""
Transaction Tools for MCP Server

Provides transaction-related tools for querying, adding, and managing financial transactions.
"""

import hashlib
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class QueryTransactionsParams(BaseModel):
    """Parameters for querying transactions."""
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    category: Optional[str] = Field(None, description="Filter by category")
    vendor: Optional[str] = Field(None, description="Filter by vendor (partial match)")
    min_amount: Optional[float] = Field(None, description="Minimum amount")
    max_amount: Optional[float] = Field(None, description="Maximum amount")
    description_search: Optional[str] = Field(None, description="Search in transaction descriptions")
    limit: Optional[int] = Field(100, description="Maximum number of results")
    sort_by: Optional[str] = Field("date", description="Sort results by: date, amount, category")
    sort_order: Optional[str] = Field("desc", description="Sort order: asc, desc")

class AddTransactionParams(BaseModel):
    """Parameters for adding a new transaction."""
    date: str = Field(..., description="Transaction date (YYYY-MM-DD)")
    description: str = Field(..., description="Transaction description")
    amount: float = Field(..., description="Transaction amount (positive for income, negative for expenses)")
    category: Optional[str] = Field(None, description="Transaction category")
    vendor: Optional[str] = Field(None, description="Vendor name")
    account: Optional[str] = Field(None, description="Account identifier")
    notes: Optional[str] = Field(None, description="Additional notes")

class FindDuplicatesParams(BaseModel):
    """Parameters for finding duplicate transactions."""
    days_range: Optional[int] = Field(7, description="Look for duplicates within N days")
    amount_tolerance: Optional[float] = Field(0.0, description="Amount difference tolerance")
    limit: Optional[int] = Field(10, description="Maximum number of duplicate groups to return")

class TransactionTools:
    """Transaction-related MCP tools."""
    
    def __init__(self, db_manager):
        """Initialize with database manager."""
        self.db_manager = db_manager
        self.tx_ops = db_manager.get_transaction_operations()
    
    def query_transactions(self, params: QueryTransactionsParams) -> str:
        """
        Query transactions with flexible filtering options.
        
        Allows filtering by date range, category, vendor, amount, and description search.
        Results can be sorted and limited for better usability.
        """
        try:
            # Parse date parameters
            start_date_obj = None
            end_date_obj = None
            
            if params.start_date:
                start_date_obj = datetime.strptime(params.start_date, '%Y-%m-%d').date()
            if params.end_date:
                end_date_obj = datetime.strptime(params.end_date, '%Y-%m-%d').date()
            
            # Query transactions from database
            transactions = self.tx_ops.get_transactions(
                start_date=start_date_obj,
                end_date=end_date_obj,
                category=params.category,
                vendor=params.vendor,
                limit=params.limit
            )
            
            # Apply additional client-side filters
            filtered_transactions = []
            for tx in transactions:
                # Amount filters
                if params.min_amount is not None and float(tx['amount']) < params.min_amount:
                    continue
                if params.max_amount is not None and float(tx['amount']) > params.max_amount:
                    continue
                
                # Description search
                if params.description_search:
                    search_term = params.description_search.lower()
                    if search_term not in tx['description'].lower():
                        continue
                
                filtered_transactions.append(tx)
            
            # Sort results
            if params.sort_by == "date":
                filtered_transactions.sort(
                    key=lambda x: x['date'], 
                    reverse=(params.sort_order == "desc")
                )
            elif params.sort_by == "amount":
                filtered_transactions.sort(
                    key=lambda x: float(x['amount']), 
                    reverse=(params.sort_order == "desc")
                )
            elif params.sort_by == "category":
                filtered_transactions.sort(
                    key=lambda x: x.get('category', ''), 
                    reverse=(params.sort_order == "desc")
                )
            
            # Format response
            if not filtered_transactions:
                return "No transactions found matching the criteria."
            
            response = f"Found {len(filtered_transactions)} transactions:\n\n"
            total_amount = sum(float(tx['amount']) for tx in filtered_transactions)
            
            for tx in filtered_transactions:
                amount_str = f"${float(tx['amount']):.2f}"
                if float(tx['amount']) > 0:
                    amount_str = f"+{amount_str}"
                
                response += f"• {tx['date']} | {tx['description'][:50]}"
                if len(tx['description']) > 50:
                    response += "..."
                response += f" | {amount_str}"
                
                if tx.get('category'):
                    response += f" | {tx['category']}"
                if tx.get('vendor'):
                    response += f" | {tx['vendor']}"
                response += "\n"
            
            # Add summary
            response += f"\nSummary:"
            response += f"\n  Count: {len(filtered_transactions)} transactions"
            response += f"\n  Total: ${total_amount:.2f}"
            
            if total_amount != 0:
                income = sum(float(tx['amount']) for tx in filtered_transactions if float(tx['amount']) > 0)
                expenses = sum(abs(float(tx['amount'])) for tx in filtered_transactions if float(tx['amount']) < 0)
                if income > 0:
                    response += f"\n  Income: ${income:.2f}"
                if expenses > 0:
                    response += f"\n  Expenses: ${expenses:.2f}"
            
            return response
            
        except Exception as e:
            return f"Error querying transactions: {str(e)}"
    
    def add_transaction(self, params: AddTransactionParams) -> str:
        """
        Add a new transaction manually.
        
        Creates a new transaction with the provided details and stores it in the database.
        Automatically generates necessary hashes for deduplication.
        """
        try:
            # Parse and validate date
            tx_date = datetime.strptime(params.date, '%Y-%m-%d').date()
            
            # Generate row hash for deduplication
            def stable_rowhash(date, description, amount):
                s = f"{date}|{description}|{amount}"
                return hashlib.md5(s.encode()).hexdigest()
            
            row_hash = stable_rowhash(tx_date, params.description, params.amount)
            
            # Prepare transaction data
            transaction_data = {
                'date': tx_date,
                'description': params.description,
                'amount': params.amount,
                'category': params.category,
                'vendor': params.vendor,
                'source': 'manual_entry',
                'txn_id': None,
                'reference': None,
                'account': params.account,
                'balance': None,
                'original_hash': row_hash,
                'possible_dup_group': None,
                'row_hash': row_hash,
                'time_part': None
            }
            
            # Insert transaction
            tx_id = self.tx_ops.insert_transaction(transaction_data)
            
            response = f"✅ Transaction added successfully!\n\n"
            response += f"Transaction ID: {tx_id}\n"
            response += f"Date: {tx_date}\n"
            response += f"Description: {params.description}\n"
            response += f"Amount: ${params.amount:.2f}"
            
            if params.amount > 0:
                response += " (Income)"
            else:
                response += " (Expense)"
            
            if params.category:
                response += f"\nCategory: {params.category}"
            if params.vendor:
                response += f"\nVendor: {params.vendor}"
            if params.account:
                response += f"\nAccount: {params.account}"
            if params.notes:
                response += f"\nNotes: {params.notes}"
            
            return response
            
        except ValueError as e:
            return f"Invalid date format. Please use YYYY-MM-DD format. Error: {str(e)}"
        except Exception as e:
            return f"Error adding transaction: {str(e)}"
    
    def find_duplicates(self, params: FindDuplicatesParams) -> str:
        """
        Find potential duplicate transactions for review.
        
        Analyzes recent transactions to identify potential duplicates based on
        date proximity, amount similarity, and description matching.
        """
        try:
            # Get recent transactions for duplicate analysis
            end_date = date.today()
            start_date = end_date - timedelta(days=30)  # Look at last 30 days
            
            transactions = self.tx_ops.get_transactions(
                start_date=start_date,
                end_date=end_date
            )
            
            # Find potential duplicates
            potential_duplicates = []
            checked_pairs = set()
            
            for i, tx1 in enumerate(transactions):
                for j, tx2 in enumerate(transactions[i+1:], i+1):
                    # Create unique pair identifier
                    pair_key = tuple(sorted([tx1['id'], tx2['id']]))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)
                    
                    # Check similarity criteria
                    date_diff = abs((tx1['date'] - tx2['date']).days)
                    amount_diff = abs(float(tx1['amount']) - float(tx2['amount']))
                    desc_similar = tx1['description'].lower().strip() == tx2['description'].lower().strip()
                    
                    # Apply filters
                    if (date_diff <= params.days_range and 
                        amount_diff <= params.amount_tolerance and 
                        desc_similar):
                        
                        similarity_score = 1.0 - (date_diff / params.days_range + amount_diff / max(abs(float(tx1['amount'])), 0.01))
                        potential_duplicates.append({
                            'tx1': tx1,
                            'tx2': tx2,
                            'similarity_score': min(similarity_score, 1.0),
                            'date_diff': date_diff,
                            'amount_diff': amount_diff
                        })
                        
                        if len(potential_duplicates) >= params.limit:
                            break
                
                if len(potential_duplicates) >= params.limit:
                    break
            
            if not potential_duplicates:
                return f"No potential duplicates found in the last 30 days.\n\nCriteria used:\n- Within {params.days_range} days\n- Amount difference ≤ ${params.amount_tolerance:.2f}\n- Exact description match"
            
            # Sort by similarity score (highest first)
            potential_duplicates.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            response = f"🔍 Found {len(potential_duplicates)} potential duplicate pairs:\n\n"
            
            for i, dup in enumerate(potential_duplicates, 1):
                tx1, tx2 = dup['tx1'], dup['tx2']
                score = dup['similarity_score']
                
                response += f"{i}. Similarity: {score:.2f} | Date diff: {dup['date_diff']} days | Amount diff: ${dup['amount_diff']:.2f}\n"
                response += f"   A: {tx1['date']} | {tx1['description'][:60]} | ${float(tx1['amount']):.2f} (ID: {tx1['id']})\n"
                response += f"   B: {tx2['date']} | {tx2['description'][:60]} | ${float(tx2['amount']):.2f} (ID: {tx2['id']})\n\n"
            
            response += "💡 Review these transactions and remove duplicates manually if confirmed.\n"
            response += "Note: This analysis looks at the last 30 days of transactions."
            
            return response
            
        except Exception as e:
            return f"Error finding duplicates: {str(e)}"