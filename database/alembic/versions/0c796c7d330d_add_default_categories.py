"""Add default categories

Revision ID: 0c796c7d330d
Revises: 28ee30ed64d7
Create Date: 2025-09-22 10:36:40.883365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c796c7d330d'
down_revision: Union[str, Sequence[str], None] = '28ee30ed64d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Insert default categories
    categories_table = sa.table('categories',
        sa.column('name', sa.String),
        sa.column('description', sa.String),
        sa.column('sort_order', sa.Integer)
    )
    
    op.bulk_insert(categories_table, [
        {'name': 'Groceries', 'description': 'Food and grocery purchases', 'sort_order': 1},
        {'name': 'Dining', 'description': 'Restaurants and food delivery', 'sort_order': 2},
        {'name': 'Utilities', 'description': 'Electric, gas, water, internet, phone', 'sort_order': 3},
        {'name': 'Subscriptions', 'description': 'Recurring monthly/annual services', 'sort_order': 4},
        {'name': 'Transportation', 'description': 'Gas, parking, public transit, car maintenance', 'sort_order': 5},
        {'name': 'Housing', 'description': 'Rent, mortgage, maintenance, furniture', 'sort_order': 6},
        {'name': 'Healthcare', 'description': 'Medical, dental, pharmacy, fitness', 'sort_order': 7},
        {'name': 'Insurance', 'description': 'Auto, health, life, property insurance', 'sort_order': 8},
        {'name': 'Income', 'description': 'Salary, freelance, investments, refunds', 'sort_order': 9},
        {'name': 'Shopping', 'description': 'Clothing, electronics, household items', 'sort_order': 10},
        {'name': 'Misc', 'description': 'Uncategorized or one-off expenses', 'sort_order': 11}
    ])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove default categories
    op.execute("DELETE FROM categories WHERE name IN ('Groceries', 'Dining', 'Utilities', 'Subscriptions', 'Transportation', 'Housing', 'Healthcare', 'Insurance', 'Income', 'Shopping', 'Misc')")
