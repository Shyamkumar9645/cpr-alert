#!/usr/bin/env python3
"""
One-time setup script for automated Fyers token management.
Run this script ONCE to set up automated token renewal.
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.auto_token_manager import AutoTokenManager

def main():
    print("\n" + "="*70)
    print("🤖 AUTOMATED FYERS TOKEN SETUP")
    print("="*70)
    print("This is a ONE-TIME setup to enable automated token renewal.")
    print("After this setup, your bot will automatically renew tokens daily.")
    print("You will NEVER need to manually generate tokens again!")
    print("="*70)

    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("\n❌ ERROR: .env file not found!")
        print("Please run 'python scripts/setup_security.py' first.")
        return False

    # Setup logging
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/token_setup.log'),
            logging.StreamHandler()
        ]
    )

    try:
        # Initialize token manager
        token_manager = AutoTokenManager()

        # Check if we already have automated setup
        if token_manager.stored_auth_code:
            print("\n✅ Automated token system already configured!")
            print("Testing current setup...")

            token = token_manager.get_valid_token()
            if token:
                print("✅ Automated token generation is working perfectly!")
                print("✅ Your bot is ready for automated operation!")
                return True
            else:
                print("⚠️  Existing setup needs refresh. Proceeding with new setup...")

        # Run interactive setup
        print("\n🔧 Starting automated token setup...")
        token = token_manager.interactive_token_setup()

        if token:
            print("\n" + "="*70)
            print("🎉 SUCCESS! AUTOMATED TOKEN SYSTEM IS NOW ACTIVE!")
            print("="*70)
            print("✅ Your bot will now automatically renew Fyers tokens daily")
            print("✅ No more manual token generation required!")
            print("✅ The bot can run unattended for months!")
            print("\nNext steps:")
            print("1. Start your bot: ./market_scheduler.sh start")
            print("2. Set up cron job for market hours automation")
            print("3. Enjoy hands-free trading bot operation!")
            print("="*70)
            return True
        else:
            print("\n❌ Setup failed. Please check your credentials and try again.")
            return False

    except Exception as e:
        print(f"\n❌ Setup error: {e}")
        logging.error(f"Token setup error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)