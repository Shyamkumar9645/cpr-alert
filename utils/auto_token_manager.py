import os
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from fyers_apiv3 import fyersModel
from dotenv import load_dotenv, set_key

class AutoTokenManager:
    """
    Automated token management for Fyers API.
    This class handles token generation, validation, and renewal.
    """

    def __init__(self, config_path: str = ".env"):
        self.config_path = Path(config_path)
        self.logger = logging.getLogger(__name__)
        self.token_file = Path("fyers_token.json")
        load_dotenv(self.config_path)

        self.app_id = os.getenv('FYERS_APP_ID')
        self.secret_key = os.getenv('FYERS_SECRET_KEY')
        self.redirect_uri = os.getenv('FYERS_REDIRECT_URI')
        self.stored_auth_code = os.getenv('FYERS_AUTH_CODE')  # We'll store this for reuse

        if not all([self.app_id, self.secret_key, self.redirect_uri]):
            raise ValueError("Missing required Fyers credentials in .env file")

    def save_token_data(self, token_data: Dict[str, Any]) -> None:
        """Save token data with expiration time."""
        token_info = {
            'access_token': token_data.get('access_token'),
            'refresh_token': token_data.get('refresh_token'),  # If available
            'expires_at': (datetime.now() + timedelta(hours=23)).isoformat(),  # Expire in 23 hours
            'generated_at': datetime.now().isoformat()
        }

        with open(self.token_file, 'w') as f:
            json.dump(token_info, f, indent=2)

        # Also update .env file
        set_key(self.config_path, 'FYERS_ACCESS_TOKEN', token_data.get('access_token'))
        self.logger.info("Token data saved successfully")

    def load_token_data(self) -> Optional[Dict[str, Any]]:
        """Load token data from file."""
        if not self.token_file.exists():
            return None

        try:
            with open(self.token_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def is_token_valid(self, token_data: Dict[str, Any]) -> bool:
        """Check if token is still valid."""
        try:
            expires_at = datetime.fromisoformat(token_data.get('expires_at', ''))
            # Consider token expired if less than 1 hour remaining
            return datetime.now() < (expires_at - timedelta(hours=1))
        except (ValueError, TypeError):
            return False

    def test_token_validity(self, access_token: str) -> bool:
        """Test if token works by making a simple API call."""
        try:
            fyers = fyersModel.FyersModel(
                client_id=self.app_id,
                token=access_token,
                log_path="logs/"
            )

            # Test with a simple API call (get profile)
            response = fyers.get_profile()
            return response and response.get('s') == 'ok'
        except Exception as e:
            self.logger.warning(f"Token validation failed: {e}")
            return False

    def generate_token_with_stored_auth(self) -> Optional[str]:
        """Generate token using stored auth code."""
        if not self.stored_auth_code:
            self.logger.warning("No stored auth code available")
            return None

        try:
            session = fyersModel.SessionModel(
                client_id=self.app_id,
                secret_key=self.secret_key,
                redirect_uri=self.redirect_uri,
                response_type="code",
                grant_type="authorization_code"
            )

            session.set_token(self.stored_auth_code)
            response = session.generate_token()

            if response and response.get('s') == 'ok':
                self.save_token_data(response)
                self.logger.info("Token generated successfully using stored auth code")
                return response['access_token']
            else:
                self.logger.error(f"Token generation failed: {response}")
                return None

        except Exception as e:
            self.logger.error(f"Error generating token with stored auth: {e}")
            return None

    def interactive_token_setup(self) -> Optional[str]:
        """Interactive token setup - only run once to get auth code."""
        self.logger.info("Setting up automated token generation...")

        session = fyersModel.SessionModel(
            client_id=self.app_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type="code",
            grant_type="authorization_code"
        )

        auth_url = session.generate_authcode()

        print("\n" + "="*60)
        print("🔐 AUTOMATED TOKEN SETUP")
        print("="*60)
        print(f"1. Open this URL in your browser:")
        print(f"   {auth_url}")
        print("\n2. After login, you'll be redirected to your redirect URI.")
        print("3. Copy the ENTIRE redirected URL and paste it below.")
        print("4. This setup is ONE-TIME only - the bot will auto-renew tokens afterward.")
        print("="*60)

        try:
            import webbrowser
            webbrowser.open(auth_url)
        except:
            pass

        redirect_url = input("\nPaste the full redirected URL here: ").strip()

        try:
            # Extract auth code from URL
            auth_code = redirect_url.split('auth_code=')[1].split('&')[0]

            # Store auth code in .env for future use
            set_key(self.config_path, 'FYERS_AUTH_CODE', auth_code)
            self.stored_auth_code = auth_code

            # Generate initial token
            session.set_token(auth_code)
            response = session.generate_token()

            if response and response.get('s') == 'ok':
                self.save_token_data(response)

                print("\n" + "="*60)
                print("✅ AUTOMATED TOKEN SETUP COMPLETE!")
                print("✅ Your bot will now automatically renew tokens daily.")
                print("✅ No more manual intervention required!")
                print("="*60)

                return response['access_token']
            else:
                print(f"\n❌ Token generation failed: {response}")
                return None

        except Exception as e:
            print(f"\n❌ Error during setup: {e}")
            return None

    def get_valid_token(self) -> Optional[str]:
        """Get a valid access token, renewing if necessary."""
        # Check if we have stored token data
        token_data = self.load_token_data()

        if token_data and self.is_token_valid(token_data):
            access_token = token_data['access_token']

            # Double-check with API call
            if self.test_token_validity(access_token):
                self.logger.info("Using existing valid token")
                return access_token
            else:
                self.logger.info("Stored token failed API test, generating new one")

        # Try to generate new token using stored auth code
        if self.stored_auth_code:
            new_token = self.generate_token_with_stored_auth()
            if new_token and self.test_token_validity(new_token):
                return new_token

        # If all automated methods fail, we need interactive setup
        self.logger.warning("Automated token generation failed. Running interactive setup...")
        return self.interactive_token_setup()

    def cleanup_old_tokens(self):
        """Clean up old token files."""
        if self.token_file.exists():
            try:
                token_data = self.load_token_data()
                if token_data and not self.is_token_valid(token_data):
                    self.logger.info("Cleaning up expired token file")
                    self.token_file.unlink()
            except:
                pass

# Convenience function for easy integration
def get_auto_token() -> Optional[str]:
    """Get a valid Fyers access token automatically."""
    try:
        manager = AutoTokenManager()
        return manager.get_valid_token()
    except Exception as e:
        logging.error(f"Auto token generation failed: {e}")
        return None

if __name__ == "__main__":
    # Test the auto token manager
    logging.basicConfig(level=logging.INFO)
    manager = AutoTokenManager()
    token = manager.get_valid_token()

    if token:
        print(f"✅ Successfully obtained token: {token[:20]}...")
    else:
        print("❌ Failed to obtain token")