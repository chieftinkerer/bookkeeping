#!/usr/bin/env python3
"""
database.py

Database utility module for AI Bookkeeping system.
Provides SQLAlchemy ORM-based PostgreSQL connection management and operations.
PostgreSQL backend enables better concurrency, data integrity, and AI integration.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from decimal import Decimal
from datetime import datetime, date
from contextlib import contextmanager

from sqlalchemy import create_engine, text, and_, or_, func, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import IntegrityError
import pandas as pd

# Import models - handle both package and direct execution
try:
    from .models import Base, Transaction, VendorMapping, ProcessingLog, DuplicateReview, Category
except ImportError:
    # Fallback for direct execution or Alembic
    from models import Base, Transaction, VendorMapping, ProcessingLog, DuplicateReview, Category

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
    """Manages PostgreSQL connections and operations using SQLAlchemy ORM."""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self.engine = None
        self.SessionLocal = None
        self._init_sqlalchemy()
    
    def _init_sqlalchemy(self):
        """Initialize SQLAlchemy engine and session factory."""
        try:
            self.engine = create_engine(
                self.config.get_connection_string(),
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False  # Set to True for SQL debugging
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            logger.info("SQLAlchemy database engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SQLAlchemy engine: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Session:
        """Context manager for database sessions."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def execute_raw_query(self, query: str, params: Optional[dict] = None) -> List[Dict]:
        """Execute a raw SQL query and return results as list of dictionaries."""
        with self.get_session() as session:
            result = session.execute(text(query), params or {})
            return [dict(row._asdict()) for row in result.fetchall()]
    
    def create_tables(self):
        """Create all tables using SQLAlchemy models (deprecated - use migrations)."""
        logger.warning("create_tables() is deprecated. Use run_migrations() instead.")
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("All tables created successfully using SQLAlchemy models")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    def run_migrations(self, message: str = "Auto migration"):
        """Run Alembic migrations to upgrade database to latest schema."""
        try:
            from alembic.config import Config
            from alembic import command
            import os
            
            # Get the directory containing this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            alembic_cfg = Config(os.path.join(current_dir, "alembic.ini"))
            
            # Run upgrade to head
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations completed successfully")
        except Exception as e:
            logger.error(f"Failed to run migrations: {e}")
            raise
    
    def create_migration(self, message: str):
        """Create a new Alembic migration based on model changes."""
        try:
            from alembic.config import Config
            from alembic import command
            import os
            
            # Get the directory containing this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            alembic_cfg = Config(os.path.join(current_dir, "alembic.ini"))
            
            # Generate new migration
            command.revision(alembic_cfg, autogenerate=True, message=message)
            logger.info(f"Created new migration: {message}")
        except Exception as e:
            logger.error(f"Failed to create migration: {e}")
            raise
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        with self.get_session() as session:
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = :table_name
                );
            """), {"table_name": table_name})
            return result.scalar()
    
    def get_table_row_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        with self.get_session() as session:
            if table_name == 'transactions':
                return session.query(func.count(Transaction.id)).scalar()
            elif table_name == 'vendor_mappings':
                return session.query(func.count(VendorMapping.id)).scalar()
            elif table_name == 'processing_log':
                return session.query(func.count(ProcessingLog.id)).scalar()
            elif table_name == 'duplicate_review':
                return session.query(func.count(DuplicateReview.id)).scalar()
            elif table_name == 'categories':
                return session.query(func.count(Category.id)).scalar()
            else:
                # Fallback to raw SQL for unknown tables
                result = session.execute(text(f"SELECT COUNT(*) as count FROM {table_name};"))
                return result.scalar()

class TransactionOperations:
    """High-level operations for transaction management using SQLAlchemy ORM."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def insert_transaction(self, transaction_data: Dict[str, Any]) -> int:
        """Insert a single transaction and return its ID."""
        with self.db.get_session() as session:
            transaction = Transaction(**transaction_data)
            session.add(transaction)
            session.flush()  # Get the ID without committing
            return transaction.id
    
    def insert_transactions_batch(self, transactions: List[Dict[str, Any]]) -> int:
        """Insert multiple transactions in a batch operation."""
        if not transactions:
            return 0
        
        with self.db.get_session() as session:
            transaction_objects = [Transaction(**t) for t in transactions]
            session.add_all(transaction_objects)
            return len(transaction_objects)
    
    def get_transactions(self, 
                        start_date: Optional[date] = None,
                        end_date: Optional[date] = None,
                        category: Optional[str] = None,
                        vendor: Optional[str] = None,
                        limit: Optional[int] = None) -> List[Dict]:
        """Get transactions with optional filtering."""
        
        with self.db.get_session() as session:
            query = session.query(Transaction)
            
            if start_date:
                query = query.filter(Transaction.date >= start_date)
            
            if end_date:
                query = query.filter(Transaction.date <= end_date)
            
            if category:
                query = query.filter(Transaction.category == category)
            
            if vendor:
                query = query.filter(Transaction.vendor.ilike(f"%{vendor}%"))
            
            query = query.order_by(desc(Transaction.date), desc(Transaction.id))
            
            if limit:
                query = query.limit(limit)
            
            results = query.all()
            return [self._transaction_to_dict(t) for t in results]
    
    def get_uncategorized_transactions(self, limit: Optional[int] = None) -> List[Dict]:
        """Get transactions that need categorization."""
        with self.db.get_session() as session:
            query = session.query(Transaction).filter(
                or_(Transaction.category.is_(None), Transaction.category == '')
            ).order_by(desc(Transaction.date), desc(Transaction.id))
            
            if limit:
                query = query.limit(limit)
            
            results = query.all()
            return [self._transaction_to_dict(t) for t in results]
    
    def update_transaction_category(self, transaction_id: int, category: str, vendor: Optional[str] = None) -> bool:
        """Update the category (and optionally vendor) of a transaction."""
        with self.db.get_session() as session:
            transaction = session.query(Transaction).filter(Transaction.id == transaction_id).first()
            if transaction:
                transaction.category = category
                if vendor:
                    transaction.vendor = vendor
                transaction.updated_at = datetime.now()
                return True
            return False
    
    def get_existing_row_hashes(self, row_hashes: List[str]) -> set:
        """Check which row hashes already exist in the database."""
        if not row_hashes:
            return set()
        
        with self.db.get_session() as session:
            results = session.query(Transaction.row_hash).filter(
                Transaction.row_hash.in_(row_hashes)
            ).all()
            return {row.row_hash for row in results}
    
    def get_monthly_summary(self, year: Optional[int] = None) -> List[Dict]:
        """Get monthly spending summary, optionally filtered by year."""
        with self.db.get_session() as session:
            query = session.query(
                func.date_trunc('month', Transaction.date).label('month'),
                Transaction.category,
                func.count().label('transaction_count'),
                func.sum(Transaction.amount).label('total_amount'),
                func.avg(Transaction.amount).label('avg_amount')
            ).filter(Transaction.category.isnot(None))
            
            if year:
                query = query.filter(func.extract('year', Transaction.date) == year)
            
            query = query.group_by(
                func.date_trunc('month', Transaction.date),
                Transaction.category
            ).order_by(
                desc(func.date_trunc('month', Transaction.date)),
                Transaction.category
            )
            
            results = query.all()
            return [dict(row._asdict()) for row in results]
    
    def _transaction_to_dict(self, transaction: Transaction) -> Dict:
        """Convert a Transaction object to a dictionary."""
        return {
            'id': transaction.id,
            'date': transaction.date,
            'description': transaction.description,
            'amount': float(transaction.amount) if transaction.amount else None,
            'category': transaction.category,
            'vendor': transaction.vendor,
            'source': transaction.source,
            'txn_id': transaction.txn_id,
            'reference': transaction.reference,
            'account': transaction.account,
            'balance': float(transaction.balance) if transaction.balance else None,
            'original_hash': transaction.original_hash,
            'possible_dup_group': transaction.possible_dup_group,
            'row_hash': transaction.row_hash,
            'time_part': transaction.time_part,
            'created_at': transaction.created_at,
            'updated_at': transaction.updated_at
        }

class VendorMappingOperations:
    """Operations for vendor mapping and categorization rules using SQLAlchemy ORM."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def add_vendor_mapping(self, vendor_pattern: str, category: str, 
                          is_regex: bool = False, priority: int = 0) -> int:
        """Add a new vendor mapping rule."""
        with self.db.get_session() as session:
            mapping = VendorMapping(
                vendor_pattern=vendor_pattern,
                category=category,
                is_regex=is_regex,
                priority=priority
            )
            session.add(mapping)
            session.flush()
            return mapping.id
    
    def get_vendor_mappings(self) -> List[Dict]:
        """Get all vendor mapping rules ordered by priority."""
        with self.db.get_session() as session:
            mappings = session.query(VendorMapping).order_by(
                desc(VendorMapping.priority),
                VendorMapping.id
            ).all()
            
            return [self._mapping_to_dict(m) for m in mappings]
    
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
    
    def _mapping_to_dict(self, mapping: VendorMapping) -> Dict:
        """Convert a VendorMapping object to a dictionary."""
        return {
            'id': mapping.id,
            'vendor_pattern': mapping.vendor_pattern,
            'category': mapping.category,
            'is_regex': mapping.is_regex,
            'priority': mapping.priority,
            'created_at': mapping.created_at,
            'updated_at': mapping.updated_at
        }

class ProcessingLogOperations:
    """Operations for tracking data processing operations using SQLAlchemy ORM."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def start_operation(self, operation_type: str, source_file: Optional[str] = None, 
                       details: Optional[Dict] = None) -> int:
        """Start tracking a new processing operation."""
        with self.db.get_session() as session:
            log_entry = ProcessingLog(
                operation_type=operation_type,
                source_file=source_file,
                details=details,
                status='pending'
            )
            session.add(log_entry)
            session.flush()
            return log_entry.id
    
    def complete_operation(self, log_id: int, 
                         records_processed: int = 0,
                         records_inserted: int = 0,
                         records_updated: int = 0,
                         records_skipped: int = 0,
                         error_count: int = 0,
                         status: str = 'completed',
                         details: Optional[Dict] = None):
        """Complete a processing operation with results."""
        with self.db.get_session() as session:
            log_entry = session.query(ProcessingLog).filter(ProcessingLog.id == log_id).first()
            if log_entry:
                log_entry.records_processed = records_processed
                log_entry.records_inserted = records_inserted
                log_entry.records_updated = records_updated
                log_entry.records_skipped = records_skipped
                log_entry.error_count = error_count
                log_entry.status = status
                log_entry.details = details
                log_entry.completed_at = datetime.now()

# Convenience function for getting a configured database manager
def get_database_manager() -> DatabaseManager:
    """Get a configured database manager instance."""
    return DatabaseManager()

# Test database connection
def test_connection():
    """Test database connection and print status."""
    try:
        db = get_database_manager()
        result = db.execute_raw_query("SELECT version();")
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
    parser.add_argument("--migrate", action="store_true",
                       help="Run database migrations to latest version")
    parser.add_argument("--create-migration", type=str, metavar="MESSAGE",
                       help="Create a new migration with the given message")
    
    # Deprecated options (kept for backward compatibility)
    parser.add_argument("--create-schema", action="store_true",
                       help="DEPRECATED: Use --migrate instead")
    parser.add_argument("--create-tables", action="store_true",
                       help="DEPRECATED: Use --migrate instead")
    parser.add_argument("--schema-file", default="database/db_schema.sql.backup",
                       help="DEPRECATED: Path to old schema SQL file")
    
    args = parser.parse_args()
    
    if args.test_connection:
        success = test_connection()
        sys.exit(0 if success else 1)
    
    if args.migrate:
        try:
            db = get_database_manager()
            db.run_migrations()
            print("✅ Database migrations completed successfully")
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            sys.exit(1)
    
    if args.create_migration:
        try:
            db = get_database_manager()
            db.create_migration(args.create_migration)
            print(f"✅ Created new migration: {args.create_migration}")
        except Exception as e:
            print(f"❌ Migration creation failed: {e}")
            sys.exit(1)
    
    # Handle deprecated options
    if args.create_schema:
        print("❌ ERROR: --create-schema is deprecated and no longer supported.")
        print("ℹ️  Use: python -m database --migrate")
        print("ℹ️  This will run Alembic migrations from SQLAlchemy models.")
        sys.exit(1)
    
    if args.create_tables:
        print("❌ ERROR: --create-tables is deprecated and no longer supported.")
        print("ℹ️  Use: python -m database --migrate")
        print("ℹ️  This will run Alembic migrations from SQLAlchemy models.")
        sys.exit(1)
    
    if not any([args.test_connection, args.migrate, args.create_migration, args.create_schema, args.create_tables]):
        # Default action: test connection
        test_connection()

if __name__ == "__main__":
    main()