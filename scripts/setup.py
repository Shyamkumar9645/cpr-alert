from pathlib import Path

def setup_environment_file():
    """
    Creates a .env file if it doesn't exist and prompts the user for credentials.
    """
    env_file = Path(__file__).parent.parent / '.env'

    if env_file.exists():
        print(f".env file already exists at: {env_file.resolve()}")
        overwrite = input("Do you want to overwrite it? (yes/no): ").lower()
        if overwrite not in ['yes', 'y']:
            print("Setup cancelled.")
            return

    print("--- Secure Setup for API Credentials ---")
    print("Please enter your credentials. They will be stored locally in a .env file.")

    fyers_app_id = input("Enter your Fyers App ID: ")
    fyers_secret_key = input("Enter your Fyers Secret Key: ")
    fyers_redirect_uri = input("Enter your Fyers Redirect URI (e.g., https://www.google.com/): ")
    telegram_bot_token = input("Enter your Telegram Bot Token: ")
    telegram_chat_id = input("Enter your Telegram Chat ID: ")

    env_content = f"""# Fyers API Credentials
FYERS_APP_ID="{fyers_app_id}"
FYERS_SECRET_KEY="{fyers_secret_key}"
FYERS_REDIRECT_URI="{fyers_redirect_uri}"
FYERS_ACCESS_TOKEN=""

# Telegram Bot Credentials
TELEGRAM_BOT_TOKEN="{telegram_bot_token}"
TELEGRAM_CHAT_ID="{telegram_chat_id}"
"""

    with open(env_file, 'w') as f:
        f.write(env_content)

    print(f"\n✅ Successfully created .env file at {env_file.resolve()}")
    print("\nNext steps:")
    print("1. Run 'pip install -r requirements.txt' to install dependencies.")
    print("2. Run 'python scripts/generate_token.py' to get your Fyers access token.")

if __name__ == "__main__":
    setup_environment_file()