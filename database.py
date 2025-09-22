#!/usr/bin/env python3
"""
database.py

Database utility module for AI Bookkeeping system.
Provides PostgreSQL connection management, migrations, and common operations.
PostgreSQL backend enables better concurrency, data integrity, and AI integration.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import datetime, date
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Configuration management for database connections."""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, str]:
        """Load database configuration from environment variables or defaults."""
        return {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', '5432')),
            'database': os.getenv('POSTGRES_DB', 'bookkeeping'),
            'user': os.getenv('POSTGRES_USER', 'bookkeeper'),
            'password': os.getenv('POSTGRES_PASSWORD', 'password'),
            'sslmode': os.getenv('POSTGRES_SSLMODE', 'prefer'),
            'application_name': 'ai_bookkeeping'
        }
    
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        return (f"postgresql://{self.config['user']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/{self.config['database']}"
                f"?sslmode={self.config['sslmode']}&application_name={self.config['application_name']}")

class DatabaseManager:
    """Manages PostgreSQL connections and operations for bookkeeping system."""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._pool: Optional[ThreadedConnectionPool] = None
        self._init_connection_pool()
    
    def _init_connection_pool(self):
        """Initialize PostgreSQL connection pool."""
        try:
            self._pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                **self.config.config
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Execute a SELECT query and return results as list of dictionaries."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected row count."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount
    
    def execute_batch(self, query: str, params_list: List[tuple]) -> int:
        """Execute a query with multiple parameter sets (batch operation)."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, query, params_list)
                return cur.rowcount
    
    def create_schema(self, schema_file: str = "db_schema.sql"):
        """Create database schema from SQL file."""
        try:
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(schema_sql)
            
            logger.info(f"Database schema created successfully from {schema_file}")
        except Exception as e:
            logger.error(f"Failed to create database schema: {e}")
            raise
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        );
        """
        result = self.execute_query(query, (table_name,))
        return result[0]['exists'] if result else False
    
    def get_table_row_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        query = f"SELECT COUNT(*) as count FROM {table_name};"
        result = self.execute_query(query)
        return result[0]['count'] if result else 0

class TransactionOperations:
    """High-level operations for transaction management."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def insert_transaction(self, transaction_data: Dict[str, Any]) -> int:
        """Insert a single transaction and return its ID."""
        query = """
        INSERT INTO transactions (
            date, description, amount, category, vendor, source, 
            txn_id, reference, account, balance, original_hash, 
            possible_dup_group, row_hash, time_part
        ) VALUES (
            %(date)s, %(description)s, %(amount)s, %(category)s, %(vendor)s, %(source)s,
            %(txn_id)s, %(reference)s, %(account)s, %(balance)s, %(original_hash)s,
            %(possible_dup_group)s, %(row_hash)s, %(time_part)s
        ) RETURNING id;
        """
        
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, transaction_data)
                return cur.fetchone()[0]
    
    def insert_transactions_batch(self, transactions: List[Dict[str, Any]]) -> int:
        """Insert multiple transactions in a batch operation."""
        if not transactions:
            return 0
        
        query = """
        INSERT INTO transactions (
            date, description, amount, category, vendor, source, 
            txn_id, reference, account, balance, original_hash, 
            possible_dup_group, row_hash, time_part
        ) VALUES (
            %(date)s, %(description)s, %(amount)s, %(category)s, %(vendor)s, %(source)s,
            %(txn_id)s, %(reference)s, %(account)s, %(balance)s, %(original_hash)s,
            %(possible_dup_group)s, %(row_hash)s, %(time_part)s
        ) ON CONFLICT (row_hash) DO NOTHING;
        """
        
        # Convert to list of tuples for psycopg2.extras.execute_batch
        params_list = []
        for t in transactions:
            params_list.append(t)
        
        return self.db.execute_batch(query, params_list)
    
    def get_transactions(self, 
                        start_date: Optional[date] = None,
                        end_date: Optional[date] = None,
                        category: Optional[str] = None,
                        vendor: Optional[str] = None,
                        limit: Optional[int] = None) -> List[Dict]:
        """Get transactions with optional filtering."""
        
        conditions = []
        params = []
        
        query = "SELECT * FROM transactions WHERE 1=1"
        
        if start_date:
            conditions.append("date >= %s")
            params.append(start_date)
        
        if end_date:
            conditions.append("date <= %s")
            params.append(end_date)
        
        if category:
            conditions.append("category = %s")
            params.append(category)
        
        if vendor:
            conditions.append("vendor ILIKE %s")
            params.append(f"%{vendor}%")
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY date DESC, id DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        return self.db.execute_query(query, tuple(params))
    
    def get_uncategorized_transactions(self, limit: Optional[int] = None) -> List[Dict]:
        """Get transactions that need categorization."""
        query = """
        SELECT id, date, description, amount, vendor, source, created_at
        FROM transactions 
        WHERE category IS NULL OR category = ''
        ORDER BY date DESC, id DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        return self.db.execute_query(query)
    
    def update_transaction_category(self, transaction_id: int, category: str, vendor: Optional[str] = None) -> bool:
        """Update the category (and optionally vendor) of a transaction."""
        if vendor:
            query = """
            UPDATE transactions 
            SET category = %s, vendor = %s, updated_at = NOW()
            WHERE id = %s
            """
            params = (category, vendor, transaction_id)
        else:
            query = """
            UPDATE transactions 
            SET category = %s, updated_at = NOW()
            WHERE id = %s
            """
            params = (category, transaction_id)
        
        return self.db.execute_update(query, params) > 0
    
    def get_existing_row_hashes(self, row_hashes: List[str]) -> set:
        """Check which row hashes already exist in the database."""
        if not row_hashes:
            return set()
        
        # Use ANY operator for efficient IN-style query
        query = "SELECT row_hash FROM transactions WHERE row_hash = ANY(%s)"
        result = self.db.execute_query(query, (row_hashes,))
        return {row['row_hash'] for row in result}
    
    def get_monthly_summary(self, year: Optional[int] = None) -> List[Dict]:
        """Get monthly spending summary, optionally filtered by year."""
        query = """
        SELECT 
            date_trunc('month', date) as month,
            category,
            COUNT(*) as transaction_count,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount
        FROM transactions 
        WHERE category IS NOT NULL
        """
        
        params = []
        if year:
            query += " AND EXTRACT(year FROM date) = %s"
            params.append(year)
        
        query += """
        GROUP BY date_trunc('month', date), category
        ORDER BY month DESC, category
        """
        
        return self.db.execute_query(query, tuple(params))

class VendorMappingOperations:
    """Operations for vendor mapping and categorization rules."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def add_vendor_mapping(self, vendor_pattern: str, category: str, 
                          is_regex: bool = False, priority: int = 0) -> int:
        """Add a new vendor mapping rule."""
        query = """
        INSERT INTO vendor_mappings (vendor_pattern, category, is_regex, priority)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
        """
        
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (vendor_pattern, category, is_regex, priority))
                return cur.fetchone()[0]
    
    def get_vendor_mappings(self) -> List[Dict]:
        """Get all vendor mapping rules ordered by priority."""
        query = """
        SELECT * FROM vendor_mappings 
        ORDER BY priority DESC, id
        """
        return self.db.execute_query(query)
    
    def find_category_for_vendor(self, vendor_name: str) -> Optional[str]:
        """Find the best matching category for a vendor name."""
        mappings = self.get_vendor_mappings()
        
        for mapping in mappings:
            pattern = mapping['vendor_pattern']
            
            if mapping['is_regex']:
                import re
                if re.search(pattern, vendor_name, re.IGNORECASE):
                    return mapping['category']
            else:
                if pattern.lower() in vendor_name.lower():
                    return mapping['category']
        
        return None

class ProcessingLogOperations:
    """Operations for tracking data processing operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def start_operation(self, operation_type: str, source_file: Optional[str] = None, 
                       details: Optional[Dict] = None) -> int:
        """Start tracking a new processing operation."""
        query = """
        INSERT INTO processing_log (operation_type, source_file, details, status)
        VALUES (%s, %s, %s, 'pending')
        RETURNING id;
        """
        
        details_json = json.dumps(details) if details else None
        
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (operation_type, source_file, details_json))
                return cur.fetchone()[0]
    
    def complete_operation(self, log_id: int, 
                         records_processed: int = 0,
                         records_inserted: int = 0,
                         records_updated: int = 0,
                         records_skipped: int = 0,
                         error_count: int = 0,
                         status: str = 'completed',
                         details: Optional[Dict] = None):
        """Complete a processing operation with results."""
        query = """
        UPDATE processing_log 
        SET records_processed = %s, records_inserted = %s, records_updated = %s,
            records_skipped = %s, error_count = %s, status = %s, 
            details = %s, completed_at = NOW()
        WHERE id = %s
        """
        
        details_json = json.dumps(details) if details else None
        
        self.db.execute_update(query, (
            records_processed, records_inserted, records_updated,
            records_skipped, error_count, status, details_json, log_id
        ))

# Convenience function for getting a configured database manager
def get_database_manager() -> DatabaseManager:
    """Get a configured database manager instance."""
    return DatabaseManager()

# Test database connection
def test_connection():
    """Test database connection and print status."""
    try:
        db = get_database_manager()
        result = db.execute_query("SELECT version();")
        print(f"✅ Database connection successful!")
        print(f"PostgreSQL version: {result[0]['version']}")
        
        # Check if schema exists
        if db.table_exists('transactions'):
            count = db.get_table_row_count('transactions')
            print(f"📊 Transactions table exists with {count} records")
        else:
            print("⚠️  Transactions table not found - run schema creation first")
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    return True

def main():
    """Command-line interface for database operations."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Database utility operations")
    parser.add_argument("--test-connection", action="store_true", 
                       help="Test database connection")
    parser.add_argument("--create-schema", action="store_true",
                       help="Create database schema from db_schema.sql")
    parser.add_argument("--schema-file", default="db_schema.sql",
                       help="Path to schema SQL file")
    
    args = parser.parse_args()
    
    if args.test_connection:
        success = test_connection()
        sys.exit(0 if success else 1)
    
    if args.create_schema:
        try:
            db = get_database_manager()
            db.create_schema(args.schema_file)
            print(f"✅ Schema created successfully from {args.schema_file}")
        except Exception as e:
            print(f"❌ Schema creation failed: {e}")
            sys.exit(1)
    
    if not any([args.test_connection, args.create_schema]):
        # Default action: test connection
        test_connection()

if __name__ == "__main__":
    main()