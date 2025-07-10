#!/usr/bin/env python3
"""
Test script to verify chart functionality
"""

import sys
import os

def test_chart_dependencies():
    """Test if chart dependencies are installed"""
    print("🧪 Testing chart dependencies...")
    
    try:
        import mplfinance as mpf
        print("✅ mplfinance imported successfully")
    except ImportError as e:
        print(f"❌ mplfinance import failed: {e}")
        return False
    
    try:
        import pandas as pd
        print("✅ pandas imported successfully")
    except ImportError as e:
        print(f"❌ pandas import failed: {e}")
        return False
    
    try:
        from PIL import Image
        print("✅ PIL imported successfully")
    except ImportError as e:
        print(f"❌ PIL import failed: {e}")
        return False
    
    try:
        import matplotlib.pyplot as plt
        print("✅ matplotlib imported successfully")
    except ImportError as e:
        print(f"❌ matplotlib import failed: {e}")
        return False
    
    print("✅ All chart dependencies are available!")
    return True

def test_chart_generation():
    """Test basic chart generation"""
    print("\n🎨 Testing chart generation...")
    
    try:
        import pandas as pd
        import mplfinance as mpf
        import io
        from datetime import datetime, timedelta
        
        # Create sample data
        dates = pd.date_range(start='2023-01-01', periods=50, freq='5min')
        
        # Generate sample OHLC data
        sample_data = []
        base_price = 100
        
        for i, date in enumerate(dates):
            open_price = base_price + (i * 0.1)
            high_price = open_price + 2
            low_price = open_price - 1.5
            close_price = open_price + 0.5
            volume = 1000 + (i * 10)
            
            sample_data.append({
                'Open': open_price,
                'High': high_price,
                'Low': low_price,
                'Close': close_price,
                'Volume': volume
            })
        
        df = pd.DataFrame(sample_data, index=dates)
        
        # Test basic chart creation
        buf = io.BytesIO()
        
        # Create horizontal lines (CPR levels) - mplfinance format
        hlines = dict(
            hlines=[98, 102, 106],
            colors=['red', 'blue', 'green'],
            linestyle=['--', '-', '--'],
            linewidths=[2, 2, 2]
        )
        
        fig, axes = mpf.plot(
            df,
            type='candle',
            volume=True,
            hlines=hlines,
            title='Test Chart with CPR Levels',
            figsize=(12, 8),
            returnfig=True
        )
        
        # Save to buffer
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        
        # Check if buffer has content
        if buf.getvalue():
            print("✅ Chart generation successful!")
            print(f"📊 Chart buffer size: {len(buf.getvalue())} bytes")
            
            # Try to save as file for verification
            with open('test_chart.png', 'wb') as f:
                f.write(buf.getvalue())
            print("✅ Test chart saved as 'test_chart.png'")
            
            return True
        else:
            print("❌ Chart buffer is empty")
            return False
            
    except Exception as e:
        print(f"❌ Chart generation failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 CPR Alert Chart Testing")
    print("=" * 40)
    
    if not test_chart_dependencies():
        print("\n❌ Install missing dependencies:")
        print("pip install mplfinance pandas pillow matplotlib")
        return False
    
    if not test_chart_generation():
        print("\n❌ Chart generation test failed")
        return False
    
    print("\n🎉 All tests passed! Chart functionality is ready.")
    print("📈 The CPR bot will now send charts with alerts!")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)