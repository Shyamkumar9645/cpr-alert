#!/usr/bin/env python3
"""
Demo script showing the enhanced CPR alert with chart functionality
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import io

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cpr_bot import (
    ChartGenerator, CPRLevels, CandleData, LevelType, 
    CHART_SUPPORT
)

def create_demo_chart():
    """Create a demo chart showing CPR levels with a stock alert"""
    
    if not CHART_SUPPORT:
        print("❌ Chart support not available. Please install dependencies:")
        print("pip install mplfinance pandas pillow matplotlib")
        return
    
    print("🎨 Creating demo CPR alert chart...")
    
    # Create sample CPR levels
    cpr_levels = CPRLevels(
        pivot=2500.0,
        tc=2520.0,
        bc=2480.0,
        r1=2540.0,
        s1=2460.0
    )
    
    # Generate realistic 5-minute candle data
    base_time = datetime.now() - timedelta(hours=4)
    candles = []
    
    # Create 50 candles with realistic price action around CPR levels
    for i in range(50):
        timestamp = base_time + timedelta(minutes=i * 5)
        
        # Price action that moves toward S1 level
        if i < 20:
            # Normal movement
            base_price = 2500 - (i * 0.5)
        elif i < 35:
            # Approach S1 level
            base_price = 2480 + ((i - 20) * 0.3)
        else:
            # Touch and bounce from S1
            base_price = 2460 + ((i - 35) * 0.8)
        
        # Add some randomness
        import random
        open_price = base_price + random.uniform(-2, 2)
        high_price = open_price + random.uniform(1, 5)
        low_price = open_price - random.uniform(1, 4)
        close_price = open_price + random.uniform(-3, 3)
        volume = random.randint(1000, 5000)
        
        candles.append(CandleData(
            timestamp=int(timestamp.timestamp()),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            datetime=timestamp,
            time_str=timestamp.strftime('%H:%M')
        ))
    
    # Create chart generator
    chart_gen = ChartGenerator()
    
    # Generate the chart
    chart_buffer = chart_gen.create_cpr_chart(
        symbol="NSE:NIFTY50-INDEX",
        asset_name="NIFTY 50",
        candle_data=candles,
        cpr_levels=cpr_levels,
        current_level=LevelType.S1,
        current_price=2461.5  # Just touched S1 level
    )
    
    if chart_buffer:
        # Save the demo chart
        with open('demo_cpr_alert_chart.png', 'wb') as f:
            f.write(chart_buffer.getvalue())
        
        print("✅ Demo chart created successfully!")
        print("📊 Chart saved as 'demo_cpr_alert_chart.png'")
        print("🎯 This shows what users will receive when S1 level is touched")
        
        # Display chart info
        print("\n📈 Chart Features:")
        print("• 5-minute candlestick chart")
        print("• CPR levels marked as horizontal lines:")
        print(f"  - S1: {cpr_levels.s1:.2f} (Red dashed)")
        print(f"  - Pivot: {cpr_levels.pivot:.2f} (Blue solid)")
        print(f"  - R1: {cpr_levels.r1:.2f} (Green dashed)")
        print("• Current price highlighted")
        print("• Volume bars included")
        print("• Professional styling")
        
        return True
    else:
        print("❌ Failed to create demo chart")
        return False

def create_alert_message_demo():
    """Show what the alert message will look like"""
    
    print("\n📱 Demo Alert Message:")
    print("=" * 40)
    
    message = """📉 *S1 Touch Alert*

*NIFTY 50* touched S1 level!

📊 *Level:* `2460.00`
🚨 *Alert Time:* `14:23:45` *(REAL-TIME)*
📅 *Data Time:* `14:23`

🎯 *Key Level Alert* - Major support/resistance

📈 *Chart:* 5-minute candlestick with CPR levels
⏰ *Next alert for NIFTY 50:* 30 minutes"""
    
    print(message)
    print("=" * 40)
    
    print("\n📊 What happens next:")
    print("1. Telegram receives this message")
    print("2. Chart image is sent along with the message")
    print("3. User sees both text alert and visual chart")
    print("4. Next alert for this stock blocked for 30 minutes")

def main():
    """Main demo function"""
    print("🚀 CPR Alert System - Chart Demo")
    print("=" * 50)
    
    print("\n🎯 This demo shows the enhanced alert system with:")
    print("• Real-time CPR level detection")
    print("• 5-minute candlestick charts")
    print("• Professional chart styling")
    print("• Telegram integration")
    print("• 30-minute cooldown per stock")
    
    if create_demo_chart():
        create_alert_message_demo()
        
        print("\n🎉 Demo completed successfully!")
        print("🚀 Your CPR alert system is now ready with chart support!")
        print("\nTo start the bot with chart functionality:")
        print("python cpr_bot.py")
        
        return True
    else:
        print("\n❌ Demo failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)