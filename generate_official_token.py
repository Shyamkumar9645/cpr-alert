#!/usr/bin/env python3

"""
Simplified Fyers API v3 Access Token Generator
"""

import requests
import json
import hashlib
import webbrowser
import os
import time
from datetime import datetime, timedelta

def load_config():
    """Load configuration from config file"""
    config_path = os.environ.get('STOCK_ALERT_CONFIG', 'config1.json')
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return None
    
    with open(config_path, 'r') as f:
        return json.load(f)

def create_app_id_hash(app_id: str, app_secret: str) -> str:
    """Create SHA-256 hash of app_id:app_secret"""
    return hashlib.sha256(f"{app_id}:{app_secret}".encode()).hexdigest()

def generate_fyers_access_token():
    """Generate Fyers access token using OAuth2 flow"""
    print("🔑 FYERS API v3 ACCESS TOKEN GENERATOR")
    print("=" * 50)
    
    config = load_config()
    if not config:
        return None
    
    app_id = config['fyers']['app_id']
    app_secret = config['fyers']['secret_key']
    redirect_uri = config['fyers']['redirect_uri']
    
    print(f"📱 App ID: {app_id}")
    print(f"🔐 App Secret: {app_secret[:10]}...")
    print(f"🔗 Redirect URI: {redirect_uri}")
    
    if app_id == "YOUR_FYERS_APP_ID" or app_secret == "YOUR_FYERS_SECRET_KEY":
        print("\n❌ ERROR: Please update your config file with actual Fyers API credentials")
        return None
    
    try:
        print(f"\n🚀 STEP 1: Generating authorization URL...")
        
        auth_url = (
            f"https://api-t1.fyers.in/api/v3/generate-authcode?"
            f"client_id={app_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"state=sample_state"
        )
        
        print(f"✅ Authorization URL generated!")
        print(f"🔗 URL: {auth_url}")
        
        print(f"\n🌐 STEP 2: Opening browser for authentication...")
        webbrowser.open(auth_url)
        
        print(f"\n⌨️  STEP 3: Enter the authorization code")
        auth_code = input("📝 Enter the auth_code from the URL: ").strip()
        
        if not auth_code:
            print("❌ No auth_code provided!")
            return None
        
        print(f"\n🔄 STEP 4: Generating access token...")
        
        app_id_hash = create_app_id_hash(app_id, app_secret)
        print(f"🔐 Created appIdHash: {app_id_hash[:20]}...")
        
        url = "https://api-t1.fyers.in/api/v3/validate-authcode"
        payload = {
            "grant_type": "authorization_code",
            "appIdHash": app_id_hash,
            "code": auth_code
        }
        
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('s') == 'ok':
                access_token = result['access_token']
                refresh_token = result.get('refresh_token')
                
                print(f"✅ Access token generated successfully!")
                print(f"🎫 Access Token: {access_token[:30]}...{access_token[-10:]}")
                
                print(f"\n💾 STEP 5: Updating config file...")
                config['fyers']['access_token'] = access_token
                if refresh_token:
                    config['fyers']['refresh_token'] = refresh_token
                
                config_path = os.environ.get('STOCK_ALERT_CONFIG', 'config1.json')
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                
                print(f"✅ Config file updated: {config_path}")
                
                print(f"\n🧪 STEP 6: Testing the access token...")
                test_result = test_access_token(access_token)
                
                if test_result:
                    print(f"\n🎉 SUCCESS! Your access token is working!")
                    print(f"✅ You can now run your stock alert system")
                    return access_token
                else:
                    print(f"\n⚠️  Token generated but test failed. Please try again.")
                    return None
            else:
                print(f"❌ API Error: {result}")
                return None
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error generating access token: {e}")
        return None

def test_access_token(access_token: str) -> bool:
    """Test if the access token works with Fyers API"""
    url = "https://api-t1.fyers.in/data/quotes"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"symbols": "NSE:RELIANCE-EQ"}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('s') == 'ok':
                quotes = result.get('d', {})
                if 'NSE:RELIANCE-EQ' in quotes:
                    quote_data = quotes['NSE:RELIANCE-EQ']
                    ltp = quote_data.get('v', {}).get('lp', 'N/A')
                    print(f"   ✅ Token works! NSE:RELIANCE-EQ: ₹{ltp}")
                    return True
                else:
                    print(f"   ⚠️  No quote data in response")
            else:
                print(f"   ⚠️  API returned error: {result.get('message', 'Unknown')}")
        
        print(f"   ❌ Test failed: {response.status_code}")
        
        print(f"   🔄 Trying alternative auth format...")
        alt_headers = {"Authorization": access_token}
        alt_response = requests.get(url, headers=alt_headers, params=params, timeout=10)
        
        if alt_response.status_code == 200:
            alt_result = alt_response.json()
            if alt_result.get('s') == 'ok':
                print(f"   ✅ Alternative format works!")
                return True
        
        print(f"   ❌ Alternative format also failed: {alt_response.status_code}")
        return False
        
    except Exception as e:
        print(f"   ❌ Test error: {e}")
        return False

def simple_token_refresh(config):
    """Simple token refresh using stored refresh token"""
    refresh_token = config.get('fyers', {}).get('refresh_token')
    
    if not refresh_token:
        return None
        
    app_id = config['fyers']['app_id']
    app_secret = config['fyers']['secret_key']
    app_id_hash = create_app_id_hash(app_id, app_secret)
    
    url = "https://api-t1.fyers.in/api/v3/refresh-token"
    payload = {
        "refresh_token": refresh_token,
        "appIdHash": app_id_hash,
        "grant_type": "refresh_token"
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('s') == 'ok':
            new_token = result.get('access_token')
            new_refresh_token = result.get('refresh_token')
            
            config['fyers']['access_token'] = new_token
            if new_refresh_token:
                config['fyers']['refresh_token'] = new_refresh_token
            
            return new_token
    
    return None

def main():
    """Main function"""
    print("Fyers API Access Token Generator")
    print("=" * 40)
    
    config = load_config()
    if not config:
        print("❌ Config file issue. Please check your setup.")
        return
    
    app_id = config.get('fyers', {}).get('app_id', '')
    app_secret = config.get('fyers', {}).get('secret_key', '')
    
    if app_id.startswith('YOUR_') or app_secret.startswith('YOUR_'):
        print("\n❌ SETUP REQUIRED:")
        print("1. Visit: https://myapi.fyers.in/dashboard/")
        print("2. Create a new app")
        print("3. Copy App ID and Secret Key")
        print("4. Update your config file with real values")
        return
    
    # Try silent refresh first
    if len(os.sys.argv) > 1 and os.sys.argv[1] == "--silent":
        new_token = simple_token_refresh(config)
        if new_token:
            print("✅ Silent token refresh successful")
            return new_token
        else:
            print("❌ Silent refresh failed, falling back to manual generation")
    
    access_token = generate_fyers_access_token()
    
    if access_token:
        print(f"\n🎯 NEXT STEPS:")
        print(f"1. ✅ Access token is now in your config file")
        print(f"2. 🚀 Run your stock alert system: python cpr_bot.py")
        print(f"3. 📱 Check Telegram for alerts!")
    else:
        print(f"\n❌ Token generation failed. Please check your credentials and try again.")

if __name__ == "__main__":
    main()