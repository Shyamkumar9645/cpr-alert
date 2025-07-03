# CPR Alert Bot - GitHub Actions Deployment (100% FREE)

Run your CPR alert bot completely free using GitHub Actions!

## 🆓 Why GitHub Actions?

- **Completely FREE** for public repositories
- **2,000 minutes/month FREE** for private repositories  
- **6 hours daily runtime** (perfect for market hours 9:15 AM - 3:30 PM IST)
- **No credit card required**
- **Automatic scheduling** - runs only during market hours
- **Secure environment** - encrypted secrets

## 📋 Setup Instructions

### 1. Create GitHub Repository

```bash
# Navigate to your deployment folder
cd /Users/shyam/IdeaProjects/claude-mcp/stock-alerts/render-deploy

# Initialize git repository
git init

# Add all files
git add .

# Commit changes
git commit -m "Initial CPR Alert Bot setup"

# Create repository on GitHub (public for unlimited free minutes)
# Then add remote and push
git remote add origin https://github.com/yourusername/cpr-alert-bot.git
git branch -M main
git push -u origin main
```

### 2. Set GitHub Secrets

Go to your repository → Settings → Secrets and variables → Actions

Add these secrets:

| Secret Name | Value | Description |
|-------------|--------|-------------|
| `FYERS_APP_ID` | Your Fyers App ID | From Fyers Developer Portal |
| `FYERS_SECRET_KEY` | Your Fyers Secret Key | From Fyers Developer Portal |
| `FYERS_ACCESS_TOKEN` | Your Fyers Access Token | Generated access token |
| `TELEGRAM_BOT_TOKEN` | Your Telegram Bot Token | From @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram Chat ID | From @userinfobot |

### 3. Workflow Schedule

The bot automatically runs:
- **Monday to Friday** at **9:10 AM IST** (5 minutes before market open)
- **Stops automatically** after 6 hours (3:30 PM IST)
- **Manual trigger available** via GitHub Actions tab

### 4. Monitor Execution

1. Go to your repository
2. Click **Actions** tab
3. View real-time logs and execution status
4. Download logs artifacts after completion

## 🕐 Cost Breakdown

**GitHub Actions Usage:**
- **Daily runtime**: 6 hours (market hours)
- **Monthly usage**: ~132 hours (22 trading days × 6 hours)
- **Cost**: **$0 (FREE)** for public repositories

**Comparison with paid platforms:**
- Render Free: 750 hours/month
- Railway Free: 500 hours/month  
- Heroku: No longer free
- **GitHub Actions: UNLIMITED (public repos)**

## 🔧 Advanced Configuration

### Custom Schedule
Edit `.github/workflows/cpr-bot.yml` to change timing:

```yaml
schedule:
  # Run at 9:00 AM IST (3:30 AM UTC)
  - cron: '30 3 * * 1-5'
```

### Manual Triggers
Trigger manually from Actions tab or via API:

```bash
# Trigger via GitHub CLI
gh workflow run cpr-bot.yml
```

### Extend Runtime
For longer monitoring (if needed):

```yaml
run: |
  timeout 8h python cpr_bot.py  # 8 hours instead of 6
```

## 📊 Monitoring & Debugging

### View Real-time Logs
1. Actions tab → Latest workflow run
2. Click on "cpr-monitoring" job
3. Expand steps to see real-time output

### Download Log Files
- Logs automatically uploaded as artifacts
- Available for 7 days after run
- Download from completed workflow runs

### Troubleshooting
- **Workflow not running**: Check repository is public or has Actions enabled
- **Secrets not working**: Verify secret names match exactly
- **Bot stopping early**: Check market hours and error logs

## 🚀 Deployment Steps

1. **Create public GitHub repository**
2. **Push this code**
3. **Add secrets in repository settings**
4. **Enable GitHub Actions** (usually enabled by default)
5. **Wait for next scheduled run** or trigger manually

## 🔒 Security

- All credentials stored as encrypted GitHub Secrets
- Never exposed in logs or code
- Secure execution environment
- Automatic cleanup after runs

## 📈 Benefits

✅ **100% Free** - No hosting costs  
✅ **Reliable** - GitHub's infrastructure  
✅ **Automated** - Runs on schedule  
✅ **Scalable** - Can add more workflows  
✅ **Monitored** - Built-in logging  
✅ **Secure** - Encrypted secrets  

---

## Quick Start Commands

```bash
# 1. Clone/setup your repository
git clone https://github.com/yourusername/cpr-alert-bot.git
cd cpr-alert-bot

# 2. Add your secrets via GitHub web interface
# Settings → Secrets and variables → Actions

# 3. Trigger first run (optional)
gh workflow run cpr-bot.yml

# 4. Monitor
# Go to Actions tab in your repository
```

**That's it!** Your CPR bot will run completely free on GitHub Actions during market hours! 🎉