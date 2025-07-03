# CPR Alert Bot - Render Deployment

A real-time stock market CPR (Central Pivot Range) level alert bot that monitors Indian stocks and sends alerts via Telegram when price touches key support/resistance levels.

## Features

- 🎯 Real-time CPR level monitoring (S1, PIVOT, R1)
- 📱 Telegram alerts with detailed information
- 🔒 30-minute cooldown to prevent spam
- 📊 Supports 15+ premium intraday stocks
- 🚀 Optimized for Fyers API limits (200 calls/min)
- 💾 SQLite database for alert history

## Render Deployment

### 1. Prerequisites

- Render account (free tier available - 750 hours/month)
- Fyers trading account with API access
- Telegram bot token and chat ID

### 2. Environment Variables

Set these in Render dashboard:

```env
FYERS_APP_ID=your_app_id_here
FYERS_SECRET_KEY=your_secret_key_here
FYERS_ACCESS_TOKEN=your_access_token_here
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
FYERS_REDIRECT_URI=https://trade.fyers.in/api-login/redirect-uri/index.html
```

### 3. Deploy to Render

#### Method 1: GitHub Integration (Recommended)

1. **Push to GitHub:**
```bash
cd render-deploy
git init
git add .
git commit -m "Initial CPR bot setup"
git remote add origin https://github.com/yourusername/cpr-alert-bot.git
git push -u origin main
```

2. **Connect to Render:**
   - Login to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" → "Background Worker"
   - Connect your GitHub repository
   - Select this folder/branch

3. **Configure Service:**
   - **Name:** `cpr-alert-bot`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python cpr_bot.py`
   - **Plan:** `Free`

4. **Set Environment Variables:**
   - Go to Environment tab
   - Add all required variables listed above

#### Method 2: Direct Upload

1. Create new Background Worker on Render
2. Upload this folder as ZIP
3. Configure build/start commands
4. Set environment variables

### 4. Getting API Credentials

#### Fyers API Setup
1. Login to [Fyers Developer Portal](https://myapi.fyers.in/)
2. Create new app to get `APP_ID` and `SECRET_KEY`
3. Generate access token using the authentication flow
4. Set the redirect URI as provided

#### Telegram Bot Setup
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create new bot with `/newbot` command
3. Get bot token from BotFather
4. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot)

### 5. Monitored Assets

The bot monitors these premium intraday stocks:

**Indices (★★★★★)**
- NIFTY 50, BANK NIFTY, NIFTY FINANCIAL

**Banking Stocks (★★★★★)**
- HDFC BANK, ICICI BANK, AXIS BANK, STATE BANK, INDUSIND BANK

**High Volatility Movers (★★★★★)**
- RELIANCE, TATA MOTORS, BAJAJ FINANCE, JSW STEEL, TATA STEEL, ADANI ENT

### 6. Alert Logic

Alerts are triggered when:
- Price actually touches S1/R1/PIVOT levels (0.05% tolerance)
- Directional validation passes (approaching from correct side)
- No recent alerts (30-minute stock-wide cooldown)
- Market is open (09:15 - 15:30 IST)

### 7. Logs and Monitoring

- Check Render dashboard for real-time logs
- Database stores all alerts with timestamps
- Bot automatically resets daily levels at 6 AM
- Service auto-restarts on failures

### 8. Cost Optimization

**Free Tier Limits:**
- Render: 750 hours/month (perfect for market hours: ~6.5h/day × 22 days = ~143h/month)
- Service sleeps after 15 minutes of inactivity (no HTTP requests)
- Fyers API: 200 calls/minute (bot uses ~150 calls/min)
- Telegram: No limits on message sending

### 9. Render-Specific Features

**Auto-Sleep Management:**
- Service stays active during market hours (09:15-15:30 IST)
- Automatically sleeps after market close
- No need for external ping services

**Persistent Storage:**
- SQLite database persists across deployments
- Logs stored and accessible via dashboard

### 10. Troubleshooting

**Common Issues:**
- Missing environment variables → Check Render Environment tab
- Service sleeping → Normal behavior outside market hours
- API rate limits → Bot has built-in rate limiting
- Build failures → Check Python version and dependencies

**Debug Commands:**
```bash
# Check logs in Render dashboard
# Go to your service → Logs tab

# Manual deployment
# Connect via GitHub and trigger manual deploy
```

### 11. Monitoring

**Health Checks:**
- Bot logs startup and shutdown
- Real-time market status monitoring
- Automatic error recovery with retries

**Performance:**
- ~150 API calls/minute during active monitoring
- Memory usage: ~50-100MB
- CPU usage: Low (background worker)

### 12. Security

- All credentials stored as encrypted environment variables
- No sensitive data in code repository
- Render provides automatic HTTPS and secure environment
- API tokens never logged or exposed

---

## Quick Start

1. **Fork/Clone this repository**
2. **Set up Fyers API and Telegram bot** (get credentials)
3. **Deploy to Render** using GitHub integration
4. **Set environment variables** in Render dashboard
5. **Start monitoring** - bot runs automatically during market hours

**Ready to deploy?** Just connect your GitHub repo to Render and set your environment variables!

---

### Support

For issues:
- Check Render logs first
- Verify all environment variables are set
- Ensure Fyers API credentials are valid
- Test Telegram bot connectivity