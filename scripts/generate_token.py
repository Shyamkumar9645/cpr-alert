import os
import webbrowser
from pathlib import Path
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

def generate_fyers_token():
    """
    Guides the user through the Fyers access token generation process.
    """
    print("\n--- 🔑 Fyers Access Token Generation ---")

    # Path to the .env file in the project root
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        print("\n❌ Error: .env file not found. Please run 'python scripts/setup_security.py' first.")
        return

    load_dotenv(dotenv_path=env_path)

    APP_ID = os.getenv("FYERS_APP_ID")
    SECRET_KEY = os.getenv("FYERS_SECRET_KEY")
    REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")

    if not all([APP_ID, SECRET_KEY, REDIRECT_URI]):
        print("\n❌ Error: Make sure FYERS_APP_ID, FYERS_SECRET_KEY, and FYERS_REDIRECT_URI are set in your .env file.")
        return

    # Create a session model
    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_KEY,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code"
    )

    # Generate and open the authorization URL
    auth_url = session.generate_authcode()
    print(f"\n1. Your browser will now open the Fyers login page.")
    print(f"   If it doesn't, please open this URL manually:\n   {auth_url}")
    webbrowser.open(auth_url, new=1)

    # Prompt for the auth code from the redirected URL
    auth_code_url = input("\n2. After logging in, you will be redirected. Paste the ENTIRE redirected URL here:\n   ").strip()

    # Extract the auth_code from the URL
    try:
        auth_code = auth_code_url.split('auth_code=')[1].split('&')[0]
        print(f"\n   Found Auth Code: {auth_code}")
    except IndexError:
        print("\n❌ Error: Could not find 'auth_code' in the provided URL. Please try again and paste the full URL.")
        return

    # Set the auth code and generate the access token
    session.set_token(auth_code)
    response = session.generate_token()

    if response.get("s") == "ok":
        access_token = response["access_token"]
        print(f"\n✅ Success! Your new access token has been generated.")
        print("   It has been automatically saved to your .env file.")

        # Read the existing .env file
        with open(env_path, "r") as f:
            lines = f.readlines()

        # Write back the lines, updating the access token
        with open(env_path, "w") as f:
            updated = False
            for line in lines:
                if line.strip().startswith("FYERS_ACCESS_TOKEN="):
                    f.write(f'FYERS_ACCESS_TOKEN="{access_token}"\n')
                    updated = True
                else:
                    f.write(line)
            if not updated: # Add the token if the line didn't exist
                f.write(f'FYERS_ACCESS_TOKEN="{access_token}"\n')

    else:
        print(f"\n❌ Error generating token: {response.get('message', 'Unknown error')}")

if __name__ == "__main__":
    generate_fyers_token()