import sys
import os
import subprocess
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Python Path Fix
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def install_dependencies():
    """Installs required packages from requirements.txt quietly."""
    logging.info("Checking and installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
        logging.info("Dependencies are up to date.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to install dependencies: {e}")
        sys.exit(1)
    except FileNotFoundError:
        logging.error("ERROR: requirements.txt not found. Please ensure the file exists.")
        sys.exit(1)

def ensure_automated_token():
    """
    Ensures we have a valid token using the automated token manager.
    No more manual token generation required!
    """
    from utils.auto_token_manager import AutoTokenManager

    try:
        logging.info("🤖 Using automated token management system...")
        token_manager = AutoTokenManager()

        # Get valid token (will auto-renew if needed)
        access_token = token_manager.get_valid_token()

        if access_token:
            logging.info("✅ Valid Fyers token obtained automatically")
            return True
        else:
            logging.error("❌ Automated token generation failed")
            logging.error("Please run 'python setup_automated_tokens.py' for first-time setup")
            return False

    except Exception as e:
        logging.error(f"Token management error: {e}")
        logging.error("Please run 'python setup_automated_tokens.py' for first-time setup")
        return False

def start_bot():
    """Initializes and starts the CPR Alert Bot."""
    logging.info("Starting the CPR Alert Bot application...")
    from cpr_bot import CPRAlertBot

    bot = CPRAlertBot()
    if bot.initialize_daily_levels():
        logging.info("🚀 Bot initialized successfully - starting monitoring...")
        bot.start_monitoring()
    else:
        logging.error("Failed to initialize bot. Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    # Create logs directory
    os.makedirs("logs", exist_ok=True)

    # Step 1: Install dependencies
    install_dependencies()

    # Step 2: Ensure we have a valid token (automated)
    if not ensure_automated_token():
        logging.error("Cannot start bot without valid token. Exiting.")
        sys.exit(1)

    # Step 3: Start the bot
    start_bot()