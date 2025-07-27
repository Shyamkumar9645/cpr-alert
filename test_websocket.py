import os
import time
import threading
from datetime import datetime
from dotenv import load_dotenv

# Import the official Fyers API V3 SDK
try:
    from fyers_apiv3 import fyersModel
    from fyers_apiv3.FyersWebsocket import data_ws
except ImportError:
    print("❌ Fyers API V3 SDK not found!")
    print("Please install it using: pip install fyers-apiv3")
    exit(1)

# Load environment variables from .env file
load_dotenv()

class FyersRealTimeClient:
    def __init__(self):
        """Initialize Fyers API client with credentials from .env file"""
        # Use FYERS_CLIENT_ID to be consistent with FyersModel parameter
        self.client_id = os.getenv('FYERS_APP_ID')
        self.access_token = os.getenv('FYERS_ACCESS_TOKEN')

        # Create the combined access token for the websocket
        self.ws_access_token = f"{self.client_id}:{self.access_token}"

        # Validate required environment variables
        if not self.client_id or not self.access_token:
            raise ValueError("Missing required environment variables: FYERS_CLIENT_ID or FYERS_ACCESS_TOKEN")

        # Initialize Fyers model
        self.fyers = fyersModel.FyersModel(client_id=self.client_id, token=self.access_token, log_path=os.getcwd())

        # WebSocket instance
        self.data_socket = None
        self.is_connected = False
        self.latest_data = {}

        print(f"✅ Fyers client initialized with Client ID: {self.client_id[:10]}...")

    # --- CORRECTED CALLBACK SIGNATURES ---
    # The Fyers library calls these functions with a specific number of arguments.
    # The method definitions MUST match the library's expectations.

    def on_connect(self):
        """Callback when WebSocket connects. Receives no arguments."""
        print("🔗 WebSocket Connected!")
        self.is_connected = True

    def on_close(self, message):
        """Callback when WebSocket disconnects. Receives one argument: message."""
        print(f"🔌 WebSocket Disconnected! Message: {message}")
        self.is_connected = False

    def on_error(self, message):
        """Callback when WebSocket encounters an error. Receives one argument: message."""
        print(f"❌ WebSocket Error: {message}")

    def on_message(self, message):
        """Callback when WebSocket receives a message. Receives one argument: message."""
        try:
            # Parse the message data
            symbol = message.get('symbol', 'Unknown')
            ltp = message.get('ltp', 0)
            volume = message.get('vol_traded_today', 0)
            open_price = message.get('open_price', 0)
            high_price = message.get('high_price', 0)
            low_price = message.get('low_price', 0)
            prev_close = message.get('prev_close_price', 0)
            change = message.get('ch', 0)
            change_percent = message.get('chp', 0)

            # Store latest data
            self.latest_data[symbol] = {
                'symbol': symbol,
                'ltp': ltp,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'prev_close': prev_close,
                'volume': volume,
                'change': change,
                'change_percent': change_percent,
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'bid': message.get('bid', 0.0), # Default to float
                'ask': message.get('ask', 0.0)  # Default to float
            }

            # Print real-time update
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] {symbol}: LTP=₹{ltp:.2f}, Change={change:+.2f} ({change_percent:+.2f}%), Vol={volume:,}")

        except Exception as e:
            print(f"Error processing message: {e} | Raw Message: {message}")

    def connect_websocket(self):
        """Initialize and connect WebSocket"""
        try:
            # Create WebSocket instance with corrected callbacks
            self.data_socket = data_ws.FyersDataSocket(
                access_token=self.ws_access_token,
                log_path="",
                litemode=False,
                write_to_file=False,
                on_connect=self.on_connect,
                on_close=self.on_close,
                on_error=self.on_error,
                on_message=self.on_message
            )

            # Connect to WebSocket
            self.data_socket.connect()
            print("🚀 Attempting to connect to Fyers WebSocket...")

            # Wait for connection
            timeout = 10
            while not self.is_connected and timeout > 0:
                time.sleep(1)
                timeout -= 1

            if self.is_connected:
                print("✅ Successfully connected to Fyers WebSocket!")
                return True
            else:
                print("❌ Failed to connect to WebSocket within timeout")
                return False

        except Exception as e:
            print(f"❌ WebSocket connection error: {e}")
            return False

    def subscribe_symbols(self, symbols):
        """Subscribe to real-time data for given symbols"""
        if not self.is_connected or not self.data_socket:
            print("❌ WebSocket not connected. Cannot subscribe to symbols.")
            return False

        try:
            # CORRECTED: Use 'symbols' keyword argument instead of 'symbol'
            self.data_socket.subscribe(symbols=symbols, data_type="SymbolUpdate")
            print(f"📡 Subscribed to symbols: {', '.join(symbols)}")
            return True

        except Exception as e:
            print(f"❌ Subscription error: {e}")
            return False

    def unsubscribe_symbols(self, symbols):
        """Unsubscribe from real-time data for given symbols"""
        if not self.is_connected or not self.data_socket:
            print("❌ WebSocket not connected. Cannot unsubscribe from symbols.")
            return False

        try:
            # CORRECTED: Use 'symbols' keyword argument instead of 'symbol'
            self.data_socket.unsubscribe(symbols=symbols)
            print(f"📡 Unsubscribed from symbols: {', '.join(symbols)}")
            return True

        except Exception as e:
            print(f"❌ Unsubscription error: {e}")
            return False

    def disconnect(self):
        """Disconnect WebSocket"""
        try:
            if self.data_socket:
                self.data_socket.close_connection()
        except Exception as e:
            print(f"❌ Error during disconnect: {e}")

    def get_latest_price(self, symbol):
        """Get the latest price data for a symbol"""
        return self.latest_data.get(symbol)

    def get_all_latest_data(self):
        """Get latest data for all subscribed symbols"""
        return self.latest_data.copy()

    def get_profile(self):
        """Get user profile information"""
        try:
            response = self.fyers.get_profile()
            return response
        except Exception as e:
            print(f"❌ Error fetching profile: {e}")
            return None

class FyersRealTimeTracker:
    def __init__(self):
        self.client = FyersRealTimeClient()
        self.running = False

    def start_tracking(self, symbols, duration=60):
        """
        Start real-time tracking for given symbols
        """
        try:
            print("=" * 80)
            print("🚀 FYERS V3 REAL-TIME MARKET DATA TRACKER")
            print("=" * 80)

            print("🔍 Testing API connection...")
            profile = self.client.get_profile()
            if profile and profile.get('s') == 'ok':
                user_name = profile.get('data', {}).get('name', 'Unknown')
                print(f"✅ API connection successful! Welcome, {user_name}")
            else:
                print("⚠️ API connection test failed, but continuing with WebSocket...")
                print(f"   Response: {profile}")

            if not self.client.connect_websocket():
                print("❌ Failed to connect to WebSocket. Exiting...")
                return

            if not self.client.subscribe_symbols(symbols):
                print("❌ Failed to subscribe to symbols. Exiting...")
                return

            self.running = True
            print(f"\n📊 Tracking symbols: {', '.join(symbols)}")
            print(f"⏱️  Duration: {'Indefinite' if duration == 0 else f'{duration} seconds'}")
            print("🔴 Press Ctrl+C to stop tracking")
            print("-" * 80)

            if duration > 0:
                self._track_with_timeout(duration)
            else:
                self._track_indefinitely()

        except KeyboardInterrupt:
            print("\n⛔ Tracking interrupted by user")
        except Exception as e:
            print(f"❌ Error during tracking: {e}")
        finally:
            self._cleanup(symbols)

    def _track_with_timeout(self, duration):
        """Track for a specific duration"""
        start_time = time.time()
        while self.running and (time.time() - start_time) < duration:
            time.sleep(1)

        print(f"\n⏰ Tracking duration completed ({duration} seconds)")

    def _track_indefinitely(self):
        """Track indefinitely until interrupted"""
        while self.running:
            time.sleep(1)

    def _cleanup(self, symbols):
        """Cleanup resources"""
        self.running = False
        print("\nCleaning up...")
        self._print_summary()
        if self.client.is_connected:
            self.client.unsubscribe_symbols(symbols)
            self.client.disconnect()
        print("✅ Real-time tracking stopped")

    def _print_summary(self):
        """Print final summary of collected data"""
        print(f"\n{'=' * 80}")
        print("📊 FINAL SUMMARY - Latest Prices:")
        print("=" * 80)

        latest_data = self.client.get_all_latest_data()

        if not latest_data:
            print("No data collected during tracking session.")
            return

        print(f"{'Symbol':<20} | {'LTP':<10} | {'Change':<12} | {'Change%':<10} | {'Volume':<15}")
        print("-" * 80)

        for symbol, data in latest_data.items():
            if data and data['ltp']:
                print(f"{symbol:<20} | ₹{data['ltp']:<9.2f} | "
                      f"{data['change']:+>6.2f} | "
                      f"{data['change_percent']:+>6.2f}% | "
                      f"{data['volume']:>12,}")

def test_realtime_data():
    """Test function for real-time market data"""
    try:
        tracker = FyersRealTimeTracker()
        symbols = [
            'NSE:SBIN-EQ', 'NSE:RELIANCE-EQ', 'NSE:TCS-EQ',
            'NSE:INFY-EQ', 'NSE:HDFCBANK-EQ'
        ]
        tracker.start_tracking(symbols, duration=30)

    except Exception as e:
        print(f"❌ Test error: {e}")

if __name__ == "__main__":
    print("🎯 Fyers V3 Real-Time Market Data Fetcher")
    print("📋 Make sure your .env file contains:")
    print("   FYERS_CLIENT_ID=your_client_id")
    print("   FYERS_ACCESS_TOKEN=your_access_token")
    print()
    test_realtime_data()
