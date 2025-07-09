# 🚀 CPR Stock Alerts - One Click Start

## Single Command to Start Receiving Alerts

```bash
./START_ALERTS.sh
```

**That's it!** The script will automatically:

✅ **Install dependencies** (fyers-apiv3, requests, schedule)  
✅ **Generate Fyers token** (opens browser once)  
✅ **Setup environment** (all configurations)  
✅ **Test connections** (Fyers API + Telegram)  
✅ **Start monitoring** (immediate alerts)  
✅ **Schedule refresh** (daily 9pm token renewal)  

## What You'll See

1. **Welcome banner** with feature overview
2. **Dependency check** and auto-installation
3. **Token generation** (browser opens for Fyers login)
4. **Telegram test** (you'll get a welcome message)
5. **Alert system starts** (immediate stock monitoring)

## First Run Only

- **Browser opens** for Fyers authentication
- **Copy auth code** from redirect URL
- **Paste in terminal** when prompted
- **Done!** Never needed again (auto-refresh at 9pm)

## What You Get

- 📊 **10 major stocks/indices** monitored
- 🎯 **CPR level alerts** (S1, R1, Pivot touches)
- 📱 **Telegram notifications** in real-time
- ⏰ **30-minute cooldown** per stock
- 🔄 **Auto token refresh** at 9pm daily

## Monitored Assets

- **Indices**: NIFTY 50, BANK NIFTY, FINNIFTY
- **Stocks**: RELIANCE, HDFC BANK, ICICI BANK, AXIS BANK, SBI, TATA MOTORS, BAJAJ FINANCE

## Stop the System

Press `Ctrl+C` in terminal to stop alerts.

## Files in This Directory

- **`START_ALERTS.sh`** - Run this to start alerts
- **`one_click_start.py`** - Main launcher script  
- **`cpr_bot.py`** - Core alert system
- **`generate_official_token.py`** - Token management
- **`config1.json`** - Configuration file (auto-created)
- **`QUICK_START.md`** - This documentation

## Troubleshooting

If something goes wrong:
1. Check `one_click.log` for errors
2. Ensure stable internet connection
3. Verify Telegram bot token is working
4. Re-run the script (it's idempotent)

---

**No manual token generation, no environment setup, no configuration files to edit!**