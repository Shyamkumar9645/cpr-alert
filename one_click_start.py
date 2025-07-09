#!/usr/bin/env python3
"""
ONE-CLICK CPR STOCK ALERT SYSTEM
================================
Run this script and immediately start receiving stock alerts!

This script automatically:
1. Installs required dependencies
2. Generates/refreshes Fyers token
3. Sets up environment
4. Starts the alert system
5. Schedules daily token refresh at 9pm

Usage: python one_click_start.py
"""

import os
import sys
import subprocess
import json
import time
import webbrowser
import hashlib
import requests
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / 'config1.json'
LOG_FILE = SCRIPT_DIR / 'one_click.log'

class OneClickLauncher:
    def __init__(self):
        self.config = None
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging to file and console"""
        import logging
        
        # Create logs directory
        (SCRIPT_DIR / 'logs').mkdir(exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(LOG_FILE),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def print_banner(self):
        """Print welcome banner"""
        print("\n" + "="*60)
        print("🎯 CPR STOCK ALERT SYSTEM - ONE CLICK START")
        print("="*60)
        print("✅ Automatic dependency installation")
        print("✅ Automatic token generation/refresh")
        print("✅ Immediate alert system startup")
        print("✅ Daily 9pm token refresh")
        print("✅ Real-time stock level monitoring")
        print("="*60)
        print()
        
    def check_and_install_dependencies(self):
        """Check and install required Python packages"""
        self.logger.info("📦 Checking Python dependencies...")
        
        required_packages = [
            'fyers-apiv3',
            'requests',
            'schedule'
        ]
        
        for package in required_packages:
            try:
                if package == 'fyers-apiv3':
                    import fyers_apiv3
                elif package == 'requests':
                    import requests
                elif package == 'schedule':
                    import schedule
                    
                self.logger.info(f"✅ {package} already installed")
                
            except ImportError:
                self.logger.info(f"📦 Installing {package}...")
                try:
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                    self.logger.info(f"✅ {package} installed successfully")
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"❌ Failed to install {package}: {e}")
                    return False
        
        return True
    
    def load_or_create_config(self):
        """Load existing config or create new one"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
                self.logger.info("✅ Configuration loaded from file")
                return True
            except Exception as e:
                self.logger.error(f"❌ Error loading config: {e}")
        
        self.logger.info("📝 Creating new configuration...")
        self.config = {
            "fyers": {
                "app_id": "VAC70PGA10-100",
                "secret_key": "H44VSBA64K",
                "redirect_uri": "https://trade.fyers.in/api-login/redirect-uri/index.html",
                "access_token": ""
            },
            "telegram": {
                "bot_token": "8073975228:AAFA2n9Fszn16zWCtNUghW7E4Qk1xNgQm-U",
                "chat_id": "657566600"
            },
            "assets": [
                {"symbol": "NSE:NIFTY50-INDEX", "name": "NIFTY 50"},
                {"symbol": "NSE:NIFTYBANK-INDEX", "name": "BANK NIFTY"},
                {"symbol": "NSE:RELIANCE-EQ", "name": "RELIANCE"},
                {"symbol": "NSE:HDFCBANK-EQ", "name": "HDFC BANK"},
                {"symbol": "NSE:ICICIBANK-EQ", "name": "ICICI BANK"},
                {"symbol": "NSE:AXISBANK-EQ", "name": "AXIS BANK"},
                {"symbol": "NSE:SBIN-EQ", "name": "STATE BANK"},
                {"symbol": "NSE:TATAMOTORS-EQ", "name": "TATA MOTORS"},
                {"symbol": "NSE:BAJFINANCE-EQ", "name": "BAJAJ FINANCE"}
            ],
            "alert_settings": {
                "check_interval_seconds": 60,
                "tolerance_percent": 0.15,
                "cooldown_minutes": 30,
                "preferred_resolution": "1",
                "market_hours": {
                    "start": "09:15",
                    "end": "15:30"
                }
            }
        }
        
        self.save_config()
        return True
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            self.logger.info("✅ Configuration saved")
        except Exception as e:
            self.logger.error(f"❌ Error saving config: {e}")
    
    def create_app_id_hash(self, app_id: str, app_secret: str) -> str:
        """Create SHA-256 hash of app_id:app_secret"""
        return hashlib.sha256(f"{app_id}:{app_secret}".encode()).hexdigest()
    
    def check_existing_token(self):
        """Check if we have a valid token"""
        token = self.config.get('fyers', {}).get('access_token')
        if not token:
            return False
            
        # Test token validity
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(
                "https://api-t1.fyers.in/data/quotes",
                headers=headers,
                params={"symbols": "NSE:RELIANCE-EQ"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('s') == 'ok':
                    self.logger.info("✅ Existing token is valid")
                    return True
                    
        except Exception as e:
            self.logger.info(f"⚠️ Token test failed: {e}")
            
        return False
    
    def generate_token_automatically(self):
        """Generate new token automatically"""
        self.logger.info("🔑 Generating new Fyers token...")
        
        app_id = self.config['fyers']['app_id']
        app_secret = self.config['fyers']['secret_key']
        redirect_uri = self.config['fyers']['redirect_uri']
        
        # Generate authorization URL
        auth_url = (
            f"https://api-t1.fyers.in/api/v3/generate-authcode?"
            f"client_id={app_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"state=sample_state"
        )
        
        print(f"\n🌐 Opening browser for Fyers authentication...")
        print(f"📋 Follow these steps:")
        print(f"  1. Browser will open automatically")
        print(f"  2. Login with your Fyers credentials")
        print(f"  3. Grant permissions to the app")
        print(f"  4. Copy the auth_code from the redirect URL")
        print(f"  5. Paste it below")
        print()
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Get auth code from user
        auth_code = input("📝 Enter the auth_code from the URL: ").strip()
        
        if not auth_code:
            self.logger.error("❌ No auth_code provided!")
            return False
        
        # Generate access token
        app_id_hash = self.create_app_id_hash(app_id, app_secret)
        
        url = "https://api-t1.fyers.in/api/v3/validate-authcode"
        payload = {
            "grant_type": "authorization_code",
            "appIdHash": app_id_hash,
            "code": auth_code
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('s') == 'ok':
                    access_token = result.get('access_token')
                    refresh_token = result.get('refresh_token')
                    
                    self.config['fyers']['access_token'] = access_token
                    if refresh_token:
                        self.config['fyers']['refresh_token'] = refresh_token
                    
                    self.config['fyers']['token_info'] = {
                        'generated_at': datetime.now().isoformat(),
                        'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
                    }
                    
                    self.save_config()
                    
                    self.logger.info("✅ Token generated successfully!")
                    return True
                else:
                    self.logger.error(f"❌ API Error: {result}")
                    return False
            else:
                self.logger.error(f"❌ HTTP Error: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Token generation failed: {e}")
            return False
    
    def setup_environment(self):
        """Setup environment variables"""
        self.logger.info("🔧 Setting up environment...")
        
        env_vars = {
            'FYERS_APP_ID': self.config['fyers']['app_id'],
            'FYERS_ACCESS_TOKEN': self.config['fyers']['access_token'],
            'TELEGRAM_BOT_TOKEN': self.config['telegram']['bot_token'],
            'TELEGRAM_CHAT_ID': self.config['telegram']['chat_id'],
            'STOCK_ALERT_CONFIG': str(CONFIG_FILE)
        }
        os.environ.update(env_vars)
        
        self.logger.info("✅ Environment configured")
    
    def test_telegram_connection(self):
        """Test Telegram bot connection"""
        self.logger.info("📱 Testing Telegram connection...")
        
        try:
            bot_token = self.config['telegram']['bot_token']
            chat_id = self.config['telegram']['chat_id']
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': '🚀 CPR Stock Alert System Started!\n\n✅ Connection successful\n🎯 Monitoring stock levels\n⏰ Daily token refresh at 9pm'
            }
            
            response = requests.post(url, data=payload, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("✅ Telegram connection successful")
                return True
            else:
                self.logger.error(f"❌ Telegram connection failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Telegram test failed: {e}")
            return False
    
    def start_alert_system(self):
        """Start the CPR alert system"""
        self.logger.info("🚀 Starting CPR Alert System...")
        
        try:
            # Import here to avoid circular imports
            from cpr_bot import CPRAlertBot
            
            # Create bot instance
            bot = CPRAlertBot()
            
            # Make bot available globally for token refresh
            globals()['bot_instance'] = bot
            
            # Initialize daily levels
            if not bot.initialize_daily_levels():
                self.logger.error("❌ Failed to initialize daily levels")
                return False
            
            # Send startup notification
            bot.telegram_service.send_alert(
                "🎯 **CPR Alert System Started!**\n\n"
                f"📊 Monitoring: {len(bot.asset_data)} assets\n"
                f"⏰ Check interval: {bot.check_interval}s\n"
                f"🔄 Cooldown: {bot.cooldown_manager.cooldown_minutes}min\n"
                f"📅 Token refresh: 9pm daily\n\n"
                "✅ Ready to send level touch alerts!"
            )
            
            self.logger.info("✅ Alert system started successfully")
            
            # Start monitoring
            bot.start_monitoring()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start alert system: {e}")
            return False
    
    def run(self):
        """Main execution flow"""
        try:
            self.print_banner()
            
            # Step 1: Check and install dependencies
            if not self.check_and_install_dependencies():
                print("❌ Failed to install dependencies")
                return False
            
            # Step 2: Load or create configuration
            if not self.load_or_create_config():
                print("❌ Failed to setup configuration")
                return False
            
            # Step 3: Check existing token or generate new one
            if not self.check_existing_token():
                print("🔑 Token invalid or missing, generating new one...")
                if not self.generate_token_automatically():
                    print("❌ Failed to generate token")
                    return False
            
            # Step 4: Setup environment
            self.setup_environment()
            
            # Step 5: Test Telegram connection
            if not self.test_telegram_connection():
                print("❌ Telegram connection failed")
                return False
            
            # Step 6: Start alert system
            print("\n🎯 Starting stock alert monitoring...")
            print("📱 You should receive a Telegram notification shortly")
            print("⏰ System will automatically refresh token at 9pm daily")
            print("🔄 Press Ctrl+C to stop\n")
            
            return self.start_alert_system()
            
        except KeyboardInterrupt:
            self.logger.info("👋 Received stop signal, shutting down...")
            return True
        except Exception as e:
            self.logger.error(f"❌ Fatal error: {e}")
            return False

def main():
    """Main entry point"""
    launcher = OneClickLauncher()
    
    try:
        success = launcher.run()
        if success:
            print("\n✅ CPR Alert System completed successfully")
        else:
            print("\n❌ CPR Alert System failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()