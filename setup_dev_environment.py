#!/usr/bin/env python3
"""
setup_dev_environment.py

Setup script for the AI Bookkeeping development environment.
Installs dependencies and sets up database configuration.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a shell command and handle errors."""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return None

def install_python_dependencies():
    """Install Python dependencies."""
    requirements_file = Path(__file__).parent / "requirements.txt"
    if requirements_file.exists():
        cmd = f"{sys.executable} -m pip install -r {requirements_file}"
        return run_command(cmd, "Installing Python dependencies")
    else:
        print("❌ requirements.txt not found")
        return None

def create_env_file():
    """Create a sample .env file for database configuration."""
    env_file = Path(__file__).parent / ".env.example"
    env_content = """# AI Bookkeeping Database Configuration
# Copy this to .env and update with your settings

# PostgreSQL Connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=bookkeeping
POSTGRES_USER=bookkeeper
POSTGRES_PASSWORD=password
POSTGRES_SSLMODE=prefer

# OpenAI API (for existing categorization features)
OPENAI_API_KEY=your_openai_api_key_here

# Data Paths (optional overrides)
BOOKKEEPING_CSV_PATH=/path/to/csv/files

# Development Settings
DEBUG=true
LOG_LEVEL=INFO
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print(f"✅ Created {env_file}")
        print("📝 Copy .env.example to .env and update with your settings")
    except Exception as e:
        print(f"❌ Failed to create .env.example: {e}")

def check_postgresql():
    """Check if PostgreSQL is available."""
    # Try to find psql command
    psql_check = run_command("which psql", "Checking for PostgreSQL client")
    if psql_check:
        print("✅ PostgreSQL client found")
        
        # Try to connect (this might fail if not configured)
        print("💡 To test database connection later, run: python database.py")
    else:
        print("⚠️  PostgreSQL client not found")
        print("💡 Install PostgreSQL or connect to an existing instance")
        print("💡 For local development, consider using Docker:")
        print("   docker run -d --name bookkeeping-postgres \\")
        print("     -e POSTGRES_DB=bookkeeping \\")
        print("     -e POSTGRES_USER=bookkeeper \\")
        print("     -e POSTGRES_PASSWORD=password \\")
        print("     -p 5432:5432 postgres:15")

def main():
    """Main setup function."""
    print("🚀 Setting up AI Bookkeeping development environment...")
    
    # Install dependencies
    install_python_dependencies()
    
    # Create environment configuration
    create_env_file()
    
    # Check PostgreSQL
    check_postgresql()
    
    print("\n📋 Next steps:")
    print("1. Copy .env.example to .env and update database settings")
    print("2. Set up PostgreSQL database (local or remote)")
    print("3. Run: python database.py --create-schema")
    print("4. Run: python database.py --test-connection")
    print("5. Start importing CSV data with: python csv_to_postgres.py")
    
    print("\n✨ Development environment setup complete!")

if __name__ == "__main__":
    main()