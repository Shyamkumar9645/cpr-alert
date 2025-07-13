#!/usr/bin/env python3
"""
Security Setup Script for CPR Stock Alert System
This script helps set up environment variables securely.
"""

import os
import getpass
from pathlib import Path

def create_env_file():
    """Create .env file with user input"""
    env_file = Path('.env')
    
    if env_file.exists():
        overwrite = input("⚠️ .env file already exists. Overwrite? (y/N): ")
        if overwrite.lower() != 'y':
            print("❌ Setup cancelled.")
            return False
    
    print("🔐 CPR Stock Alert System - Security Setup")
    print("=" * 50)
    print("Please enter your credentials (they will be stored securely in .env file)")
    print()
    
    # Get Fyers credentials
    print("📊 Fyers API Credentials:")
    fyers_app_id = input("Fyers App ID: ").strip()
    fyers_secret = getpass.getpass("Fyers Secret Key (hidden input): ").strip()
    
    print()
    
    # Get Telegram credentials
    print("📱 Telegram Bot Credentials:")
    tg_token = input("Telegram Bot Token: ").strip()
    tg_chat_id = input("Telegram Chat ID: ").strip()
    
    print()
    
    # Validate inputs
    if not all([fyers_app_id, fyers_secret, tg_token, tg_chat_id]):
        print("❌ All fields are required!")
        return False
    
    # Create .env file
    env_content = f"""# CPR Stock Alert System - Environment Variables
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# Fyers API Configuration
FYERS_APP_ID={fyers_app_id}
FYERS_SECRET_KEY={fyers_secret}

# Telegram Bot Configuration  
TELEGRAM_BOT_TOKEN={tg_token}
TELEGRAM_CHAT_ID={tg_chat_id}

# Optional: Alert Settings
CHECK_INTERVAL_SECONDS=60
TOLERANCE_PERCENT=0.15
COOLDOWN_MINUTES=30
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        # Set secure permissions
        os.chmod(env_file, 0o600)
        
        print("✅ Environment file created successfully!")
        print("🔒 File permissions set to 600 (owner read/write only)")
        print()
        print("Next steps:")
        print("1. Run: python one_click_start.py")
        print("2. Follow the authentication process")
        print("3. Your bot will start monitoring stocks!")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

if __name__ == "__main__":
    from datetime import datetime
    create_env_file()