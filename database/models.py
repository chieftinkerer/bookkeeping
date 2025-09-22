#!/usr/bin/env python3
"""
models.py

SQLAlchemy ORM models for AI Bookkeeping system.
Defines all database tables and relationships using SQLAlchemy ORM.
"""

from typing import Optional
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    Column, Integer, String, Text, Date, DECIMAL, Boolean, 
    DateTime, ForeignKey, CheckConstraint, UniqueConstraint,
    Index, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Transaction(Base):
    """Core transaction data from CSV imports with deduplication support."""
    
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    category = Column(String(50))
    vendor = Column(String(200))
    source = Column(String(100))
    txn_id = Column(String(100))
    reference = Column(String(100))
    account = Column(String(50))
    balance = Column(DECIMAL(12, 2))
    original_hash = Column(String(32))
    possible_dup_group = Column(String(20))
    row_hash = Column(String(32), unique=True, nullable=False)
    time_part = Column(String(10))  # For time component if available
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    duplicate_reviews = relationship("DuplicateReview", back_populates="transaction")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('amount IS NOT NULL', name='valid_amount'),
        CheckConstraint('date IS NOT NULL', name='valid_date'),
        UniqueConstraint('row_hash', name='unique_row_hash'),
        
        # Indexes for performance
        Index('idx_transactions_date', 'date'),
        Index('idx_transactions_category', 'category'),
        Index('idx_transactions_vendor', 'vendor'),
        Index('idx_transactions_amount', 'amount'),
        Index('idx_transactions_source', 'source'),
        Index('idx_transactions_created_at', 'created_at'),
        
        # Composite indexes for common queries
        Index('idx_transactions_date_category', 'date', 'category'),
        Index('idx_transactions_date_amount', 'date', 'amount'),
        Index('idx_transactions_vendor_category', 'vendor', 'category'),
        Index('idx_transactions_txn_id_account', 'txn_id', 'account'),
    )
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, date={self.date}, description='{self.description[:50]}...', amount={self.amount})>"


class VendorMapping(Base):
    """Rules for automatic vendor name cleanup and categorization."""
    
    __tablename__ = 'vendor_mappings'
    
    id = Column(Integer, primary_key=True)
    vendor_pattern = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)
    is_regex = Column(Boolean, default=False)
    priority = Column(Integer, default=0)  # Higher priority rules applied first
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Constraints
    __table_args__ = (
        CheckConstraint("vendor_pattern IS NOT NULL AND LENGTH(vendor_pattern) > 0", name='valid_vendor_pattern'),
        CheckConstraint("category IS NOT NULL AND LENGTH(category) > 0", name='valid_category'),
        
        # Indexes
        Index('idx_vendor_mappings_pattern', 'vendor_pattern'),
        Index('idx_vendor_mappings_category', 'category'),
        Index('idx_vendor_mappings_priority', 'priority', postgresql_using='btree', postgresql_ops={'priority': 'DESC'}),
    )
    
    def __repr__(self):
        return f"<VendorMapping(id={self.id}, pattern='{self.vendor_pattern}', category='{self.category}', priority={self.priority})>"


class ProcessingLog(Base):
    """Audit trail of data processing operations."""
    
    __tablename__ = 'processing_log'
    
    id = Column(Integer, primary_key=True)
    operation_type = Column(String(50), nullable=False)  # 'csv_import', 'ai_categorization', 'duplicate_cleanup', etc.
    source_file = Column(String(500))
    records_processed = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    status = Column(String(20), default='pending')  # 'pending', 'completed', 'failed', 'partial'
    details = Column(JSONB)  # Store additional metadata
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)
    
    # Constraints
    __table_args__ = (
        CheckConstraint("operation_type IS NOT NULL", name='valid_operation_type'),
        CheckConstraint("status IN ('pending', 'completed', 'failed', 'partial')", name='valid_status'),
        
        # Indexes
        Index('idx_processing_log_operation', 'operation_type'),
        Index('idx_processing_log_status', 'status'),
        Index('idx_processing_log_started', 'started_at'),
    )
    
    def __repr__(self):
        return f"<ProcessingLog(id={self.id}, operation='{self.operation_type}', status='{self.status}')>"


class DuplicateReview(Base):
    """Staging area for manual review of potential duplicate transactions."""
    
    __tablename__ = 'duplicate_review'
    
    id = Column(Integer, primary_key=True)
    group_id = Column(String(20), nullable=False)
    transaction_id = Column(Integer, ForeignKey('transactions.id'), nullable=False)
    similarity_score = Column(DECIMAL(3, 2))  # 0.00 to 1.00
    reviewed = Column(Boolean, default=False)
    action_taken = Column(String(20))  # 'keep', 'merge', 'delete', 'ignore'
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    transaction = relationship("Transaction", back_populates="duplicate_reviews")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_duplicate_review_group', 'group_id'),
        Index('idx_duplicate_review_reviewed', 'reviewed'),
    )
    
    def __repr__(self):
        return f"<DuplicateReview(id={self.id}, group_id='{self.group_id}', transaction_id={self.transaction_id}, reviewed={self.reviewed})>"


class Category(Base):
    """Master list of valid expense/income categories."""
    
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    parent_category = Column(String(50))
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', sort_order={self.sort_order})>"