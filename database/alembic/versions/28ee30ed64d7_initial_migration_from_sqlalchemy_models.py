"""Initial migration from SQLAlchemy models

Revision ID: 28ee30ed64d7
Revises: 
Create Date: 2025-09-22 10:35:18.821691

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28ee30ed64d7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create transactions table
    op.create_table('transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('amount', sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('vendor', sa.String(length=200), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('txn_id', sa.String(length=100), nullable=True),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('account', sa.String(length=50), nullable=True),
        sa.Column('balance', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('original_hash', sa.String(length=32), nullable=True),
        sa.Column('possible_dup_group', sa.String(length=20), nullable=True),
        sa.Column('row_hash', sa.String(length=32), nullable=False),
        sa.Column('time_part', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('amount IS NOT NULL', name='valid_amount'),
        sa.CheckConstraint('date IS NOT NULL', name='valid_date'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('row_hash', name='unique_row_hash')
    )
    
    # Create vendor_mappings table
    op.create_table('vendor_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vendor_pattern', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('is_regex', sa.Boolean(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("vendor_pattern IS NOT NULL AND LENGTH(vendor_pattern) > 0", name='valid_vendor_pattern'),
        sa.CheckConstraint("category IS NOT NULL AND LENGTH(category) > 0", name='valid_category'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create processing_log table
    op.create_table('processing_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('operation_type', sa.String(length=50), nullable=False),
        sa.Column('source_file', sa.String(length=500), nullable=True),
        sa.Column('records_processed', sa.Integer(), nullable=True),
        sa.Column('records_inserted', sa.Integer(), nullable=True),
        sa.Column('records_updated', sa.Integer(), nullable=True),
        sa.Column('records_skipped', sa.Integer(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('details', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("operation_type IS NOT NULL", name='valid_operation_type'),
        sa.CheckConstraint("status IN ('pending', 'completed', 'failed', 'partial')", name='valid_status'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create duplicate_review table
    op.create_table('duplicate_review',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.String(length=20), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('similarity_score', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('reviewed', sa.Boolean(), nullable=True),
        sa.Column('action_taken', sa.String(length=20), nullable=True),
        sa.Column('reviewed_by', sa.String(length=100), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create categories table
    op.create_table('categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_category', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create indexes
    op.create_index('idx_transactions_amount', 'transactions', ['amount'], unique=False)
    op.create_index('idx_transactions_category', 'transactions', ['category'], unique=False)
    op.create_index('idx_transactions_created_at', 'transactions', ['created_at'], unique=False)
    op.create_index('idx_transactions_date', 'transactions', ['date'], unique=False)
    op.create_index('idx_transactions_date_amount', 'transactions', ['date', 'amount'], unique=False)
    op.create_index('idx_transactions_date_category', 'transactions', ['date', 'category'], unique=False)
    op.create_index('idx_transactions_source', 'transactions', ['source'], unique=False)
    op.create_index('idx_transactions_txn_id_account', 'transactions', ['txn_id', 'account'], unique=False)
    op.create_index('idx_transactions_vendor', 'transactions', ['vendor'], unique=False)
    op.create_index('idx_transactions_vendor_category', 'transactions', ['vendor', 'category'], unique=False)
    op.create_index('idx_vendor_mappings_category', 'vendor_mappings', ['category'], unique=False)
    op.create_index('idx_vendor_mappings_pattern', 'vendor_mappings', ['vendor_pattern'], unique=False)
    op.create_index('idx_vendor_mappings_priority', 'vendor_mappings', ['priority'], unique=False)
    op.create_index('idx_processing_log_operation', 'processing_log', ['operation_type'], unique=False)
    op.create_index('idx_processing_log_started', 'processing_log', ['started_at'], unique=False)
    op.create_index('idx_processing_log_status', 'processing_log', ['status'], unique=False)
    op.create_index('idx_duplicate_review_group', 'duplicate_review', ['group_id'], unique=False)
    op.create_index('idx_duplicate_review_reviewed', 'duplicate_review', ['reviewed'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_duplicate_review_reviewed', table_name='duplicate_review')
    op.drop_index('idx_duplicate_review_group', table_name='duplicate_review')
    op.drop_index('idx_processing_log_status', table_name='processing_log')
    op.drop_index('idx_processing_log_started', table_name='processing_log')
    op.drop_index('idx_processing_log_operation', table_name='processing_log')
    op.drop_index('idx_vendor_mappings_priority', table_name='vendor_mappings')
    op.drop_index('idx_vendor_mappings_pattern', table_name='vendor_mappings')
    op.drop_index('idx_vendor_mappings_category', table_name='vendor_mappings')
    op.drop_index('idx_transactions_vendor_category', table_name='transactions')
    op.drop_index('idx_transactions_vendor', table_name='transactions')
    op.drop_index('idx_transactions_txn_id_account', table_name='transactions')
    op.drop_index('idx_transactions_source', table_name='transactions')
    op.drop_index('idx_transactions_date_category', table_name='transactions')
    op.drop_index('idx_transactions_date_amount', table_name='transactions')
    op.drop_index('idx_transactions_date', table_name='transactions')
    op.drop_index('idx_transactions_created_at', table_name='transactions')
    op.drop_index('idx_transactions_category', table_name='transactions')
    op.drop_index('idx_transactions_amount', table_name='transactions')
    
    # Drop tables
    op.drop_table('categories')
    op.drop_table('duplicate_review')
    op.drop_table('processing_log')
    op.drop_table('vendor_mappings')
    op.drop_table('transactions')
