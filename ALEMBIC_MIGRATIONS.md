# Database Migration with Alembic

## 🔄 Why We Eliminated the SQL Schema File

Previously, we maintained a manual `db_schema.sql` file that contained the complete database schema. This approach had several limitations:

### ❌ Problems with Manual SQL Schema:
1. **No Version Control**: Changes weren't tracked incrementally
2. **Manual Synchronization**: SQLAlchemy models and SQL could get out of sync
3. **Deployment Issues**: Hard to apply partial changes or rollback
4. **Multiple Sources of Truth**: Both Python models and SQL defined the schema

### ✅ Benefits of Alembic Migrations:
1. **Single Source of Truth**: SQLAlchemy models define the schema
2. **Version Control**: Every change is tracked as a migration
3. **Rollback Capability**: Can upgrade or downgrade to any version
4. **Team Collaboration**: Merge conflicts are handled properly
5. **Deployment Safety**: Incremental, tested changes

## 🏗️ New Migration Workflow

### 📁 Directory Structure
```
database/
├── models.py           # SQLAlchemy ORM models (source of truth)
├── database.py         # Database operations
├── alembic.ini         # Alembic configuration
├── alembic/
│   ├── env.py          # Migration environment
│   └── versions/       # Individual migration files
│       ├── 28ee30ed64d7_initial_migration.py
│       └── 0c796c7d330d_add_default_categories.py
└── db_schema.sql.backup  # Backup of old manual schema
```

### 🔧 Commands

#### Initialize Database (New Projects)
```bash
# Run all migrations to create tables and populate data
python -m database --migrate
```

#### Development Workflow
```bash
# 1. Modify SQLAlchemy models in models.py
# 2. Generate migration from model changes
python -m database --create-migration "Add user table"

# 3. Review generated migration in alembic/versions/
# 4. Apply migration to database
python -m database --migrate
```

#### Database Operations
```bash
# Test database connection
python -m database --test-connection

# Create a new migration manually
python -m database --create-migration "Your migration description"

# Apply migrations (upgrade to latest)
python -m database --migrate
```

### 📝 Migration Examples

#### 1. Initial Schema Migration
The first migration (`28ee30ed64d7_initial_migration.py`) creates all tables:
- `transactions` - Core financial data
- `vendor_mappings` - Categorization rules
- `processing_log` - Audit trail
- `duplicate_review` - Manual review workflow
- `categories` - Category definitions

#### 2. Data Migration
The second migration (`0c796c7d330d_add_default_categories.py`) populates default categories:
- Groceries, Dining, Utilities, etc.
- Includes both upgrade (insert) and downgrade (delete) operations

## 🔄 Migration Best Practices

### Creating Migrations
1. **Make model changes first** in `models.py`
2. **Generate migration** with descriptive message
3. **Review migration code** before applying
4. **Test both upgrade and downgrade** operations

### Migration Content
- **Schema changes**: Table creation, column additions, index changes
- **Data migrations**: Populating lookup tables, data transformations
- **Rollback support**: Every migration should have a downgrade method

### Production Deployment
1. **Backup database** before applying migrations
2. **Test migrations** in staging environment first
3. **Apply incrementally** using `python -m database --migrate`
4. **Monitor for issues** and be prepared to rollback if needed

## 🛠️ Advanced Alembic Operations

### Direct Alembic Commands (from project root)
```bash
# Show current migration status
alembic -c database/alembic.ini current

# Show migration history
alembic -c database/alembic.ini history

# Upgrade to specific revision
alembic -c database/alembic.ini upgrade <revision_id>

# Downgrade to specific revision  
alembic -c database/alembic.ini downgrade <revision_id>

# Generate migration automatically (requires database connection)
alembic -c database/alembic.ini revision --autogenerate -m "Description"
```

### Environment-Specific Migrations
The Alembic environment (`alembic/env.py`) automatically:
- Loads database configuration from environment variables
- Imports SQLAlchemy models as the source of truth
- Configures connection settings for different environments

## 🔧 Configuration

### Database Connection
Migrations use the same configuration as the main application:
- Environment variables: `POSTGRES_HOST`, `POSTGRES_USER`, etc.
- Fallback to defaults: `localhost:5432/bookkeeping`

### Model Integration
- Models imported from `database.models`
- `Base.metadata` used as target for migrations
- Automatic detection of model changes (when using autogenerate)

## 🚀 Benefits for Development

1. **Faster Development**: No manual SQL writing
2. **Better Testing**: Each migration can be tested independently
3. **Team Coordination**: Migration conflicts are resolved at code level
4. **Documentation**: Every change is documented with migrations
5. **Rollback Safety**: Can undo changes when issues are found

This migration system provides a professional, maintainable approach to database schema management that scales with the project's growth.