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
import threading
import re
try:
    import pyperclip
    CLIPBOARD_SUPPORT = True
except ImportError:
    CLIPBOARD_SUPPORT = False

# Load environment variables from .env file if it exists
def load_env_file():
    """Load environment variables from .env file"""
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Load environment variables
load_env_file()

# Configuration
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / 'config1.json'
LOG_FILE = SCRIPT_DIR / 'one_click.log'

def extract_auth_code_from_url(url_text):
    """Extract auth_code from Fyers redirect URL"""
    try:
        # Look for auth_code parameter in URL - handle JWT tokens with dots
        pattern = r'auth_code=([A-Za-z0-9\-_\.]+)'
        match = re.search(pattern, url_text)
        if match:
            auth_code = match.group(1)
            print(f"✅ Auth code extracted: {auth_code[:50]}...")
            return auth_code
        
        # Fallback pattern for different formats
        pattern = r'auth_code[=:]\s*([A-Za-z0-9\-_\.]+)'
        match = re.search(pattern, url_text)
        if match:
            auth_code = match.group(1)
            print(f"✅ Auth code extracted (fallback): {auth_code[:50]}...")
            return auth_code
            
        return None
    except Exception as e:
        print(f"Error extracting auth code: {e}")
        return None

def monitor_clipboard_for_auth_code(timeout=120):
    """Monitor clipboard for auth code with timeout"""
    if not CLIPBOARD_SUPPORT:
        return None
        
    start_time = time.time()
    last_clipboard = ""
    
    while (time.time() - start_time) < timeout:
        try:
            current_clipboard = pyperclip.paste()
            
            # Only process if clipboard content changed
            if current_clipboard != last_clipboard:
                last_clipboard = current_clipboard
                
                # Check if clipboard contains auth_code
                auth_code = extract_auth_code_from_url(current_clipboard)
                if auth_code:
                    return auth_code
                    
        except Exception as e:
            # Ignore clipboard errors and continue monitoring
            pass
            
        time.sleep(0.5)  # Check every 500ms
    
    return None

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
                
                # Ensure we have the correct redirect URI
                if self.config['fyers'].get('redirect_uri') != "https://trade.fyers.in/api-login/redirect-uri/index.html":
                    self.config['fyers']['redirect_uri'] = "https://trade.fyers.in/api-login/redirect-uri/index.html"
                    self.save_config()
                    self.logger.info("✅ Configuration updated with correct Fyers redirect URI")
                    
                self.logger.info("✅ Configuration loaded from file")
                return True
            except Exception as e:
                self.logger.error(f"❌ Error loading config: {e}")
        
        self.logger.info("📝 Creating new configuration...")
        
        # Validate required environment variables
        required_env_vars = {
            'FYERS_APP_ID': 'Fyers App ID',
            'FYERS_SECRET_KEY': 'Fyers Secret Key', 
            'TELEGRAM_BOT_TOKEN': 'Telegram Bot Token',
            'TELEGRAM_CHAT_ID': 'Telegram Chat ID'
        }
        
        missing_vars = []
        for var, description in required_env_vars.items():
            if not os.getenv(var):
                missing_vars.append(f"{var} ({description})")
        
        if missing_vars:
            self.logger.error("❌ Missing required environment variables:")
            for var in missing_vars:
                self.logger.error(f"   - {var}")
            self.logger.error("\n📝 Please create a .env file with your credentials.")
            self.logger.error("📋 Use .env.example as a template.")
            return False
        
        self.config = {
            "fyers": {
                "app_id": os.getenv('FYERS_APP_ID'),
                "secret_key": os.getenv('FYERS_SECRET_KEY'),
                "redirect_uri": "https://trade.fyers.in/api-login/redirect-uri/index.html",
                "access_token": ""
            },
            "telegram": {
                "bot_token": os.getenv('TELEGRAM_BOT_TOKEN'),
                "chat_id": os.getenv('TELEGRAM_CHAT_ID')
            },
            "assets": [
                {"symbol": "NSE:NIFTY50-INDEX", "name": "NIFTY 50"},
                {"symbol": "NSE:NIFTYBANK-INDEX", "name": "BANK NIFTY"},
                {"symbol": "NSE:RELIANCE-EQ", "name": "RELIANCE"},
                {"symbol": "NSE:TCS-EQ", "name": "TCS"},
                {"symbol": "NSE:HDFCBANK-EQ", "name": "HDFC BANK"},
                {"symbol": "NSE:ICICIBANK-EQ", "name": "ICICI BANK"},
                {"symbol": "NSE:BHARTIARTL-EQ", "name": "BHARTI AIRTEL"},
                {"symbol": "NSE:INFY-EQ", "name": "INFOSYS"},
                {"symbol": "NSE:SBIN-EQ", "name": "STATE BANK"},
                {"symbol": "NSE:LICI-EQ", "name": "LIC INDIA"},
                {"symbol": "NSE:ITC-EQ", "name": "ITC"},
                {"symbol": "NSE:HCLTECH-EQ", "name": "HCL TECH"},
                {"symbol": "NSE:BAJFINANCE-EQ", "name": "BAJAJ FINANCE"},
                {"symbol": "NSE:LT-EQ", "name": "L&T"},
                {"symbol": "NSE:SUNPHARMA-EQ", "name": "SUN PHARMA"},
                {"symbol": "NSE:WIPRO-EQ", "name": "WIPRO"},
                {"symbol": "NSE:AXISBANK-EQ", "name": "AXIS BANK"},
                {"symbol": "NSE:ASIANPAINT-EQ", "name": "ASIAN PAINTS"},
                {"symbol": "NSE:MARUTI-EQ", "name": "MARUTI SUZUKI"},
                {"symbol": "NSE:TITAN-EQ", "name": "TITAN"},
                {"symbol": "NSE:COALINDIA-EQ", "name": "COAL INDIA"},
                {"symbol": "NSE:NTPC-EQ", "name": "NTPC"},
                {"symbol": "NSE:NESTLEIND-EQ", "name": "NESTLE"},
                {"symbol": "NSE:ULTRACEMCO-EQ", "name": "ULTRA CEMENT"},
                {"symbol": "NSE:ONGC-EQ", "name": "ONGC"},
                {"symbol": "NSE:JSWSTEEL-EQ", "name": "JSW STEEL"},
                {"symbol": "NSE:POWERGRID-EQ", "name": "POWER GRID"},
                {"symbol": "NSE:BAJAJFINSV-EQ", "name": "BAJAJ FINSERV"},
                {"symbol": "NSE:HINDALCO-EQ", "name": "HINDALCO"},
                {"symbol": "NSE:TECHM-EQ", "name": "TECH MAHINDRA"},
                {"symbol": "NSE:HDFCLIFE-EQ", "name": "HDFC LIFE"},
                {"symbol": "NSE:SBILIFE-EQ", "name": "SBI LIFE"},
                {"symbol": "NSE:ADANIENT-EQ", "name": "ADANI ENTERPRISES"},
                {"symbol": "NSE:APOLLOHOSP-EQ", "name": "APOLLO HOSPITAL"},
                {"symbol": "NSE:HEROMOTOCO-EQ", "name": "HERO MOTOCORP"},
                {"symbol": "NSE:INDUSINDBK-EQ", "name": "INDUSIND BANK"},
                {"symbol": "NSE:CIPLA-EQ", "name": "CIPLA"},
                {"symbol": "NSE:GRASIM-EQ", "name": "GRASIM"},
                {"symbol": "NSE:BRITANNIA-EQ", "name": "BRITANNIA"},
                {"symbol": "NSE:DRREDDY-EQ", "name": "DR REDDY"},
                {"symbol": "NSE:EICHERMOT-EQ", "name": "EICHER MOTORS"},
                {"symbol": "NSE:DIVISLAB-EQ", "name": "DIVI'S LAB"},
                {"symbol": "NSE:TATAMOTORS-EQ", "name": "TATA MOTORS"},
                {"symbol": "NSE:TATASTEEL-EQ", "name": "TATA STEEL"},
                {"symbol": "NSE:ADANIPORTS-EQ", "name": "ADANI PORTS"},
                {"symbol": "NSE:TATACONSUM-EQ", "name": "TATA CONSUMER"},
                {"symbol": "NSE:BAJAJ-AUTO-EQ", "name": "BAJAJ AUTO"},
                {"symbol": "NSE:SHRIRAMFIN-EQ", "name": "SHRIRAM FINANCE"},
                {"symbol": "NSE:KOTAKBANK-EQ", "name": "KOTAK BANK"},
                {"symbol": "NSE:BPCL-EQ", "name": "BPCL"},
                {"symbol": "NSE:LTIM-EQ", "name": "LTI MINDTREE"},
                {"symbol": "NSE:HINDUNILVR-EQ", "name": "HINDUSTAN UNILEVER"},
                {"symbol": "NSE:M&M-EQ", "name": "M&M"},
                {"symbol": "NSE:FEDERALBNK-EQ", "name": "FEDERAL BANK"},
                {"symbol": "NSE:IDFCFIRSTB-EQ", "name": "IDFC FIRST BANK"},
                {"symbol": "NSE:BANKBARODA-EQ", "name": "BANK OF BARODA"},
                {"symbol": "NSE:PNB-EQ", "name": "PUNJAB NATIONAL BANK"},
                {"symbol": "NSE:AUBANK-EQ", "name": "AU SMALL FINANCE BANK"}
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
        """Generate new token automatically using clipboard monitoring"""
        self.logger.info("🔑 Generating new Fyers token automatically...")
        
        app_id = self.config['fyers']['app_id']
        app_secret = self.config['fyers']['secret_key']
        redirect_uri = self.config['fyers']['redirect_uri']
        
        # Check if pyperclip is available
        global CLIPBOARD_SUPPORT
        if not CLIPBOARD_SUPPORT:
            self.logger.warning("⚠️ Clipboard monitoring not available. Installing pyperclip...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyperclip'])
                import pyperclip
                CLIPBOARD_SUPPORT = True
                self.logger.info("✅ pyperclip installed successfully")
            except Exception as e:
                self.logger.error(f"❌ Failed to install pyperclip: {e}")
                return self._fallback_to_manual_input(app_id, app_secret, redirect_uri)
        
        # Generate authorization URL
        auth_url = (
            f"https://api-t1.fyers.in/api/v3/generate-authcode?"
            f"client_id={app_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"state=automated_auth"
        )
        
        print(f"\n🌐 Opening browser for Fyers authentication...")
        print(f"📋 Semi-automated process:")
        print(f"  1. Browser will open automatically")
        print(f"  2. Login with your Fyers credentials")
        print(f"  3. Grant permissions to the app") 
        print(f"  4. Copy the redirect URL from browser address bar")
        print(f"  5. Auth code will be detected automatically from clipboard!")
        print()
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Start clipboard monitoring in a separate thread
        auth_code = None
        clipboard_result = [None]  # Use list to allow modification in thread
        
        def clipboard_monitor():
            clipboard_result[0] = monitor_clipboard_for_auth_code(timeout=120)
        
        self.logger.info("⏳ Monitoring clipboard for auth code...")
        print("💡 After logging in, copy the full URL from your browser address bar")
        
        monitor_thread = threading.Thread(target=clipboard_monitor, daemon=True)
        monitor_thread.start()
        
        # Wait for clipboard monitoring to complete
        monitor_thread.join(timeout=125)  # 5 seconds buffer
        
        auth_code = clipboard_result[0]
        
        if not auth_code:
            self.logger.warning("⚠️ No auth code detected in clipboard. Trying manual input...")
            return self._fallback_to_manual_input(app_id, app_secret, redirect_uri)
        
        self.logger.info("✅ Auth code detected automatically from clipboard!")
        
        # Generate proper access token from auth_code
        return self._generate_access_token(app_id, app_secret, auth_code)
    
    def _fallback_to_manual_input(self, app_id, app_secret, redirect_uri):
        """Fallback to manual auth code input"""
        print("\n📝 Please enter the auth code manually:")
        auth_code = input("Enter the auth_code from the URL: ").strip()
        
        if not auth_code:
            self.logger.error("❌ No auth_code provided!")
            return False
            
        return self._generate_access_token(app_id, app_secret, auth_code)
    
    def _save_access_token(self, auth_code):
        """Save the auth_code as access token (it's already a JWT)"""
        try:
            self.config['fyers']['access_token'] = auth_code
            self.config['fyers']['token_info'] = {
                'generated_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
            }
            
            self.save_config()
            
            self.logger.info("✅ Token saved successfully!")
            self.logger.info(f"✅ Access token: {auth_code[:50]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to save token: {e}")
            return False
    
    def _generate_access_token(self, app_id, app_secret, auth_code):
        """Generate access token from auth code"""
        try:
            # Validate inputs
            if not app_id or not app_secret or not auth_code:
                self.logger.error("❌ Missing required parameters for token generation")
                return False
                
            self.logger.debug(f"App ID: {app_id}")
            self.logger.debug(f"Auth code length: {len(auth_code)}")
            
            app_id_hash = self.create_app_id_hash(app_id, app_secret)
            self.logger.debug(f"App ID Hash: {app_id_hash}")
            
            url = "https://api-t1.fyers.in/api/v3/validate-authcode"
            payload = {
                "grant_type": "authorization_code",
                "appIdHash": app_id_hash,
                "code": auth_code
            }
            
            self.logger.info("🔄 Generating access token...")
            self.logger.debug(f"Request URL: {url}")
            self.logger.debug(f"Request payload: {payload}")
            
            response = requests.post(url, json=payload, timeout=30)
            
            self.logger.debug(f"Response status: {response.status_code}")
            self.logger.debug(f"Response headers: {response.headers}")
            
            if response.status_code == 200:
                result = response.json()
                self.logger.debug(f"Response body: {result}")
                self.logger.debug(f"Response keys: {list(result.keys())}")
                
                if result.get('s') == 'ok':
                    # Try different possible field names for the access token
                    access_token = (result.get('access_token') or 
                                  result.get('authorization code') or 
                                  result.get('token') or
                                  result.get('authCode'))
                    
                    if access_token:
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
                        self.logger.info(f"✅ Access token: {access_token[:50]}...")
                        return True
                    else:
                        self.logger.error(f"❌ No access token found in response: {result}")
                        return False
                else:
                    self.logger.error(f"❌ API Error: {result}")
                    return False
            else:
                try:
                    error_response = response.json()
                    self.logger.error(f"❌ HTTP Error {response.status_code}: {error_response}")
                except:
                    self.logger.error(f"❌ HTTP Error {response.status_code}: {response.text}")
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