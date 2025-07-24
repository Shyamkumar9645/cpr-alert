import sys
import os
import subprocess
import logging

# --- Python Path Fix ---
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# -----------------------

from utils.config_manager import ConfigManager
from services.fyers_service import FyersService

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def install_dependencies():
    """Installs required packages from requirements.txt quietly."""
    logging.info("Checking and installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
        logging.info("Dependencies are up to date.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to install dependencies: {e}")
        sys.exit(1)

def manage_fyers_token():
    """
    Checks for the Fyers access token in the environment variables.
    If not found, guides the user through generating one.
    """
    config = ConfigManager.load_config()
    fyers_creds = config['fyers_credentials']

    if fyers_creds.get('access_token'):
        logging.info("Fyers access token found in .env file.")
        return

    logging.warning("Fyers access token not found in .env file. Starting generation process...")

    # Temporarily create a service instance without a token to run the generation method
    temp_fyers_service = FyersService(fyers_creds)
    new_token = temp_fyers_service.generate_access_token()

    if new_token:
        print("\n" + "="*60)
        print("✅ TOKEN GENERATED SUCCESSFULLY")
        print("Please copy the following line and add it to your .env file:")
        print(f"\nFYERS_ACCESS_TOKEN={new_token}\n")
        print("="*60 + "\n")
        logging.info("Exiting now. Please add the token to your .env file and restart the bot.")
    else:
        logging.error("Could not generate a new token. Please try again.")

    sys.exit(1) # Exit after token generation guidance

def start_bot():
    """Initializes and starts the CPR Alert Bot."""
    logging.info("Starting the CPR Alert Bot application...")
    from cpr_bot import CPRAlertBot

    bot = CPRAlertBot()
    if bot.initialize_daily_levels():
        bot.start_monitoring()
    else:
        logging.error("Failed to initialize bot. Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    install_dependencies()
    manage_fyers_token() # New token management function
    start_bot()