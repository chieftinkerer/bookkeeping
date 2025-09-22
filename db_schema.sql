-- PostgreSQL Database Schema for AI Bookkeeping System
-- Migration from Excel-based storage to PostgreSQL

-- Core transactions table
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    description TEXT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    category VARCHAR(50),
    vendor VARCHAR(200),
    source VARCHAR(100),
    txn_id VARCHAR(100),
    reference VARCHAR(100),
    account VARCHAR(50),
    balance DECIMAL(12,2),
    original_hash VARCHAR(32),
    possible_dup_group VARCHAR(20),
    row_hash VARCHAR(32) UNIQUE NOT NULL,
    time_part VARCHAR(10), -- For time component if available
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_amount CHECK (amount IS NOT NULL),
    CONSTRAINT valid_date CHECK (date IS NOT NULL),
    CONSTRAINT unique_row_hash UNIQUE (row_hash)
);

-- Category mappings for automatic vendor categorization
CREATE TABLE vendor_mappings (
    id SERIAL PRIMARY KEY,
    vendor_pattern VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL,
    is_regex BOOLEAN DEFAULT FALSE,
    priority INTEGER DEFAULT 0, -- Higher priority rules applied first
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_vendor_pattern CHECK (vendor_pattern IS NOT NULL AND LENGTH(vendor_pattern) > 0),
    CONSTRAINT valid_category CHECK (category IS NOT NULL AND LENGTH(category) > 0)
);

-- Processing log for tracking data imports and operations
CREATE TABLE processing_log (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(50) NOT NULL, -- 'csv_import', 'ai_categorization', 'duplicate_cleanup', etc.
    source_file VARCHAR(500),
    records_processed INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'completed', 'failed', 'partial'
    details JSONB, -- Store additional metadata
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    
    -- Constraints
    CONSTRAINT valid_operation_type CHECK (operation_type IS NOT NULL),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'completed', 'failed', 'partial'))
);

-- Duplicate review table for manual review of potential duplicates
CREATE TABLE duplicate_review (
    id SERIAL PRIMARY KEY,
    group_id VARCHAR(20) NOT NULL,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    similarity_score DECIMAL(3,2), -- 0.00 to 1.00
    reviewed BOOLEAN DEFAULT FALSE,
    action_taken VARCHAR(20), -- 'keep', 'merge', 'delete', 'ignore'
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Categories reference table for validation
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    parent_category VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert default categories
INSERT INTO categories (name, description, sort_order) VALUES
('Groceries', 'Food and grocery purchases', 1),
('Dining', 'Restaurants and food delivery', 2),
('Utilities', 'Electric, gas, water, internet, phone', 3),
('Subscriptions', 'Recurring monthly/annual services', 4),
('Transportation', 'Gas, parking, public transit, car maintenance', 5),
('Housing', 'Rent, mortgage, maintenance, furniture', 6),
('Healthcare', 'Medical, dental, pharmacy, fitness', 7),
('Insurance', 'Auto, health, life, property insurance', 8),
('Income', 'Salary, freelance, investments, refunds', 9),
('Shopping', 'Clothing, electronics, household items', 10),
('Misc', 'Uncategorized or one-off expenses', 11);

-- Indexes for performance
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_vendor ON transactions(vendor);
CREATE INDEX idx_transactions_amount ON transactions(amount);
CREATE INDEX idx_transactions_source ON transactions(source);
CREATE INDEX idx_transactions_txn_id ON transactions(txn_id, account);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);

-- Composite indexes for common queries
CREATE INDEX idx_transactions_date_category ON transactions(date, category);
CREATE INDEX idx_transactions_date_amount ON transactions(date, amount);
CREATE INDEX idx_transactions_vendor_category ON transactions(vendor, category);

-- Full-text search index for descriptions
CREATE INDEX idx_transactions_description_fts ON transactions USING GIN (to_tsvector('english', description));

-- Vendor mappings indexes
CREATE INDEX idx_vendor_mappings_pattern ON vendor_mappings(vendor_pattern);
CREATE INDEX idx_vendor_mappings_category ON vendor_mappings(category);
CREATE INDEX idx_vendor_mappings_priority ON vendor_mappings(priority DESC);

-- Processing log indexes
CREATE INDEX idx_processing_log_operation ON processing_log(operation_type);
CREATE INDEX idx_processing_log_status ON processing_log(status);
CREATE INDEX idx_processing_log_started ON processing_log(started_at);

-- Duplicate review indexes
CREATE INDEX idx_duplicate_review_group ON duplicate_review(group_id);
CREATE INDEX idx_duplicate_review_reviewed ON duplicate_review(reviewed);

-- Views for common queries
CREATE VIEW transaction_summary AS
SELECT 
    date_trunc('month', date) as month,
    category,
    COUNT(*) as transaction_count,
    SUM(amount) as total_amount,
    AVG(amount) as avg_amount,
    MIN(amount) as min_amount,
    MAX(amount) as max_amount
FROM transactions 
WHERE category IS NOT NULL
GROUP BY date_trunc('month', date), category
ORDER BY month DESC, category;

CREATE VIEW monthly_totals AS
SELECT 
    date_trunc('month', date) as month,
    COUNT(*) as transaction_count,
    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_income,
    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_expenses,
    SUM(amount) as net_total
FROM transactions 
GROUP BY date_trunc('month', date)
ORDER BY month DESC;

CREATE VIEW uncategorized_transactions AS
SELECT 
    id, date, description, amount, vendor, source, created_at
FROM transactions 
WHERE category IS NULL OR category = ''
ORDER BY date DESC;

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to automatically update updated_at columns
CREATE TRIGGER update_transactions_updated_at 
    BEFORE UPDATE ON transactions 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_vendor_mappings_updated_at 
    BEFORE UPDATE ON vendor_mappings 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE transactions IS 'Core transaction data from CSV imports with deduplication support';
COMMENT ON TABLE vendor_mappings IS 'Rules for automatic vendor name cleanup and categorization';
COMMENT ON TABLE processing_log IS 'Audit trail of data processing operations';
COMMENT ON TABLE duplicate_review IS 'Staging area for manual review of potential duplicate transactions';
COMMENT ON TABLE categories IS 'Master list of valid expense/income categories';

COMMENT ON COLUMN transactions.row_hash IS 'Unique hash for deduplication, computed from date+description+amount';
COMMENT ON COLUMN transactions.original_hash IS 'Original hash from CSV import for tracking data lineage';
COMMENT ON COLUMN transactions.possible_dup_group IS 'Group ID for transactions that may be duplicates requiring manual review';
COMMENT ON COLUMN vendor_mappings.is_regex IS 'Whether vendor_pattern should be treated as regex or literal match';
COMMENT ON COLUMN vendor_mappings.priority IS 'Higher values take precedence when multiple patterns match';