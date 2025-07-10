#!/usr/bin/env python3
"""
Test script to send CPR chart to Telegram
This script will generate a realistic chart and send it to your Telegram chat
"""

import sys
import os
import json
from datetime import datetime, timedelta
import random

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cpr_bot import (
    ChartGenerator, TelegramService, FyersService, CPRLevels, CandleData, LevelType,
    CHART_SUPPORT, ConfigManager, CPRCalculator
)

def load_config():
    """Load configuration from config1.json"""
    config_path = 'config1.json'
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None

def generate_realistic_candles(base_price=23500, count=50):
    """Generate realistic 5-minute candles for NIFTY 50"""
    candles = []
    current_time = datetime.now() - timedelta(hours=4)
    
    for i in range(count):
        # Create realistic price movement
        if i < 15:
            # Initial sideways movement
            price_trend = base_price + random.uniform(-50, 50)
        elif i < 30:
            # Downward trend toward S1
            price_trend = base_price - (i - 15) * 4 + random.uniform(-30, 30)
        elif i < 40:
            # Approaching S1 level (23400)
            price_trend = 23420 + random.uniform(-20, 40)
        else:
            # Bouncing from S1 level
            price_trend = 23400 + (i - 40) * 3 + random.uniform(-25, 25)
        
        # Generate OHLC
        open_price = price_trend + random.uniform(-10, 10)
        high_price = open_price + random.uniform(5, 25)
        low_price = open_price - random.uniform(5, 20)
        close_price = open_price + random.uniform(-15, 15)
        
        # Ensure high is highest and low is lowest
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)
        
        # Generate volume
        volume = random.randint(50000, 200000)
        
        candle_time = current_time + timedelta(minutes=i * 5)
        
        candles.append(CandleData(
            timestamp=int(candle_time.timestamp()),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=volume,
            datetime=candle_time,
            time_str=candle_time.strftime('%H:%M')
        ))
    
    return candles

def create_realistic_cpr_levels():
    """Create realistic CPR levels for NIFTY 50"""
    # Based on typical NIFTY 50 levels
    return CPRLevels(
        pivot=23500.0,
        tc=23600.0,
        bc=23400.0,
        r1=23700.0,
        s1=23300.0
    )

def test_telegram_chart_sending():
    """Test sending a chart to Telegram with real CPR levels and market data"""
    
    print("🚀 Testing Telegram Chart Sending with REAL Data")
    print("=" * 50)
    
    # Check chart support
    if not CHART_SUPPORT:
        print("❌ Chart support not available. Installing dependencies...")
        return False
    
    # Load configuration
    config = load_config()
    if not config:
        print("❌ Failed to load configuration")
        return False
    
    # Verify Telegram config
    telegram_config = config.get('telegram', {})
    if not telegram_config.get('bot_token') or not telegram_config.get('chat_id'):
        print("❌ Telegram configuration missing")
        return False
    
    print(f"✅ Telegram Bot Token: {'SET' if telegram_config.get('bot_token') else 'NOT SET'}")
    print(f"✅ Telegram Chat ID: {telegram_config.get('chat_id')}")
    
    try:
        # Initialize services with real Fyers connection
        print("\n🔧 Initializing services...")
        chart_generator = ChartGenerator()
        telegram_service = TelegramService(telegram_config)
        fyers_service = FyersService(config['fyers'])
        cpr_calculator = CPRCalculator()
        
        # Test symbol
        symbol = "NSE:NIFTY50-INDEX"
        asset_name = "NIFTY 50"
        
        print(f"📊 Fetching REAL market data for {asset_name}...")
        
        # Get real chart data (5-minute candles for today + yesterday)
        candles = chart_generator.get_chart_data(fyers_service, symbol, candle_count=78)  # ~6.5 hours of 5min data
        
        if not candles:
            print("❌ Failed to fetch real market data - falling back to simulated data")
            cpr_levels = create_realistic_cpr_levels()
            candles = generate_realistic_candles()
            current_price = 23302.50
        else:
            print(f"📈 Fetched {len(candles)} real candles")
            
            # Calculate real CPR levels from yesterday's data
            from datetime import date, timedelta
            yesterday = date.today() - timedelta(days=1)
            yesterday_data = fyers_service.get_historical_ohlc(symbol, yesterday)
            
            if yesterday_data:
                cpr_levels = cpr_calculator.calculate_levels(yesterday_data)
                current_price = candles[-1].close  # Latest close price
                print(f"🎯 REAL CPR Levels from {yesterday}: S1={cpr_levels.s1:.2f}, Pivot={cpr_levels.pivot:.2f}, R1={cpr_levels.r1:.2f}")
                print(f"💰 Current Price: {current_price:.2f}")
            else:
                print("⚠️ Could not fetch yesterday's data - using default CPR levels")
                cpr_levels = create_realistic_cpr_levels()
                current_price = candles[-1].close
        
        # Determine which level is closest (for alert simulation)
        current_price = candles[-1].close
        distances = {
            LevelType.S1: abs(current_price - cpr_levels.s1),
            LevelType.PIVOT: abs(current_price - cpr_levels.pivot),
            LevelType.R1: abs(current_price - cpr_levels.r1)
        }
        touched_level = min(distances, key=distances.get)
        
        print(f"\n📉 Simulating {touched_level.value} level alert at {current_price:.2f}")
        
        # Generate chart with real data
        print("🎨 Generating chart with REAL market data...")
        chart_buffer = chart_generator.create_cpr_chart(
            symbol=symbol,
            asset_name=asset_name,
            candle_data=candles,
            cpr_levels=cpr_levels,
            current_level=touched_level,
            current_price=current_price
        )
        
        if not chart_buffer:
            print("❌ Chart generation failed")
            return False
        
        print(f"✅ Chart generated successfully! Size: {len(chart_buffer.getvalue())} bytes")
        
        # Create alert message
        detection_time = datetime.now()
        
        message = f"""📉 *S1 Touch Alert* *(TEST)*
        
*NIFTY 50* touched S1 level!

📊 *Level:* `{cpr_levels.s1:.2f}`
🚨 *Alert Time:* `{detection_time.strftime('%H:%M:%S')}` *(REAL-TIME)*
📅 *Data Time:* `{candles[-1].time_str}`
💰 *Current Price:* `{current_price:.2f}`

⚠️ *This is a TEST alert*"""
        
        # Send to Telegram
        print("\n📱 Sending to Telegram...")
        print("📨 Message preview:")
        print("-" * 40)
        print(message)
        print("-" * 40)
        
        # Send the chart with message
        success = telegram_service.send_photo_with_caption(
            photo_buffer=chart_buffer,
            caption=message
        )
        
        if success:
            print("✅ Chart sent to Telegram successfully!")
            print("📱 Check your Telegram chat for the chart")
            print("🎯 You should see:")
            print("  • A 5-minute candlestick chart")
            print("  • CPR levels marked as horizontal lines")
            print("  • Volume bars at the bottom")
            print("  • Clean alert message as caption")
            return True
        else:
            print("❌ Failed to send chart to Telegram")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False

def test_fallback_text_alert():
    """Test fallback text alert if chart fails"""
    
    print("\n🔄 Testing fallback text alert...")
    
    config = load_config()
    if not config:
        return False
    
    telegram_service = TelegramService(config['telegram'])
    
    # Test regular text alert
    text_message = """🚨 *FALLBACK ALERT TEST*

*NIFTY 50* - CPR Level Alert

📊 *Level:* S1 at `23300.00`
🚨 *Alert Time:* `{time}`
💰 *Current Price:* `23302.50`

⚠️ *Chart generation failed - Text alert only*

🎯 *Key Level Alert* - Major support/resistance
⏰ *Next alert for NIFTY 50:* 30 minutes""".format(time=datetime.now().strftime('%H:%M:%S'))
    
    success = telegram_service.send_alert(text_message)
    
    if success:
        print("✅ Fallback text alert sent successfully!")
        return True
    else:
        print("❌ Fallback text alert failed")
        return False

def main():
    """Main test function"""
    print("🧪 CPR Alert System - Telegram Chart Test")
    print("=" * 60)
    
    print("\n🎯 This test will:")
    print("• Generate a realistic 5-minute chart with CPR levels")
    print("• Send it to your Telegram chat")
    print("• Test both chart and fallback text alerts")
    print("• Verify the complete alert workflow")
    
    print("\n🚀 Starting automated test...")
    import time
    time.sleep(2)  # Brief pause
    
    # Test 1: Chart sending
    print("\n🧪 TEST 1: Chart Generation and Telegram Sending")
    chart_success = test_telegram_chart_sending()
    
    if chart_success:
        print("\n✅ Chart test PASSED!")
        
        # Test 2: Fallback alert
        print("\n🧪 TEST 2: Fallback Text Alert")
        fallback_success = test_fallback_text_alert()
        
        if fallback_success:
            print("\n🎉 ALL TESTS PASSED!")
            print("✅ Your CPR alert system is ready with chart support!")
            print("📱 Check your Telegram for both messages")
            return True
        else:
            print("\n⚠️ Chart test passed, but fallback failed")
            return False
    else:
        print("\n❌ Chart test FAILED!")
        print("🔧 Please check:")
        print("• Telegram bot token and chat ID")
        print("• Internet connection")
        print("• Chart dependencies installed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)