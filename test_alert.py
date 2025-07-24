import asyncio
from datetime import datetime, timedelta, date
import io
import os
import pytz

# Adjust the path to import from the parent directory
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from cpr_bot1 import (
    CPRAlertBot,
    LevelType,
    CandleData,
    CPRLevels,
    AssetData,
    ChartGenerator,
    FyersService,
    TelegramService,
    ConfigManager,
    DateHelper,
    CPRCalculator
)

async def main():
    """
    Test script to generate a chart for a specific stock and date with accurate CPR levels.
    """
    print("--- Starting Accurate Test Alert Script ---")

    # 1. Initialize the CPRAlertBot
    try:
        bot = CPRAlertBot()
        print("CPRAlertBot initialized successfully.")
    except Exception as e:
        print(f"Error initializing CPRAlertBot: {e}")
        return

    # 2. Define Test Parameters
    test_symbol = "NSE:RELIANCE-EQ"
    chart_date = DateHelper.get_previous_trading_day() # e.g., 2025-07-22
    cpr_cal_date = DateHelper.get_previous_trading_day(chart_date) # e.g., 2025-07-21

    asset_config = next((asset for asset in bot.config['assets'] if asset['symbol'] == test_symbol), None)
    if not asset_config:
        print(f"Asset {test_symbol} not found in config.")
        return
    asset_name = asset_config['name']

    print(f"- Test Stock: {asset_name} ({test_symbol})")
    print(f"- Chart Date: {chart_date.strftime('%Y-%m-%d')}")
    print(f"- CPR Calculation Date (OHLC from): {cpr_cal_date.strftime('%Y-%m-%d')}")

    # 3. Fetch OHLC data for CPR calculation
    print(f"\nFetching OHLC data for {cpr_cal_date.strftime('%Y-%m-%d')} to calculate CPR...")
    ohlc_data = bot.fyers_service.get_historical_ohlc(test_symbol, cpr_cal_date)
    if not ohlc_data:
        print(f"Could not fetch OHLC data for {cpr_cal_date.strftime('%Y-%m-%d')}.")
        return
    print(f"OHLC Data: O={ohlc_data.open}, H={ohlc_data.high}, L={ohlc_data.low}, C={ohlc_data.close}")

    # 4. Calculate CPR Levels for the chart date
    correct_cpr_levels = CPRCalculator.calculate_levels(ohlc_data)
    print("\nCalculated CPR Levels for Chart Date:")
    print(f"  R1: {correct_cpr_levels.r1:.2f}, TC: {correct_cpr_levels.tc:.2f}, Pivot: {correct_cpr_levels.pivot:.2f}, BC: {correct_cpr_levels.bc:.2f}, S1: {correct_cpr_levels.s1:.2f}")

    # 5. Fetch intraday data for the chart
    print(f"\nFetching intraday chart data for {chart_date.strftime('%Y-%m-%d')}...")
    chart_candles = bot.chart_generator.get_chart_data(bot.fyers_service, test_symbol, for_date=chart_date)
    if not chart_candles:
        print(f"Could not fetch intraday data for {chart_date.strftime('%Y-%m-%d')}.")
        return
    print(f"Successfully fetched {len(chart_candles)} candles.")

    # 6. Simulate a touch event for the alert
    touched_level = LevelType.R1
    touch_price = correct_cpr_levels.r1
    touching_candle = chart_candles[-1]

    # 7. Generate the chart
    print("\nGenerating chart with correct data...")
    chart_buffer = bot.chart_generator.create_cpr_chart(
        symbol=test_symbol,
        asset_name=asset_name,
        candle_data=chart_candles,
        cpr_levels=correct_cpr_levels,
        current_level=touched_level,
        current_price=touch_price
    )
    if not chart_buffer:
        print("Chart generation failed.")
        return
    print("Chart generated successfully.")

    # 8. Send the Telegram alert
    print("\nSending Telegram alert...")
    success = bot.telegram_service.send_formatted_alert(
        asset_name=asset_name,
        level_type=touched_level,
        level_value=touch_price,
        candle=touching_candle,
        total_touches=1,
        chart_buffer=chart_buffer,
        symbol=test_symbol
    )
    if success:
        print("--- Test Alert Sent Successfully! Please verify the chart and CPR levels. ---")
    else:
        print("--- Failed to Send Test Alert! ---")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    import asyncio
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "cannot run loop while another loop is running" in str(e):
            loop = asyncio.get_running_loop()
            loop.create_task(main())
        else:
            raise