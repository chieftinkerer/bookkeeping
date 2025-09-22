#!/usr/bin/env python3
"""
Setup script for MCP Bookkeeping Server

Helps with initial setup, dependency installation, and testing.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Run a shell command with error handling."""
    print(f"📋 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        return False

def check_dependencies():
    """Check if required dependencies are available."""
    print("🔍 Checking dependencies...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Check PostgreSQL
    if run_command("which psql", "Checking PostgreSQL client"):
        print("✅ PostgreSQL client available")
    else:
        print("⚠️ PostgreSQL client not found - you may need to install it")
    
    return True

def install_dependencies():
    """Install Python dependencies."""
    requirements_file = Path(__file__).parent.parent / "requirements.txt"
    
    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    return run_command(
        f"pip install -r {requirements_file}",
        "Installing Python dependencies"
    )

def setup_environment():
    """Setup environment configuration."""
    env_example = Path(__file__).parent / ".env.example"
    env_file = Path(__file__).parent / ".env"
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    if env_example.exists():
        try:
            with open(env_example, 'r') as src, open(env_file, 'w') as dst:
                dst.write(src.read())
            print("✅ Created .env file from template")
            print("💡 Please edit .env with your database credentials")
            return True
        except Exception as e:
            print(f"❌ Failed to create .env file: {e}")
            return False
    else:
        print("❌ .env.example template not found")
        return False

def test_database_connection():
    """Test database connectivity."""
    print("🔌 Testing database connection...")
    
    # Import after potential dependency installation
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from mcp.config import get_config
        from mcp.utils.database_manager import DatabaseManager
        
        config = get_config()
        db_manager = DatabaseManager(config.database.connection_string)
        
        health = db_manager.get_database_health()
        if health.get('connected'):
            print("✅ Database connection successful")
            print(f"📊 Found {health.get('total_transactions', 0)} transactions")
            return True
        else:
            print(f"❌ Database connection failed: {health.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def main():
    """Main setup routine."""
    print("🚀 MCP Bookkeeping Server Setup")
    print("=" * 40)
    
    success = True
    
    # Step 1: Check system dependencies
    if not check_dependencies():
        success = False
    
    # Step 2: Install Python dependencies
    if success and not install_dependencies():
        success = False
    
    # Step 3: Setup environment
    if success and not setup_environment():
        success = False
    
    # Step 4: Test database (optional)
    print("\n🔧 Optional: Test database connection")
    test_db = input("Would you like to test database connection? (y/N): ").lower().strip()
    if test_db == 'y':
        test_database_connection()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 Setup completed successfully!")
        print("\n📝 Next steps:")
        print("1. Edit .env with your database credentials")
        print("2. Setup PostgreSQL database with: psql -f ../db_schema.sql")
        print("3. Start server with: python start_server.py")
    else:
        print("❌ Setup encountered some issues")
        print("Please check the errors above and try again")

if __name__ == "__main__":
    main()