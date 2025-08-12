import sys
import os
import subprocess
import logging

# Setup basic logging
# This can be at the top as it only uses standard libraries
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Python Path Fix ---
# This is also fine at the top level
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# -----------------------

def install_dependencies():
    """Installs required packages from requirements.txt quietly."""
    logging.info("Checking and installing dependencies...")
    try:
        # Using check_call to ensure the command succeeds
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
        logging.info("Dependencies are up to date.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to install dependencies: {e}")
        # Exit if dependencies can't be installed, as the rest of the script will fail
        sys.exit(1)
    except FileNotFoundError:
        logging.error("ERROR: requirements.txt not found. Please ensure the file exists.")
        sys.exit(1)


def manage_fyers_token():
    """
    Checks for the Fyers access token in the environment variables.
    If not found, guides the user through generating one.
    """
    # Import necessary modules inside the function
    from utils.config_manager import ConfigManager
    from services.fyers_service import FyersService

    config = ConfigManager.load_config()
    fyers_creds = config['fyers_credentials']

    # Check for the access token; note that getenv might return None or an empty string
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

    # Exit after token generation guidance so the user can update the .env file
    sys.exit(1)

def start_bot():
    """Initializes and starts the CPR Alert Bot."""
    logging.info("Starting the CPR Alert Bot application...")
    # Import the bot class here, after dependencies are confirmed to be installed
    from cpr_bot import CPRAlertBot

    bot = CPRAlertBot()
    if bot.initialize_daily_levels():
        bot.start_monitoring()
    else:
        logging.error("Failed to initialize bot. Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    # --- Critical Step 1: Install dependencies ---
    # This MUST be the first thing to run to ensure all required modules are available.
    install_dependencies()

    # --- Step 2: Manage secrets and configurations ---
    # Now that dependencies are installed, we can safely call functions that import them.
    manage_fyers_token()

    # --- Step 3: Start the main application logic ---
    start_bot()
