#!/usr/bin/env python3
"""
bookkeeping_mcp_server.py

MCP (Model Context Protocol) server for AI-assisted bookkeeping.
Provides tools for natural language interaction with financial transaction data.

This enables AI chat interfaces (like Claude) to:
- Query transactions with natural language
- Generate spending analysis and insights
- Create monthly/yearly summaries
- Find and review potential duplicates
- Add new transactions
- Generate visualizations

Usage:
    python bookkeeping_mcp_server.py

The server will start and provide MCP tools that can be used by AI assistants.
"""

import asyncio
import json
import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
from dotenv import load_dotenv

# Import our database utilities
from database import DatabaseManager, TransactionOperations, VendorMappingOperations, ProcessingLogOperations

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BookkeepingMCPServer:
    """MCP Server for AI-assisted bookkeeping operations."""
    
    def __init__(self):
        self.server = Server("ai-bookkeeping")
        self.db = DatabaseManager()
        self.tx_ops = TransactionOperations(self.db)
        self.vendor_ops = VendorMappingOperations(self.db)
        self.log_ops = ProcessingLogOperations(self.db)
        
        # Register tools
        self._register_tools()
        
        logger.info("BookkeepingMCPServer initialized successfully")
    
    def _register_tools(self):
        """Register all MCP tools."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List all available tools."""
            return [
                Tool(
                    name="query_transactions",
                    description="Query transactions with flexible filtering options",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                            "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                            "category": {"type": "string", "description": "Filter by category"},
                            "vendor": {"type": "string", "description": "Filter by vendor (partial match)"},
                            "min_amount": {"type": "number", "description": "Minimum amount"},
                            "max_amount": {"type": "number", "description": "Maximum amount"},
                            "description_search": {"type": "string", "description": "Search in transaction descriptions"},
                            "limit": {"type": "integer", "description": "Maximum number of results"},
                            "sort_by": {"type": "string", "enum": ["date", "amount", "category"], "description": "Sort results by"},
                            "sort_order": {"type": "string", "enum": ["asc", "desc"], "description": "Sort order"}
                        }
                    }
                ),
                Tool(
                    name="monthly_summary",
                    description="Generate monthly spending summary and analysis",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "year": {"type": "integer", "description": "Year for summary (defaults to current year)"},
                            "month": {"type": "integer", "description": "Month for summary (1-12, defaults to current month)"},
                            "include_comparison": {"type": "boolean", "description": "Include comparison with previous month"}
                        }
                    }
                ),
                Tool(
                    name="spending_analysis",
                    description="Analyze spending patterns and provide insights",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "period": {"type": "string", "enum": ["month", "quarter", "year"], "description": "Analysis period"},
                            "category_focus": {"type": "string", "description": "Focus analysis on specific category"},
                            "include_trends": {"type": "boolean", "description": "Include trend analysis"}
                        }
                    }
                ),
                Tool(
                    name="find_duplicates",
                    description="Find potential duplicate transactions for review",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "days_range": {"type": "integer", "description": "Look for duplicates within N days (default: 7)"},
                            "amount_tolerance": {"type": "number", "description": "Amount difference tolerance (default: 0.0)"},
                            "limit": {"type": "integer", "description": "Maximum number of duplicate groups to return"}
                        }
                    }
                ),
                Tool(
                    name="add_transaction",
                    description="Add a new transaction manually",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Transaction date (YYYY-MM-DD)"},
                            "description": {"type": "string", "description": "Transaction description"},
                            "amount": {"type": "number", "description": "Transaction amount (positive for income, negative for expenses)"},
                            "category": {"type": "string", "description": "Transaction category"},
                            "vendor": {"type": "string", "description": "Vendor name (optional)"},
                            "account": {"type": "string", "description": "Account identifier (optional)"},
                            "notes": {"type": "string", "description": "Additional notes (optional)"}
                        },
                        "required": ["date", "description", "amount"]
                    }
                ),
                Tool(
                    name="get_categories",
                    description="Get all available spending categories",
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="update_vendor_mapping",
                    description="Add or update vendor mapping rule for automatic categorization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "vendor_pattern": {"type": "string", "description": "Vendor name pattern to match"},
                            "category": {"type": "string", "description": "Category to assign"},
                            "is_regex": {"type": "boolean", "description": "Whether pattern is regex (default: false)"},
                            "priority": {"type": "integer", "description": "Rule priority (higher = more important)"}
                        },
                        "required": ["vendor_pattern", "category"]
                    }
                ),
                Tool(
                    name="database_stats",
                    description="Get database statistics and health information",
                    inputSchema={"type": "object", "properties": {}}
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                if name == "query_transactions":
                    return await self._handle_query_transactions(arguments)
                elif name == "monthly_summary":
                    return await self._handle_monthly_summary(arguments)
                elif name == "spending_analysis":
                    return await self._handle_spending_analysis(arguments)
                elif name == "find_duplicates":
                    return await self._handle_find_duplicates(arguments)
                elif name == "add_transaction":
                    return await self._handle_add_transaction(arguments)
                elif name == "get_categories":
                    return await self._handle_get_categories(arguments)
                elif name == "update_vendor_mapping":
                    return await self._handle_update_vendor_mapping(arguments)
                elif name == "database_stats":
                    return await self._handle_database_stats(arguments)
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
            except Exception as e:
                logger.error(f"Error handling tool {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _handle_query_transactions(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle transaction query requests."""
        try:
            # Parse arguments
            start_date = args.get('start_date')
            end_date = args.get('end_date')
            category = args.get('category')
            vendor = args.get('vendor')
            limit = args.get('limit', 100)
            
            # Convert date strings to date objects
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
            
            # Query transactions
            transactions = self.tx_ops.get_transactions(
                start_date=start_date_obj,
                end_date=end_date_obj,
                category=category,
                vendor=vendor,
                limit=limit
            )
            
            # Apply additional filters
            if args.get('min_amount') is not None:
                transactions = [t for t in transactions if float(t['amount']) >= args['min_amount']]
            if args.get('max_amount') is not None:
                transactions = [t for t in transactions if float(t['amount']) <= args['max_amount']]
            if args.get('description_search'):
                search_term = args['description_search'].lower()
                transactions = [t for t in transactions if search_term in t['description'].lower()]
            
            # Sort results
            sort_by = args.get('sort_by', 'date')
            sort_order = args.get('sort_order', 'desc')
            reverse = sort_order == 'desc'
            
            if sort_by == 'date':
                transactions.sort(key=lambda x: x['date'], reverse=reverse)
            elif sort_by == 'amount':
                transactions.sort(key=lambda x: float(x['amount']), reverse=reverse)
            elif sort_by == 'category':
                transactions.sort(key=lambda x: x.get('category', ''), reverse=reverse)
            
            # Format response
            if not transactions:
                return [TextContent(type="text", text="No transactions found matching the criteria.")]
            
            response = f"Found {len(transactions)} transactions:\n\n"
            total_amount = sum(float(t['amount']) for t in transactions)
            
            for tx in transactions:
                response += f"• {tx['date']} | {tx['description']} | ${float(tx['amount']):.2f}"
                if tx.get('category'):
                    response += f" | {tx['category']}"
                if tx.get('vendor'):
                    response += f" | {tx['vendor']}"
                response += "\n"
            
            response += f"\nTotal: ${total_amount:.2f}"
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error querying transactions: {str(e)}")]
    
    async def _handle_monthly_summary(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle monthly summary requests."""
        try:
            year = args.get('year', datetime.now().year)
            month = args.get('month', datetime.now().month)
            
            # Get date range for the month
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            # Get transactions for the month
            transactions = self.tx_ops.get_transactions(
                start_date=start_date,
                end_date=end_date
            )
            
            # Calculate summary by category
            category_totals = {}
            total_income = 0
            total_expenses = 0
            
            for tx in transactions:
                amount = float(tx['amount'])
                category = tx.get('category', 'Uncategorized')
                
                if amount > 0:
                    total_income += amount
                    category = 'Income'  # Group all positive amounts as income
                else:
                    total_expenses += abs(amount)
                
                if category not in category_totals:
                    category_totals[category] = 0
                category_totals[category] += abs(amount)
            
            # Generate response
            month_name = date(year, month, 1).strftime('%B %Y')
            response = f"📊 Monthly Summary for {month_name}\n\n"
            response += f"💰 Income: ${total_income:.2f}\n"
            response += f"💸 Expenses: ${total_expenses:.2f}\n"
            response += f"📈 Net: ${total_income - total_expenses:.2f}\n\n"
            
            response += "💳 Spending by Category:\n"
            sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
            for category, amount in sorted_categories:
                if category != 'Income':  # Skip income in expense breakdown
                    percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
                    response += f"  • {category}: ${amount:.2f} ({percentage:.1f}%)\n"
            
            response += f"\n📈 Transaction Count: {len(transactions)}"
            
            # Include comparison if requested
            if args.get('include_comparison'):
                # Get previous month data
                if month == 1:
                    prev_year, prev_month = year - 1, 12
                else:
                    prev_year, prev_month = year, month - 1
                
                prev_start = date(prev_year, prev_month, 1)
                if prev_month == 12:
                    prev_end = date(prev_year + 1, 1, 1) - timedelta(days=1)
                else:
                    prev_end = date(prev_year, prev_month + 1, 1) - timedelta(days=1)
                
                prev_transactions = self.tx_ops.get_transactions(
                    start_date=prev_start,
                    end_date=prev_end
                )
                
                prev_expenses = sum(abs(float(t['amount'])) for t in prev_transactions if float(t['amount']) < 0)
                expense_change = total_expenses - prev_expenses
                change_pct = (expense_change / prev_expenses * 100) if prev_expenses > 0 else 0
                
                response += f"\n\n📈 vs Previous Month:\n"
                response += f"  Expense Change: ${expense_change:+.2f} ({change_pct:+.1f}%)"
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error generating monthly summary: {str(e)}")]
    
    async def _handle_spending_analysis(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle spending analysis requests."""
        try:
            period = args.get('period', 'month')
            category_focus = args.get('category_focus')
            
            # Determine date range based on period
            today = date.today()
            if period == 'month':
                start_date = today.replace(day=1)
                end_date = today
            elif period == 'quarter':
                quarter_start_month = ((today.month - 1) // 3) * 3 + 1
                start_date = today.replace(month=quarter_start_month, day=1)
                end_date = today
            elif period == 'year':
                start_date = today.replace(month=1, day=1)
                end_date = today
            
            # Get transactions
            transactions = self.tx_ops.get_transactions(
                start_date=start_date,
                end_date=end_date,
                category=category_focus
            )
            
            if category_focus:
                # Focused analysis on specific category
                total_spent = sum(abs(float(t['amount'])) for t in transactions if float(t['amount']) < 0)
                avg_transaction = total_spent / len(transactions) if transactions else 0
                
                # Top vendors in this category
                vendor_totals = {}
                for tx in transactions:
                    if float(tx['amount']) < 0:  # Only expenses
                        vendor = tx.get('vendor') or tx['description'][:30] + "..."
                        amount = abs(float(tx['amount']))
                        vendor_totals[vendor] = vendor_totals.get(vendor, 0) + amount
                
                response = f"🔍 {category_focus} Analysis ({period})\n\n"
                response += f"💸 Total Spent: ${total_spent:.2f}\n"
                response += f"📊 Transactions: {len(transactions)}\n"
                response += f"📈 Average: ${avg_transaction:.2f}\n\n"
                
                response += "🏪 Top Vendors:\n"
                sorted_vendors = sorted(vendor_totals.items(), key=lambda x: x[1], reverse=True)[:5]
                for vendor, amount in sorted_vendors:
                    response += f"  • {vendor}: ${amount:.2f}\n"
            
            else:
                # General spending analysis
                category_totals = {}
                daily_totals = {}
                
                for tx in transactions:
                    amount = float(tx['amount'])
                    if amount < 0:  # Only expenses
                        amount = abs(amount)
                        category = tx.get('category', 'Uncategorized')
                        tx_date = tx['date']
                        
                        category_totals[category] = category_totals.get(category, 0) + amount
                        daily_totals[tx_date] = daily_totals.get(tx_date, 0) + amount
                
                total_expenses = sum(category_totals.values())
                avg_daily = total_expenses / len(daily_totals) if daily_totals else 0
                
                response = f"📊 Spending Analysis ({period})\n\n"
                response += f"💸 Total Expenses: ${total_expenses:.2f}\n"
                response += f"📅 Average Daily: ${avg_daily:.2f}\n"
                response += f"📈 Active Days: {len(daily_totals)}\n\n"
                
                response += "📂 By Category:\n"
                sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
                for category, amount in sorted_categories:
                    percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
                    response += f"  • {category}: ${amount:.2f} ({percentage:.1f}%)\n"
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error analyzing spending: {str(e)}")]
    
    async def _handle_find_duplicates(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle duplicate detection requests."""
        try:
            days_range = args.get('days_range', 7)
            amount_tolerance = args.get('amount_tolerance', 0.0)
            limit = args.get('limit', 10)
            
            # Get recent transactions
            end_date = date.today()
            start_date = end_date - timedelta(days=30)  # Look at last 30 days for duplicates
            
            transactions = self.tx_ops.get_transactions(
                start_date=start_date,
                end_date=end_date
            )
            
            # Find potential duplicates
            potential_duplicates = []
            checked_pairs = set()
            
            for i, tx1 in enumerate(transactions):
                for j, tx2 in enumerate(transactions[i+1:], i+1):
                    pair_key = tuple(sorted([tx1['id'], tx2['id']]))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)
                    
                    # Check if transactions are similar
                    date_diff = abs((tx1['date'] - tx2['date']).days)
                    amount_diff = abs(float(tx1['amount']) - float(tx2['amount']))
                    desc_similar = tx1['description'].lower() == tx2['description'].lower()
                    
                    if (date_diff <= days_range and 
                        amount_diff <= amount_tolerance and 
                        desc_similar):
                        potential_duplicates.append((tx1, tx2))
                        
                        if len(potential_duplicates) >= limit:
                            break
                
                if len(potential_duplicates) >= limit:
                    break
            
            if not potential_duplicates:
                return [TextContent(type="text", text="No potential duplicates found.")]
            
            response = f"🔍 Found {len(potential_duplicates)} potential duplicate pairs:\n\n"
            
            for i, (tx1, tx2) in enumerate(potential_duplicates, 1):
                response += f"{i}. Potential Duplicate:\n"
                response += f"   A: {tx1['date']} | {tx1['description']} | ${float(tx1['amount']):.2f}\n"
                response += f"   B: {tx2['date']} | {tx2['description']} | ${float(tx2['amount']):.2f}\n"
                response += f"   IDs: {tx1['id']}, {tx2['id']}\n\n"
            
            response += "💡 Review these transactions and remove duplicates if confirmed."
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error finding duplicates: {str(e)}")]
    
    async def _handle_add_transaction(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle manual transaction addition."""
        try:
            # Parse and validate arguments
            date_str = args['date']
            description = args['description']
            amount = float(args['amount'])
            
            # Parse date
            tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Generate row hash
            import hashlib
            def stable_rowhash(date, description, amount):
                s = f"{date}|{description}|{amount}"
                return hashlib.md5(s.encode()).hexdigest()
            
            row_hash = stable_rowhash(tx_date, description, amount)
            
            # Prepare transaction data
            transaction_data = {
                'date': tx_date,
                'description': description,
                'amount': amount,
                'category': args.get('category'),
                'vendor': args.get('vendor'),
                'source': 'manual_entry',
                'txn_id': None,
                'reference': None,
                'account': args.get('account'),
                'balance': None,
                'original_hash': row_hash,
                'possible_dup_group': None,
                'row_hash': row_hash,
                'time_part': None
            }
            
            # Insert transaction
            tx_id = self.tx_ops.insert_transaction(transaction_data)
            
            response = f"✅ Transaction added successfully!\n\n"
            response += f"ID: {tx_id}\n"
            response += f"Date: {tx_date}\n"
            response += f"Description: {description}\n"
            response += f"Amount: ${amount:.2f}\n"
            if args.get('category'):
                response += f"Category: {args['category']}\n"
            if args.get('vendor'):
                response += f"Vendor: {args['vendor']}\n"
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error adding transaction: {str(e)}")]
    
    async def _handle_get_categories(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle category listing requests."""
        try:
            # Get categories from database
            categories_query = "SELECT name, description FROM categories WHERE is_active = true ORDER BY sort_order, name"
            categories = self.db.execute_query(categories_query)
            
            if not categories:
                return [TextContent(type="text", text="No categories found.")]
            
            response = "📂 Available Categories:\n\n"
            for cat in categories:
                response += f"• {cat['name']}"
                if cat.get('description'):
                    response += f" - {cat['description']}"
                response += "\n"
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting categories: {str(e)}")]
    
    async def _handle_update_vendor_mapping(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle vendor mapping updates."""
        try:
            vendor_pattern = args['vendor_pattern']
            category = args['category']
            is_regex = args.get('is_regex', False)
            priority = args.get('priority', 0)
            
            # Add vendor mapping
            mapping_id = self.vendor_ops.add_vendor_mapping(
                vendor_pattern=vendor_pattern,
                category=category,
                is_regex=is_regex,
                priority=priority
            )
            
            response = f"✅ Vendor mapping added successfully!\n\n"
            response += f"ID: {mapping_id}\n"
            response += f"Pattern: {vendor_pattern}\n"
            response += f"Category: {category}\n"
            response += f"Regex: {is_regex}\n"
            response += f"Priority: {priority}\n"
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error updating vendor mapping: {str(e)}")]
    
    async def _handle_database_stats(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle database statistics requests."""
        try:
            # Get basic counts
            total_transactions = self.db.get_table_row_count('transactions')
            uncategorized_count = len(self.tx_ops.get_uncategorized_transactions())
            vendor_mappings_count = len(self.vendor_ops.get_vendor_mappings())
            
            # Get date range
            date_range_query = """
            SELECT MIN(date) as earliest, MAX(date) as latest 
            FROM transactions WHERE date IS NOT NULL
            """
            date_range = self.db.execute_query(date_range_query)
            
            # Get category breakdown
            category_query = """
            SELECT category, COUNT(*) as count, SUM(ABS(amount)) as total_amount
            FROM transactions 
            WHERE category IS NOT NULL 
            GROUP BY category 
            ORDER BY count DESC
            """
            category_stats = self.db.execute_query(category_query)
            
            response = "📊 Database Statistics\n\n"
            response += f"📈 Total Transactions: {total_transactions:,}\n"
            response += f"❓ Uncategorized: {uncategorized_count:,}\n"
            response += f"✅ Categorized: {total_transactions - uncategorized_count:,}\n"
            response += f"🏪 Vendor Mappings: {vendor_mappings_count:,}\n\n"
            
            if date_range and date_range[0]['earliest']:
                response += f"📅 Date Range: {date_range[0]['earliest']} to {date_range[0]['latest']}\n\n"
            
            if category_stats:
                response += "📂 Categories:\n"
                for cat in category_stats[:10]:  # Top 10 categories
                    response += f"  • {cat['category']}: {cat['count']} transactions (${float(cat['total_amount']):.2f})\n"
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting database stats: {str(e)}")]
    
    async def run(self):
        """Run the MCP server."""
        logger.info("Starting Bookkeeping MCP Server...")
        
        # Test database connection
        try:
            total_transactions = self.db.get_table_row_count('transactions')
            logger.info(f"Database connection successful. {total_transactions} transactions available.")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
        
        # Start server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="ai-bookkeeping",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities=None,
                    ),
                ),
            )

def main():
    """Main function to run the MCP server."""
    try:
        server = BookkeepingMCPServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise

if __name__ == "__main__":
    main()