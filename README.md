# CPR Alert Bot - Railway Deployment

A real-time stock market CPR (Central Pivot Range) level alert bot that monitors Indian stocks and sends alerts via Telegram when price touches key support/resistance levels.

## Features

- 🎯 Real-time CPR level monitoring (S1, PIVOT, R1)
- 📱 Telegram alerts with detailed information
- 🔒 30-minute cooldown to prevent spam
- 📊 Supports 15+ premium intraday stocks
- 🚀 Optimized for Fyers API limits (200 calls/min)
- 💾 SQLite database for alert history

## Railway Deployment

### 1. Prerequisites

- Railway account (free tier available)
- Fyers trading account with API access
- Telegram bot token and chat ID

### 2. Environment Variables

Set these in Railway dashboard:

```env
FYERS_APP_ID=your_app_id_here
FYERS_SECRET_KEY=your_secret_key_here
FYERS_ACCESS_TOKEN=your_access_token_here
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
FYERS_REDIRECT_URI=https://trade.fyers.in/api-login/redirect-uri/index.html
```

### 3. Deploy to Railway

#### Method 1: CLI Deployment

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project in this directory
railway init

# Deploy
railway deploy
```

#### Method 2: GitHub Integration

1. Push this folder to GitHub repository
2. Connect repository to Railway
3. Set environment variables in Railway dashboard
4. Deploy automatically

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

- Check Railway dashboard for real-time logs
- Database stores all alerts with timestamps
- Bot automatically resets daily levels at 6 AM

### 8. Cost Optimization

**Free Tier Limits:**
- Railway: 500 hours/month (sufficient for market hours)
- Fyers API: 200 calls/minute (bot uses ~150 calls/min)
- Telegram: No limits on message sending

### 9. Troubleshooting

**Common Issues:**
- Missing environment variables → Check Railway dashboard
- API rate limits → Bot has built-in rate limiting
- No alerts → Check market hours and cooldown status

**Debug Commands:**
```bash
# Check Railway logs
railway logs

# Connect to Railway shell
railway shell
```

### 10. Security

- All credentials stored as encrypted environment variables
- No sensitive data in code repository
- API tokens automatically refreshed

---

**Ready to deploy?** Just set your environment variables and run `railway deploy`!