"""
Management Tools for MCP Server

Provides database management, configuration, and maintenance tools.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class UpdateVendorMappingParams(BaseModel):
    """Parameters for updating vendor mappings."""
    vendor_pattern: str = Field(..., description="Vendor name pattern to match")
    category: str = Field(..., description="Category to assign")
    is_regex: Optional[bool] = Field(False, description="Whether pattern is regex")
    priority: Optional[int] = Field(0, description="Rule priority (higher = more important)")

class StageDuplicatesParams(BaseModel):
    """Parameters for staging duplicate transactions for review."""
    days_back: Optional[int] = Field(30, description="Look for duplicates in last N days")
    amount_tolerance: Optional[float] = Field(0.01, description="Amount difference tolerance")
    auto_stage: Optional[bool] = Field(True, description="Automatically stage high-confidence duplicates")

class ReviewDuplicateParams(BaseModel):
    """Parameters for reviewing a duplicate transaction pair."""
    group_id: str = Field(..., description="Duplicate group ID to review")
    action: str = Field(..., description="Action to take: 'keep_both', 'delete_duplicate', 'merge', or 'ignore'")
    keep_transaction_id: Optional[int] = Field(None, description="Which transaction to keep (required for delete_duplicate)")
    notes: Optional[str] = Field("", description="Notes about the decision")

class DeleteTransactionParams(BaseModel):
    """Parameters for deleting a transaction."""
    transaction_id: int = Field(..., description="ID of transaction to delete")
    reason: str = Field(..., description="Reason for deletion (e.g., 'duplicate', 'error', 'test')")
    permanent: Optional[bool] = Field(False, description="Permanently delete vs soft delete")

class ManagementTools:
    """Database and system management MCP tools."""
    
    def __init__(self, db_manager):
        """Initialize with database manager."""
        self.db_manager = db_manager
        self.vendor_ops = db_manager.get_vendor_operations()
        self.db = db_manager.get_core_db()
    
    def get_categories(self) -> str:
        """
        Get all available spending categories.
        
        Returns a list of all categories that can be used for transaction categorization,
        including their descriptions and current usage statistics.
        """
        try:
            # Get categories from database
            categories_query = """
            SELECT c.name, c.description, c.sort_order,
                   COUNT(t.id) as transaction_count,
                   COALESCE(SUM(ABS(t.amount)), 0) as total_amount
            FROM categories c
            LEFT JOIN transactions t ON c.name = t.category
            WHERE c.is_active = true
            GROUP BY c.id, c.name, c.description, c.sort_order
            ORDER BY c.sort_order, c.name
            """
            categories = self.db.execute_query(categories_query)
            
            if not categories:
                return "No categories found in the database."
            
            response = "📂 Available Categories:\n\n"
            
            total_transactions = sum(cat['transaction_count'] for cat in categories)
            total_amount = sum(float(cat['total_amount']) for cat in categories)
            
            for cat in categories:
                response += f"• **{cat['name']}**"
                if cat.get('description'):
                    response += f" - {cat['description']}"
                
                tx_count = cat['transaction_count']
                amount = float(cat['total_amount'])
                
                if tx_count > 0:
                    response += f"\n  📊 {tx_count:,} transactions | ${amount:,.2f}"
                    if total_transactions > 0:
                        percentage = (tx_count / total_transactions * 100)
                        response += f" ({percentage:.1f}%)"
                else:
                    response += "\n  📊 No transactions yet"
                
                response += "\n\n"
            
            response += f"📈 Summary: {len(categories)} categories | {total_transactions:,} total transactions | ${total_amount:,.2f} total amount"
            
            return response
            
        except Exception as e:
            return f"Error getting categories: {str(e)}"
    
    def update_vendor_mapping(self, params: UpdateVendorMappingParams) -> str:
        """
        Add or update vendor mapping rule for automatic categorization.
        
        Creates rules that automatically assign categories to transactions based on
        vendor names or description patterns. Helps automate future categorization.
        """
        try:
            # Validate category exists
            valid_categories_query = "SELECT name FROM categories WHERE is_active = true"
            valid_categories = self.db.execute_query(valid_categories_query)
            valid_category_names = [cat['name'] for cat in valid_categories]
            
            if params.category not in valid_category_names:
                return f"Error: '{params.category}' is not a valid category.\n\nValid categories: {', '.join(valid_category_names)}"
            
            # Check if similar mapping already exists
            existing_mappings = self.vendor_ops.get_vendor_mappings()
            similar_mappings = [
                m for m in existing_mappings 
                if m['vendor_pattern'].lower() == params.vendor_pattern.lower()
            ]
            
            if similar_mappings:
                existing = similar_mappings[0]
                return f"⚠️ Similar mapping already exists:\n\nPattern: '{existing['vendor_pattern']}'\nCategory: {existing['category']}\nPriority: {existing['priority']}\n\nPlease modify the existing rule or use a different pattern."
            
            # Add vendor mapping
            mapping_id = self.vendor_ops.add_vendor_mapping(
                vendor_pattern=params.vendor_pattern,
                category=params.category,
                is_regex=params.is_regex,
                priority=params.priority
            )
            
            response = f"✅ Vendor mapping added successfully!\n\n"
            response += f"🆔 Mapping ID: {mapping_id}\n"
            response += f"🏪 Pattern: '{params.vendor_pattern}'\n"
            response += f"📂 Category: {params.category}\n"
            response += f"🔤 Regex: {'Yes' if params.is_regex else 'No'}\n"
            response += f"⚡ Priority: {params.priority}\n\n"
            
            response += "💡 This rule will automatically categorize future transactions that match the pattern.\n"
            response += "To apply to existing transactions, run the AI categorization process."
            
            return response
            
        except Exception as e:
            return f"Error updating vendor mapping: {str(e)}"
    
    def get_vendor_mappings(self) -> str:
        """
        Get all vendor mapping rules.
        
        Returns a list of all automatic categorization rules currently configured,
        showing their patterns, categories, and priorities.
        """
        try:
            mappings = self.vendor_ops.get_vendor_mappings()
            
            if not mappings:
                return "No vendor mapping rules found.\n\nUse 'update_vendor_mapping' to create automatic categorization rules."
            
            response = f"🏪 Vendor Mapping Rules ({len(mappings)} total):\n\n"
            
            # Group by priority for better organization
            priority_groups = {}
            for mapping in mappings:
                priority = mapping['priority']
                if priority not in priority_groups:
                    priority_groups[priority] = []
                priority_groups[priority].append(mapping)
            
            # Sort by priority (highest first)
            for priority in sorted(priority_groups.keys(), reverse=True):
                if priority > 0:
                    response += f"⚡ Priority {priority}:\n"
                elif priority == 0:
                    response += f"📋 Standard Priority:\n"
                else:
                    response += f"🔽 Low Priority ({priority}):\n"
                
                for mapping in priority_groups[priority]:
                    response += f"  • '{mapping['vendor_pattern']}' → {mapping['category']}"
                    if mapping['is_regex']:
                        response += " (regex)"
                    response += f" [ID: {mapping['id']}]\n"
                
                response += "\n"
            
            response += "💡 Rules are applied in priority order (highest first).\n"
            response += "💡 Use 'update_vendor_mapping' to add new rules."
            
            return response
            
        except Exception as e:
            return f"Error getting vendor mappings: {str(e)}"
    
    def database_stats(self) -> str:
        """
        Get database statistics and health information.
        
        Provides comprehensive overview of database status, including transaction counts,
        categorization progress, date ranges, and system health.
        """
        try:
            # Get database health information
            health = self.db_manager.get_database_health()
            
            if not health.get('connected'):
                return f"❌ Database connection failed: {health.get('error', 'Unknown error')}"
            
            response = "📊 Database Statistics & Health Report\n\n"
            
            # Connection info
            response += "🔗 Connection Status:\n"
            response += f"  ✅ Connected to PostgreSQL\n"
            if 'postgres_version' in health:
                response += f"  📍 Version: {health['postgres_version']}\n"
            response += "\n"
            
            # Table status
            if 'tables_exist' in health:
                response += "🗃️ Database Schema:\n"
                tables = health['tables_exist']
                for table, exists in tables.items():
                    status = "✅" if exists else "❌"
                    response += f"  {status} {table}\n"
                response += "\n"
            
            # Transaction statistics
            response += "📈 Transaction Statistics:\n"
            response += f"  📊 Total Transactions: {health.get('total_transactions', 0):,}\n"
            
            categorized_count = health['total_transactions'] - health.get('uncategorized_transactions', 0)
            response += f"  ✅ Categorized: {categorized_count:,}\n"
            response += f"  ❓ Uncategorized: {health.get('uncategorized_transactions', 0):,}\n"
            
            if health['total_transactions'] > 0:
                categorized_pct = (categorized_count / health['total_transactions'] * 100)
                response += f"  📊 Categorization Rate: {categorized_pct:.1f}%\n"
            
            response += "\n"
            
            # Date range information
            if health.get('date_range'):
                date_info = health['date_range']
                response += "📅 Data Coverage:\n"
                response += f"  📅 Earliest Transaction: {date_info.get('earliest', 'N/A')}\n"
                response += f"  📅 Latest Transaction: {date_info.get('latest', 'N/A')}\n"
                
                if date_info.get('earliest') and date_info.get('latest'):
                    from datetime import datetime
                    try:
                        earliest = datetime.strptime(str(date_info['earliest']), '%Y-%m-%d').date()
                        latest = datetime.strptime(str(date_info['latest']), '%Y-%m-%d').date()
                        days_span = (latest - earliest).days
                        response += f"  📊 Data Span: {days_span} days\n"
                    except:
                        pass
                
                response += "\n"
            
            # Category and mapping statistics
            response += "📂 Configuration:\n"
            response += f"  📂 Categories: {health.get('total_categories', 0)}\n"
            response += f"  🏪 Vendor Mappings: {health.get('total_vendor_mappings', 0)}\n"
            response += "\n"
            
            # Recent activity
            try:
                recent_query = """
                SELECT COUNT(*) as count
                FROM transactions 
                WHERE created_at >= NOW() - INTERVAL '7 days'
                """
                recent_result = self.db.execute_query(recent_query)
                recent_count = recent_result[0]['count'] if recent_result else 0
                
                response += "🕐 Recent Activity:\n"
                response += f"  📊 Transactions added (last 7 days): {recent_count}\n"
                response += "\n"
            except:
                pass
            
            # Health indicators
            response += "🏥 Health Indicators:\n"
            
            if health['total_transactions'] == 0:
                response += "  ⚠️ No transactions in database\n"
            elif health.get('uncategorized_transactions', 0) > health['total_transactions'] * 0.5:
                response += "  ⚠️ High number of uncategorized transactions\n"
            else:
                response += "  ✅ Good categorization coverage\n"
            
            if health.get('total_vendor_mappings', 0) == 0:
                response += "  💡 Consider adding vendor mapping rules for automation\n"
            else:
                response += "  ✅ Vendor mapping rules configured\n"
            
            return response
            
        except Exception as e:
            return f"Error getting database stats: {str(e)}"
    
    def stage_duplicates_for_review(self, params: StageDuplicatesParams) -> str:
        """
        Stage potential duplicate transactions for manual review.
        
        This replaces the Excel 'Dup Review' sheet functionality by identifying 
        potential duplicates and staging them in the duplicate_review table.
        """
        try:
            from datetime import datetime, timedelta
            
            # Clear previous duplicate reviews if requested
            self.db.execute_query("DELETE FROM duplicate_review WHERE reviewed = false")
            
            # Get recent transactions for duplicate analysis
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=params.days_back)
            
            transactions_query = """
            SELECT id, date, description, amount, vendor, account, txn_id, reference
            FROM transactions 
            WHERE date >= %s AND date <= %s 
            AND deleted_at IS NULL
            ORDER BY date DESC, amount
            """
            transactions = self.db.execute_query(transactions_query, [start_date, end_date])
            
            if len(transactions) < 2:
                return f"Only {len(transactions)} transactions found in the last {params.days_back} days. Need at least 2 to find duplicates."
            
            # Find potential duplicates using similar logic to original
            duplicate_groups = []
            processed_pairs = set()
            
            for i, tx1 in enumerate(transactions):
                for j, tx2 in enumerate(transactions[i+1:], i+1):
                    # Skip if already processed this pair
                    pair_key = tuple(sorted([tx1['id'], tx2['id']]))
                    if pair_key in processed_pairs:
                        continue
                    
                    # Check if they're potential duplicates
                    date_diff = abs((tx1['date'] - tx2['date']).days) if tx1['date'] != tx2['date'] else 0
                    amount_diff = abs(float(tx1['amount']) - float(tx2['amount']))
                    description_match = tx1['description'].lower() == tx2['description'].lower()
                    
                    # Various duplicate criteria
                    is_duplicate = False
                    similarity_score = 0.0
                    reason = ""
                    
                    # Exact match (highest confidence)
                    if (tx1['txn_id'] and tx2['txn_id'] and 
                        tx1['txn_id'] == tx2['txn_id'] and 
                        tx1['account'] == tx2['account']):
                        is_duplicate = True
                        similarity_score = 1.0
                        reason = "Same TxnId and Account"
                    
                    # Reference + Date + Amount match
                    elif (tx1['reference'] and tx2['reference'] and 
                          tx1['reference'] == tx2['reference'] and 
                          date_diff <= 1 and amount_diff <= params.amount_tolerance):
                        is_duplicate = True
                        similarity_score = 0.95
                        reason = "Same Reference, Date, and Amount"
                    
                    # Description + Amount + Close Date
                    elif (description_match and 
                          amount_diff <= params.amount_tolerance and 
                          date_diff <= 3):
                        is_duplicate = True
                        similarity_score = 0.85 if date_diff == 0 else 0.75
                        reason = f"Same Description and Amount, {date_diff} days apart"
                    
                    # Vendor + Amount + Close Date (for cleaned up vendors)
                    elif (tx1.get('vendor') and tx2.get('vendor') and
                          tx1['vendor'].lower() == tx2['vendor'].lower() and
                          amount_diff <= params.amount_tolerance and
                          date_diff <= 2):
                        is_duplicate = True
                        similarity_score = 0.80
                        reason = f"Same Vendor and Amount, {date_diff} days apart"
                    
                    if is_duplicate:
                        group_id = f"DUP_{len(duplicate_groups)+1:04d}"
                        duplicate_groups.append({
                            'group_id': group_id,
                            'transactions': [tx1, tx2],
                            'similarity_score': similarity_score,
                            'reason': reason
                        })
                        processed_pairs.add(pair_key)
                        
                        # If auto-staging high confidence duplicates
                        if params.auto_stage and similarity_score >= 0.9:
                            self._stage_duplicate_group(group_id, [tx1, tx2], similarity_score, f"Auto-staged: {reason}")
            
            if not duplicate_groups:
                return f"No potential duplicates found in the last {params.days_back} days.\n\nAnalyzed {len(transactions)} transactions using criteria:\n- Amount tolerance: ${params.amount_tolerance:.2f}\n- Date range: {params.days_back} days"
            
            # Stage all groups for review
            staged_count = 0
            for group in duplicate_groups:
                if not params.auto_stage or group['similarity_score'] < 0.9:
                    self._stage_duplicate_group(
                        group['group_id'], 
                        group['transactions'], 
                        group['similarity_score'],
                        group['reason']
                    )
                    staged_count += 1
            
            response = f"🔍 Found {len(duplicate_groups)} potential duplicate groups:\n\n"
            
            # Show summary of groups
            for group in duplicate_groups[:10]:  # Show first 10
                tx1, tx2 = group['transactions']
                response += f"**{group['group_id']}** (Score: {group['similarity_score']:.0%})\n"
                response += f"  • Transaction {tx1['id']}: {tx1['date']} | ${tx1['amount']:.2f} | {tx1['description'][:50]}\n"
                response += f"  • Transaction {tx2['id']}: {tx2['date']} | ${tx2['amount']:.2f} | {tx2['description'][:50]}\n"
                response += f"  • Reason: {group['reason']}\n\n"
            
            if len(duplicate_groups) > 10:
                response += f"... and {len(duplicate_groups) - 10} more groups.\n\n"
            
            if params.auto_stage:
                auto_staged = len(duplicate_groups) - staged_count
                if auto_staged > 0:
                    response += f"✅ Auto-staged {auto_staged} high-confidence duplicates\n"
            
            response += f"📋 Staged {staged_count} groups for manual review\n"
            response += "💡 Use 'get_duplicate_review_queue' to see pending reviews\n"
            response += "💡 Use 'review_duplicate' to make decisions on each group"
            
            return response
            
        except Exception as e:
            return f"Error staging duplicates: {str(e)}"
    
    def _stage_duplicate_group(self, group_id: str, transactions: List[Dict], similarity_score: float, reason: str):
        """Helper method to stage a duplicate group for review."""
        for tx in transactions:
            insert_query = """
            INSERT INTO duplicate_review 
            (group_id, transaction_id, similarity_score, notes, reviewed, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """
            self.db.execute_query(insert_query, [
                group_id, 
                tx['id'], 
                similarity_score, 
                reason,
                False
            ])
    
    def get_duplicate_review_queue(self) -> str:
        """
        Get pending duplicate reviews (replaces Excel Dup Review sheet).
        
        Shows all duplicate groups that need manual review decisions.
        """
        try:
            # Get pending reviews grouped by group_id
            review_query = """
            SELECT dr.group_id, dr.similarity_score, dr.notes, dr.created_at,
                   t.id, t.date, t.description, t.amount, t.vendor, t.account, t.category
            FROM duplicate_review dr
            JOIN transactions t ON dr.transaction_id = t.id
            WHERE dr.reviewed = false
            ORDER BY dr.group_id, t.date
            """
            reviews = self.db.execute_query(review_query)
            
            if not reviews:
                return "📋 No pending duplicate reviews!\n\n💡 Use 'stage_duplicates_for_review' to find new potential duplicates."
            
            # Group by group_id
            groups = {}
            for review in reviews:
                group_id = review['group_id']
                if group_id not in groups:
                    groups[group_id] = {
                        'similarity_score': review['similarity_score'],
                        'reason': review['notes'],
                        'created_at': review['created_at'],
                        'transactions': []
                    }
                groups[group_id]['transactions'].append(review)
            
            response = f"📋 Duplicate Review Queue ({len(groups)} groups pending):\n\n"
            
            for group_id, group_data in groups.items():
                response += f"**{group_id}** (Score: {group_data['similarity_score']:.0%})\n"
                response += f"Reason: {group_data['reason']}\n"
                response += f"Found: {group_data['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
                
                for i, tx in enumerate(group_data['transactions'], 1):
                    response += f"  {i}. **Transaction {tx['id']}**\n"
                    response += f"     Date: {tx['date']}\n"
                    response += f"     Amount: ${tx['amount']:.2f}\n"
                    response += f"     Description: {tx['description']}\n"
                    response += f"     Vendor: {tx.get('vendor', 'N/A')}\n"
                    response += f"     Account: {tx['account']}\n"
                    response += f"     Category: {tx.get('category', 'Uncategorized')}\n\n"
                
                response += "---\n\n"
            
            response += "🎯 **Next Steps:**\n"
            response += "• Use 'review_duplicate' to make decisions on each group\n"
            response += "• Actions available: 'keep_both', 'delete_duplicate', 'merge', 'ignore'\n"
            response += "• Example: review_duplicate(group_id='DUP_0001', action='delete_duplicate', keep_transaction_id=123)"
            
            return response
            
        except Exception as e:
            return f"Error getting duplicate review queue: {str(e)}"
    
    def review_duplicate(self, params: ReviewDuplicateParams) -> str:
        """
        Review and take action on a duplicate group (replaces Excel manual decisions).
        
        This is equivalent to setting the 'Decision' column in the Excel Dup Review sheet.
        """
        try:
            # Get the duplicate group
            group_query = """
            SELECT dr.transaction_id, dr.similarity_score, dr.notes,
                   t.date, t.description, t.amount, t.vendor, t.account
            FROM duplicate_review dr
            JOIN transactions t ON dr.transaction_id = t.id
            WHERE dr.group_id = %s AND dr.reviewed = false
            ORDER BY t.date
            """
            group_transactions = self.db.execute_query(group_query, [params.group_id])
            
            if not group_transactions:
                return f"No pending review found for group '{params.group_id}'. It may have already been reviewed or doesn't exist."
            
            if len(group_transactions) < 2:
                return f"Group '{params.group_id}' has only {len(group_transactions)} transaction(s). Duplicate groups should have at least 2."
            
            # Validate action
            valid_actions = ['keep_both', 'delete_duplicate', 'merge', 'ignore']
            if params.action not in valid_actions:
                return f"Invalid action '{params.action}'. Valid actions: {', '.join(valid_actions)}"
            
            # Process the action
            action_result = ""
            
            if params.action == 'keep_both':
                # Mark as reviewed but take no action
                action_result = f"✅ Keeping both transactions - marked as not duplicates"
                
            elif params.action == 'delete_duplicate':
                if not params.keep_transaction_id:
                    return "Error: 'keep_transaction_id' is required when action is 'delete_duplicate'"
                
                # Validate the transaction ID is in this group
                group_tx_ids = [tx['transaction_id'] for tx in group_transactions]
                if params.keep_transaction_id not in group_tx_ids:
                    return f"Error: Transaction ID {params.keep_transaction_id} is not in group '{params.group_id}'. Available IDs: {group_tx_ids}"
                
                # Soft delete the other transaction(s)
                for tx in group_transactions:
                    if tx['transaction_id'] != params.keep_transaction_id:
                        delete_query = """
                        UPDATE transactions 
                        SET deleted_at = NOW(), 
                            deletion_reason = %s,
                            notes = COALESCE(notes || '; ', '') || %s
                        WHERE id = %s
                        """
                        self.db.execute_query(delete_query, [
                            'duplicate_review', 
                            f"Duplicate of transaction {params.keep_transaction_id}",
                            tx['transaction_id']
                        ])
                
                action_result = f"🗑️ Soft-deleted duplicate(s), kept transaction {params.keep_transaction_id}"
                
            elif params.action == 'merge':
                # For now, mark as needing manual merge - could implement automatic merging later
                action_result = f"📎 Marked for merge - manual intervention required"
                
            elif params.action == 'ignore':
                action_result = f"👁️ Ignored - marked as false positive"
            
            # Mark the review as completed
            update_query = """
            UPDATE duplicate_review 
            SET reviewed = true, 
                action_taken = %s,
                reviewed_by = 'mcp_user',
                reviewed_at = NOW(),
                notes = COALESCE(notes || '; ', '') || %s
            WHERE group_id = %s
            """
            self.db.execute_query(update_query, [
                params.action,
                f"User decision: {params.notes}" if params.notes else f"Action: {params.action}",
                params.group_id
            ])
            
            # Log the action
            log_query = """
            INSERT INTO processing_log (operation_type, source_file, records_processed, status, notes)
            VALUES ('duplicate_review', %s, %s, 'completed', %s)
            """
            self.db.execute_query(log_query, [
                f"group_{params.group_id}",
                len(group_transactions),
                f"Action: {params.action}; {action_result}"
            ])
            
            response = f"✅ Reviewed duplicate group '{params.group_id}'\n\n"
            response += f"**Action taken:** {params.action}\n"
            response += f"**Result:** {action_result}\n"
            
            if params.notes:
                response += f"**Notes:** {params.notes}\n"
            
            response += f"\n**Group contained {len(group_transactions)} transactions:**\n"
            for tx in group_transactions:
                status = "KEPT" if (params.action != 'delete_duplicate' or 
                                 tx['transaction_id'] == params.keep_transaction_id) else "DELETED"
                response += f"• Transaction {tx['transaction_id']} ({status}): {tx['date']} | ${tx['amount']:.2f} | {tx['description'][:50]}\n"
            
            return response
            
        except Exception as e:
            return f"Error reviewing duplicate: {str(e)}"
    
    def delete_transaction(self, params: DeleteTransactionParams) -> str:
        """
        Delete a transaction (soft delete by default, with audit trail).
        
        This replaces moving rows to 'Deleted Rows' sheet in Excel.
        """
        try:
            # Get transaction details first
            tx_query = "SELECT * FROM transactions WHERE id = %s AND deleted_at IS NULL"
            transaction = self.db.execute_query(tx_query, [params.transaction_id])
            
            if not transaction:
                return f"Transaction {params.transaction_id} not found or already deleted."
            
            tx = transaction[0]
            
            if params.permanent:
                # Permanent deletion (use with caution)
                delete_query = "DELETE FROM transactions WHERE id = %s"
                self.db.execute_query(delete_query, [params.transaction_id])
                action = "permanently deleted"
            else:
                # Soft delete (recommended)
                update_query = """
                UPDATE transactions 
                SET deleted_at = NOW(), 
                    deletion_reason = %s,
                    notes = COALESCE(notes || '; ', '') || %s
                WHERE id = %s
                """
                self.db.execute_query(update_query, [
                    params.reason,
                    f"Deleted via MCP: {params.reason}",
                    params.transaction_id
                ])
                action = "soft deleted"
            
            # Log the deletion
            log_query = """
            INSERT INTO processing_log (operation_type, source_file, records_processed, status, notes)
            VALUES ('transaction_deletion', %s, 1, 'completed', %s)
            """
            self.db.execute_query(log_query, [
                f"transaction_{params.transaction_id}",
                f"Reason: {params.reason}; Permanent: {params.permanent}"
            ])
            
            response = f"✅ Transaction {params.transaction_id} {action}\n\n"
            response += f"**Deleted transaction details:**\n"
            response += f"• Date: {tx['date']}\n"
            response += f"• Amount: ${tx['amount']:.2f}\n"
            response += f"• Description: {tx['description']}\n"
            response += f"• Account: {tx['account']}\n"
            response += f"• Reason: {params.reason}\n"
            
            if not params.permanent:
                response += f"\n💡 This was a soft delete. The transaction is hidden but can be restored if needed."
            else:
                response += f"\n⚠️ This was a permanent deletion. The transaction cannot be recovered."
            
            return response
            
        except Exception as e:
            return f"Error deleting transaction: {str(e)}"
    
    def get_uncategorized_transactions(self) -> str:
        """
        Get transactions that need category review (replaces Excel categorization workflow).
        
        Shows uncategorized transactions that need manual review and categorization.
        """
        try:
            # Get uncategorized transactions
            query = """
            SELECT id, date, description, amount, vendor, account, notes
            FROM transactions 
            WHERE (category IS NULL OR category = '' OR category = 'Uncategorized')
            AND deleted_at IS NULL
            ORDER BY date DESC
            LIMIT 50
            """
            transactions = self.db.execute_query(query)
            
            if not transactions:
                return "🎉 All transactions are categorized!\n\nNo uncategorized transactions found."
            
            response = f"📋 Uncategorized Transactions ({len(transactions)} found):\n\n"
            
            for tx in transactions:
                response += f"**Transaction {tx['id']}**\n"
                response += f"• Date: {tx['date']}\n"
                response += f"• Amount: ${tx['amount']:.2f}\n"
                response += f"• Description: {tx['description']}\n"
                response += f"• Vendor: {tx.get('vendor', 'N/A')}\n"
                response += f"• Account: {tx['account']}\n"
                if tx.get('notes'):
                    response += f"• Notes: {tx['notes']}\n"
                response += "\n"
            
            if len(transactions) == 50:
                response += "... (showing first 50 results)\n\n"
            
            response += "💡 **Next Steps:**\n"
            response += "• Run AI categorization: Use 'bookkeeping_helper_postgres.py'\n"
            response += "• Create vendor mappings: Use 'update_vendor_mapping'\n"
            response += "• Manual categorization: Update transactions directly in database\n"
            
            return response
            
        except Exception as e:
            return f"Error getting uncategorized transactions: {str(e)}"
    
    def get_vendor_mapping_suggestions(self) -> str:
        """
        Get suggestions for new vendor mappings based on uncategorized transactions.
        
        Analyzes patterns in uncategorized transactions to suggest useful vendor mappings.
        """
        try:
            # Get frequent uncategorized vendors
            query = """
            SELECT vendor, COUNT(*) as transaction_count, 
                   AVG(amount) as avg_amount,
                   MIN(date) as first_seen,
                   MAX(date) as last_seen,
                   STRING_AGG(DISTINCT description, ' | ') as sample_descriptions
            FROM transactions 
            WHERE (category IS NULL OR category = '' OR category = 'Uncategorized')
            AND vendor IS NOT NULL 
            AND vendor != ''
            AND deleted_at IS NULL
            GROUP BY vendor
            HAVING COUNT(*) >= 2
            ORDER BY COUNT(*) DESC, vendor
            LIMIT 20
            """
            vendors = self.db.execute_query(query)
            
            if not vendors:
                return "No vendor mapping suggestions available.\n\nEither all transactions are categorized or vendors need to be cleaned up first."
            
            response = f"🏪 Vendor Mapping Suggestions ({len(vendors)} vendors):\n\n"
            response += "These vendors appear frequently in uncategorized transactions:\n\n"
            
            for vendor in vendors:
                response += f"**{vendor['vendor']}**\n"
                response += f"• Transactions: {vendor['transaction_count']}\n"
                response += f"• Average Amount: ${vendor['avg_amount']:.2f}\n"
                response += f"• First Seen: {vendor['first_seen']}\n"
                response += f"• Last Seen: {vendor['last_seen']}\n"
                response += f"• Sample Descriptions: {vendor['sample_descriptions'][:100]}...\n"
                response += f"• **Suggested Command:** `update_vendor_mapping(vendor_pattern='{vendor['vendor']}', category='[CHOOSE CATEGORY]')`\n\n"
            
            response += "💡 **Common Categories:**\n"
            response += "• Groceries, Dining, Gas, Shopping, Utilities, Entertainment, Travel, Healthcare, etc.\n"
            response += "• Use 'get_categories' to see all available categories\n"
            
            return response
            
        except Exception as e:
            return f"Error getting vendor mapping suggestions: {str(e)}"