"""
Analysis Tools for MCP Server

Provides spending analysis, trend analysis, and financial insights tools.
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class MonthlySummaryParams(BaseModel):
    """Parameters for monthly summary analysis."""
    year: Optional[int] = Field(None, description="Year for summary (defaults to current year)")
    month: Optional[int] = Field(None, description="Month for summary (1-12, defaults to current month)")
    include_comparison: Optional[bool] = Field(False, description="Include comparison with previous month")

class SpendingAnalysisParams(BaseModel):
    """Parameters for spending analysis."""
    period: Optional[str] = Field("month", description="Analysis period: month, quarter, year")
    category_focus: Optional[str] = Field(None, description="Focus analysis on specific category")
    include_trends: Optional[bool] = Field(False, description="Include trend analysis")

class CategoryBreakdownParams(BaseModel):
    """Parameters for category breakdown analysis."""
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    top_n: Optional[int] = Field(10, description="Number of top categories to show")

class VendorAnalysisParams(BaseModel):
    """Parameters for vendor analysis."""
    category: Optional[str] = Field(None, description="Analyze vendors within specific category")
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    top_n: Optional[int] = Field(10, description="Number of top vendors to show")

class AnalysisTools:
    """Analysis and reporting MCP tools."""
    
    def __init__(self, db_manager):
        """Initialize with database manager."""
        self.db_manager = db_manager
        self.tx_ops = db_manager.get_transaction_operations()
        self.db = db_manager.get_core_db()
    
    def monthly_summary(self, params: MonthlySummaryParams) -> str:
        """
        Generate monthly spending summary and analysis.
        
        Provides detailed breakdown of income, expenses, and spending by category
        for a specific month, with optional comparison to previous month.
        """
        try:
            # Default to current month/year if not specified
            current_date = datetime.now()
            year = params.year or current_date.year
            month = params.month or current_date.month
            
            # Calculate date range for the month
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
            
            if not transactions:
                return f"No transactions found for {start_date.strftime('%B %Y')}."
            
            # Calculate summary statistics
            category_totals = {}
            total_income = 0
            total_expenses = 0
            daily_spending = {}
            
            for tx in transactions:
                amount = float(tx['amount'])
                tx_date = tx['date']
                category = tx.get('category', 'Uncategorized')
                
                # Track daily spending
                if tx_date not in daily_spending:
                    daily_spending[tx_date] = 0
                daily_spending[tx_date] += abs(amount) if amount < 0 else 0
                
                if amount > 0:
                    total_income += amount
                    category = 'Income'
                else:
                    total_expenses += abs(amount)
                
                # Aggregate by category
                if category not in category_totals:
                    category_totals[category] = 0
                category_totals[category] += abs(amount)
            
            # Generate response
            month_name = start_date.strftime('%B %Y')
            response = f"📊 Monthly Summary for {month_name}\n\n"
            
            # Financial overview
            net_amount = total_income - total_expenses
            response += f"💰 Income: ${total_income:,.2f}\n"
            response += f"💸 Expenses: ${total_expenses:,.2f}\n"
            response += f"📈 Net: ${net_amount:,.2f}"
            
            if net_amount > 0:
                response += " ✅ (Positive)"
            elif net_amount < 0:
                response += " ⚠️ (Negative)"
            else:
                response += " ➖ (Break-even)"
            
            response += f"\n📅 Transaction Count: {len(transactions)}\n\n"
            
            # Spending breakdown by category (excluding income)
            expense_categories = {k: v for k, v in category_totals.items() if k != 'Income'}
            if expense_categories:
                response += "💳 Spending by Category:\n"
                sorted_categories = sorted(expense_categories.items(), key=lambda x: x[1], reverse=True)
                
                for category, amount in sorted_categories:
                    percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
                    response += f"  • {category}: ${amount:,.2f} ({percentage:.1f}%)\n"
            
            # Daily spending insights
            if daily_spending:
                avg_daily_spending = sum(daily_spending.values()) / len(daily_spending)
                max_spending_day = max(daily_spending.items(), key=lambda x: x[1])
                response += f"\n📅 Daily Spending Insights:\n"
                response += f"  • Average daily spending: ${avg_daily_spending:.2f}\n"
                response += f"  • Highest spending day: {max_spending_day[0]} (${max_spending_day[1]:.2f})\n"
                response += f"  • Active spending days: {len([d for d in daily_spending.values() if d > 0])}\n"
            
            # Include comparison if requested
            if params.include_comparison:
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
                
                if prev_transactions:
                    prev_expenses = sum(abs(float(t['amount'])) for t in prev_transactions if float(t['amount']) < 0)
                    prev_income = sum(float(t['amount']) for t in prev_transactions if float(t['amount']) > 0)
                    
                    expense_change = total_expenses - prev_expenses
                    income_change = total_income - prev_income
                    
                    response += f"\n📈 vs {prev_start.strftime('%B %Y')}:\n"
                    response += f"  • Expense Change: ${expense_change:+,.2f}"
                    if prev_expenses > 0:
                        expense_pct = (expense_change / prev_expenses * 100)
                        response += f" ({expense_pct:+.1f}%)"
                    response += "\n"
                    
                    response += f"  • Income Change: ${income_change:+,.2f}"
                    if prev_income > 0:
                        income_pct = (income_change / prev_income * 100)
                        response += f" ({income_pct:+.1f}%)"
                    response += "\n"
            
            return response
            
        except Exception as e:
            return f"Error generating monthly summary: {str(e)}"
    
    def spending_analysis(self, params: SpendingAnalysisParams) -> str:
        """
        Analyze spending patterns and provide insights.
        
        Provides comprehensive analysis of spending patterns over different periods,
        with optional focus on specific categories and trend analysis.
        """
        try:
            # Determine date range based on period
            today = date.today()
            
            if params.period == "month":
                start_date = today.replace(day=1)
                period_name = "This Month"
            elif params.period == "quarter":
                quarter_start_month = ((today.month - 1) // 3) * 3 + 1
                start_date = today.replace(month=quarter_start_month, day=1)
                period_name = "This Quarter"
            elif params.period == "year":
                start_date = today.replace(month=1, day=1)
                period_name = "This Year"
            else:
                return "Invalid period. Use 'month', 'quarter', or 'year'."
            
            end_date = today
            
            # Get transactions for the period
            transactions = self.tx_ops.get_transactions(
                start_date=start_date,
                end_date=end_date,
                category=params.category_focus
            )
            
            if not transactions:
                return f"No transactions found for {period_name.lower()}."
            
            if params.category_focus:
                # Category-focused analysis
                category_transactions = [t for t in transactions if t.get('category') == params.category_focus]
                total_spent = sum(abs(float(t['amount'])) for t in category_transactions if float(t['amount']) < 0)
                avg_transaction = total_spent / len(category_transactions) if category_transactions else 0
                
                # Analyze vendors within category
                vendor_totals = {}
                for tx in category_transactions:
                    if float(tx['amount']) < 0:  # Only expenses
                        vendor = tx.get('vendor') or tx['description'][:30].strip()
                        amount = abs(float(tx['amount']))
                        vendor_totals[vendor] = vendor_totals.get(vendor, 0) + amount
                
                response = f"🔍 {params.category_focus} Analysis ({period_name})\n\n"
                response += f"💸 Total Spent: ${total_spent:,.2f}\n"
                response += f"📊 Transactions: {len(category_transactions)}\n"
                response += f"📈 Average per transaction: ${avg_transaction:.2f}\n\n"
                
                if vendor_totals:
                    response += "🏪 Top Vendors/Merchants:\n"
                    sorted_vendors = sorted(vendor_totals.items(), key=lambda x: x[1], reverse=True)[:5]
                    for vendor, amount in sorted_vendors:
                        percentage = (amount / total_spent * 100) if total_spent > 0 else 0
                        response += f"  • {vendor}: ${amount:,.2f} ({percentage:.1f}%)\n"
                
            else:
                # General spending analysis
                category_totals = {}
                daily_totals = {}
                weekly_totals = {}
                
                for tx in transactions:
                    amount = float(tx['amount'])
                    if amount < 0:  # Only expenses for spending analysis
                        amount = abs(amount)
                        category = tx.get('category', 'Uncategorized')
                        tx_date = tx['date']
                        
                        # Category totals
                        category_totals[category] = category_totals.get(category, 0) + amount
                        
                        # Daily totals
                        daily_totals[tx_date] = daily_totals.get(tx_date, 0) + amount
                        
                        # Weekly totals (ISO week)
                        week_key = tx_date.isocalendar()[:2]  # (year, week)
                        weekly_totals[week_key] = weekly_totals.get(week_key, 0) + amount
                
                total_expenses = sum(category_totals.values())
                avg_daily = total_expenses / len(daily_totals) if daily_totals else 0
                avg_weekly = total_expenses / len(weekly_totals) if weekly_totals else 0
                
                response = f"📊 Spending Analysis ({period_name})\n\n"
                response += f"💸 Total Expenses: ${total_expenses:,.2f}\n"
                response += f"📅 Average Daily: ${avg_daily:.2f}\n"
                response += f"📆 Average Weekly: ${avg_weekly:.2f}\n"
                response += f"📈 Active Days: {len(daily_totals)}\n\n"
                
                response += "📂 Spending by Category:\n"
                sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
                for category, amount in sorted_categories:
                    percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
                    response += f"  • {category}: ${amount:,.2f} ({percentage:.1f}%)\n"
                
                # Add trend insights if requested
                if params.include_trends and len(weekly_totals) > 1:
                    weekly_amounts = list(weekly_totals.values())
                    recent_avg = sum(weekly_amounts[-2:]) / min(2, len(weekly_amounts))
                    overall_avg = sum(weekly_amounts) / len(weekly_amounts)
                    
                    response += f"\n📈 Trend Insights:\n"
                    if recent_avg > overall_avg * 1.1:
                        response += f"  • Spending trending upward (recent: ${recent_avg:.2f}/week vs avg: ${overall_avg:.2f}/week)\n"
                    elif recent_avg < overall_avg * 0.9:
                        response += f"  • Spending trending downward (recent: ${recent_avg:.2f}/week vs avg: ${overall_avg:.2f}/week)\n"
                    else:
                        response += f"  • Spending relatively stable (${overall_avg:.2f}/week average)\n"
            
            return response
            
        except Exception as e:
            return f"Error analyzing spending: {str(e)}"
    
    def category_breakdown(self, params: CategoryBreakdownParams) -> str:
        """
        Get detailed breakdown of spending by category.
        
        Provides comprehensive analysis of how money is distributed across
        different spending categories over a specified time period.
        """
        try:
            # Parse date parameters
            start_date_obj = None
            end_date_obj = None
            
            if params.start_date:
                start_date_obj = datetime.strptime(params.start_date, '%Y-%m-%d').date()
            if params.end_date:
                end_date_obj = datetime.strptime(params.end_date, '%Y-%m-%d').date()
            
            # Default to current month if no dates specified
            if not start_date_obj and not end_date_obj:
                today = date.today()
                start_date_obj = today.replace(day=1)
                end_date_obj = today
            
            # Get transactions
            transactions = self.tx_ops.get_transactions(
                start_date=start_date_obj,
                end_date=end_date_obj
            )
            
            if not transactions:
                period_str = f"from {start_date_obj} to {end_date_obj}" if start_date_obj and end_date_obj else "in the specified period"
                return f"No transactions found {period_str}."
            
            # Analyze by category
            category_stats = {}
            total_income = 0
            total_expenses = 0
            
            for tx in transactions:
                amount = float(tx['amount'])
                category = tx.get('category', 'Uncategorized')
                
                if amount > 0:
                    total_income += amount
                    category = 'Income'
                else:
                    total_expenses += abs(amount)
                
                if category not in category_stats:
                    category_stats[category] = {
                        'total': 0,
                        'count': 0,
                        'min': float('inf'),
                        'max': float('-inf')
                    }
                
                abs_amount = abs(amount)
                category_stats[category]['total'] += abs_amount
                category_stats[category]['count'] += 1
                category_stats[category]['min'] = min(category_stats[category]['min'], abs_amount)
                category_stats[category]['max'] = max(category_stats[category]['max'], abs_amount)
            
            # Format response
            period_str = f"from {start_date_obj} to {end_date_obj}" if start_date_obj and end_date_obj else "in specified period"
            response = f"📂 Category Breakdown ({period_str})\n\n"
            
            response += f"💰 Income: ${total_income:,.2f}\n"
            response += f"💸 Expenses: ${total_expenses:,.2f}\n"
            response += f"📈 Net: ${total_income - total_expenses:,.2f}\n\n"
            
            # Sort categories by total amount (excluding income)
            expense_categories = {k: v for k, v in category_stats.items() if k != 'Income'}
            sorted_categories = sorted(expense_categories.items(), key=lambda x: x[1]['total'], reverse=True)
            
            response += f"📊 Top {min(params.top_n, len(sorted_categories))} Expense Categories:\n"
            
            for i, (category, stats) in enumerate(sorted_categories[:params.top_n], 1):
                percentage = (stats['total'] / total_expenses * 100) if total_expenses > 0 else 0
                avg_amount = stats['total'] / stats['count']
                
                response += f"\n{i}. {category}\n"
                response += f"   💰 Total: ${stats['total']:,.2f} ({percentage:.1f}%)\n"
                response += f"   📊 Transactions: {stats['count']}\n"
                response += f"   📈 Average: ${avg_amount:.2f}\n"
                response += f"   📉 Range: ${stats['min']:.2f} - ${stats['max']:.2f}\n"
            
            return response
            
        except Exception as e:
            return f"Error generating category breakdown: {str(e)}"
    
    def vendor_analysis(self, params: VendorAnalysisParams) -> str:
        """
        Analyze spending patterns by vendor/merchant.
        
        Provides insights into which vendors/merchants you spend the most with,
        optionally filtered by category and date range.
        """
        try:
            # Parse date parameters
            start_date_obj = None
            end_date_obj = None
            
            if params.start_date:
                start_date_obj = datetime.strptime(params.start_date, '%Y-%m-%d').date()
            if params.end_date:
                end_date_obj = datetime.strptime(params.end_date, '%Y-%m-%d').date()
            
            # Get transactions
            transactions = self.tx_ops.get_transactions(
                start_date=start_date_obj,
                end_date=end_date_obj,
                category=params.category
            )
            
            if not transactions:
                return "No transactions found for the specified criteria."
            
            # Analyze by vendor
            vendor_stats = {}
            total_analyzed = 0
            
            for tx in transactions:
                amount = float(tx['amount'])
                if amount >= 0:  # Skip income transactions
                    continue
                
                amount = abs(amount)
                total_analyzed += amount
                
                # Use vendor if available, otherwise use description
                vendor = tx.get('vendor') or tx['description'][:40].strip()
                
                if vendor not in vendor_stats:
                    vendor_stats[vendor] = {
                        'total': 0,
                        'count': 0,
                        'avg': 0,
                        'category': tx.get('category', 'Uncategorized')
                    }
                
                vendor_stats[vendor]['total'] += amount
                vendor_stats[vendor]['count'] += 1
                vendor_stats[vendor]['avg'] = vendor_stats[vendor]['total'] / vendor_stats[vendor]['count']
            
            if not vendor_stats:
                return "No expense transactions found for analysis."
            
            # Format response
            period_str = ""
            if start_date_obj and end_date_obj:
                period_str = f" from {start_date_obj} to {end_date_obj}"
            elif params.category:
                period_str = f" in {params.category} category"
            
            response = f"🏪 Vendor Analysis{period_str}\n\n"
            response += f"💸 Total Analyzed: ${total_analyzed:,.2f}\n"
            response += f"🏢 Unique Vendors: {len(vendor_stats)}\n\n"
            
            # Sort vendors by total spending
            sorted_vendors = sorted(vendor_stats.items(), key=lambda x: x[1]['total'], reverse=True)
            
            response += f"📊 Top {min(params.top_n, len(sorted_vendors))} Vendors:\n"
            
            for i, (vendor, stats) in enumerate(sorted_vendors[:params.top_n], 1):
                percentage = (stats['total'] / total_analyzed * 100) if total_analyzed > 0 else 0
                
                response += f"\n{i}. {vendor}\n"
                response += f"   💰 Total: ${stats['total']:,.2f} ({percentage:.1f}%)\n"
                response += f"   📊 Transactions: {stats['count']}\n"
                response += f"   📈 Average: ${stats['avg']:.2f}\n"
                response += f"   📂 Category: {stats['category']}\n"
            
            return response
            
        except Exception as e:
            return f"Error analyzing vendors: {str(e)}"