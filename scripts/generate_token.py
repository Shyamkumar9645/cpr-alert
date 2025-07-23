import os
import webbrowser
from pathlib import Path
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

def generate_fyers_token():
    """
    Guides the user through the Fyers access token generation process.
    """
    print("--- Fyers Access Token Generation ---")

    # Load credentials from .env file
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        print("Error: .env file not found. Please run setup_security.py first.")
        return
    load_dotenv(dotenv_path=env_path)

    APP_ID = os.getenv("FYERS_APP_ID")
    SECRET_KEY = os.getenv("FYERS_SECRET_KEY")
    REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")

    if not all([APP_ID, SECRET_KEY, REDIRECT_URI]):
        print("Error: Make sure FYERS_APP_ID, FYERS_SECRET_KEY, and FYERS_REDIRECT_URI are set in your .env file.")
        return

    # Create a session model
    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_KEY,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code"
    )

    # Generate the authorization URL
    auth_url = session.generate_authcode()
    print(f"\n1. Please open the following URL in your browser:\n{auth_url}")
    webbrowser.open(auth_url, new=1)

    # Prompt for the auth code
    auth_code = input("\n2. After logging in, you will be redirected. Paste the full redirected URL here:\n").strip()

    # Extract the auth_code from the URL
    try:
        auth_code = auth_code.split('auth_code=')[1].split('&')[0]
        print(f"\nExtracted Auth Code: {auth_code}")
    except IndexError:
        print("\nError: Could not find 'auth_code' in the provided URL. Please paste the full URL.")
        return

    # Set the auth code and generate the access token
    session.set_token(auth_code)
    response = session.generate_token()

    if response.get("s") == "ok":
        access_token = response["access_token"]
        print(f"\n✅ Success! Your new access token is:\n{access_token}")
        print("\nThis token has been automatically saved to your .env file.")

        # Update the .env file
        with open(env_path, "r") as f:
            lines = f.readlines()
        with open(env_path, "w") as f:
            for line in lines:
                if line.startswith("FYERS_ACCESS_TOKEN="):
                    f.write(f'FYERS_ACCESS_TOKEN="{access_token}"\n')
                else:
                    f.write(line)
    else:
        print(f"\n❌ Error generating token: {response.get('message')}")

if __name__ == "__main__":
    generate_fyers_token()