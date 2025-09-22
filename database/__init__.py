"""
Database package for AI Bookkeeping system.

This package provides SQLAlchemy ORM models and database operations
for the PostgreSQL-based bookkeeping system.
"""

from .database import (
    DatabaseConfig,
    DatabaseManager,
    TransactionOperations,
    VendorMappingOperations,
    ProcessingLogOperations,
    get_database_manager,
    test_connection
)

from .models import (
    Base,
    Transaction,
    VendorMapping,
    ProcessingLog,
    DuplicateReview,
    Category
)

__all__ = [
    # Database operations
    'DatabaseConfig',
    'DatabaseManager',
    'TransactionOperations',
    'VendorMappingOperations',
    'ProcessingLogOperations',
    'get_database_manager',
    'test_connection',
    
    # ORM Models
    'Base',
    'Transaction',
    'VendorMapping',
    'ProcessingLog',
    'DuplicateReview',
    'Category'
]