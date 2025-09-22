"""
Database Manager for MCP Server

Provides database operations and connection management for the AI Bookkeeping MCP server.
"""

import sys
from pathlib import Path

# Add parent directory to path for database imports
sys.path.append(str(Path(__file__).parent.parent))

from database import DatabaseManager as CoreDatabaseManager, TransactionOperations, VendorMappingOperations, ProcessingLogOperations

class DatabaseManager:
    """Enhanced database manager for MCP server operations."""
    
    def __init__(self):
        """Initialize database connections and operations."""
        self.db = CoreDatabaseManager()
        self.tx_ops = TransactionOperations(self.db)
        self.vendor_ops = VendorMappingOperations(self.db)
        self.log_ops = ProcessingLogOperations(self.db)
    
    def get_transaction_operations(self):
        """Get transaction operations instance."""
        return self.tx_ops
    
    def get_vendor_operations(self):
        """Get vendor mapping operations instance."""
        return self.vendor_ops
    
    def get_log_operations(self):
        """Get processing log operations instance."""
        return self.log_ops
    
    def get_core_db(self):
        """Get core database manager instance."""
        return self.db
    
    def test_connection(self):
        """Test database connection and return basic stats."""
        try:
            # Test basic query
            result = self.db.execute_query("SELECT version();")
            postgres_version = result[0]['version'] if result else 'Unknown'
            
            # Get basic counts
            total_transactions = self.db.get_table_row_count('transactions')
            total_categories = self.db.get_table_row_count('categories')
            total_vendor_mappings = self.db.get_table_row_count('vendor_mappings')
            
            return {
                'connected': True,
                'postgres_version': postgres_version,
                'total_transactions': total_transactions,
                'total_categories': total_categories,
                'total_vendor_mappings': total_vendor_mappings
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }
    
    def get_database_health(self):
        """Get comprehensive database health information."""
        try:
            health = self.test_connection()
            
            if health['connected']:
                # Add more detailed health checks
                uncategorized_count = len(self.tx_ops.get_uncategorized_transactions(limit=1))
                
                # Get date range of transactions
                date_range_query = """
                SELECT MIN(date) as earliest, MAX(date) as latest, COUNT(*) as total
                FROM transactions WHERE date IS NOT NULL
                """
                date_info = self.db.execute_query(date_range_query)
                
                health.update({
                    'uncategorized_transactions': uncategorized_count,
                    'date_range': date_info[0] if date_info else None,
                    'tables_exist': {
                        'transactions': self.db.table_exists('transactions'),
                        'categories': self.db.table_exists('categories'),
                        'vendor_mappings': self.db.table_exists('vendor_mappings'),
                        'processing_log': self.db.table_exists('processing_log')
                    }
                })
            
            return health
        except Exception as e:
            return {
                'connected': False,
                'error': f"Health check failed: {str(e)}"
            }