# PythonAnywhere Secure Deployment Guide

## Overview
Deploy CPR Stock Alert System securely on PythonAnywhere without exposing secrets.

## 🚀 Step-by-Step Deployment

### 1. Upload Code (Without Secrets)

**Option A: Git Clone (Recommended)**
```bash
# In PythonAnywhere Bash console
cd ~
git clone https://github.com/yourusername/cpr-alert.git
cd cpr-alert
```

**Option B: File Upload**
- Upload project files via PythonAnywhere Files tab
- **DO NOT upload .env file!**

### 2. Set Environment Variables Securely

**Method 1: Using .bashrc (Recommended)**

1. Open PythonAnywhere Bash console
2. Edit your .bashrc file:

```bash
nano ~/.bashrc
```

3. Add your environment variables at the end:

```bash
# CPR Stock Alert System Environment Variables
export FYERS_APP_ID="your_app_id_here"
export FYERS_SECRET_KEY="your_secret_key_here"
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"

# Optional settings
export CHECK_INTERVAL_SECONDS="60"
export TOLERANCE_PERCENT="0.15"
export COOLDOWN_MINUTES="30"
```

4. Reload the environment:

```bash
source ~/.bashrc
```

5. Verify variables are set:

```bash
echo $FYERS_APP_ID
# Should print your app ID
```

**Method 2: Using Python Script**

Create a secure setup script on PythonAnywhere:

```bash
nano ~/setup_env.py
```

```python
#!/usr/bin/env python3
import os
import getpass

def setup_environment():
    """Set up environment variables securely"""
    
    print("🔐 CPR Alert - PythonAnywhere Setup")
    print("=" * 40)
    
    # Get credentials securely
    app_id = input("Fyers App ID: ").strip()
    secret_key = getpass.getpass("Fyers Secret Key (hidden): ").strip()
    bot_token = input("Telegram Bot Token: ").strip()
    chat_id = input("Telegram Chat ID: ").strip()
    
    # Create environment file for PythonAnywhere
    env_script = f'''#!/bin/bash
# CPR Alert Environment Variables
export FYERS_APP_ID="{app_id}"
export FYERS_SECRET_KEY="{secret_key}"
export TELEGRAM_BOT_TOKEN="{bot_token}"
export TELEGRAM_CHAT_ID="{chat_id}"
'''
    
    # Write to a script file
    with open(os.path.expanduser('~/set_cpr_env.sh'), 'w') as f:
        f.write(env_script)
    
    # Make executable
    os.chmod(os.path.expanduser('~/set_cpr_env.sh'), 0o700)
    
    print("✅ Environment variables saved to ~/set_cpr_env.sh")
    print("Run: source ~/set_cpr_env.sh")

if __name__ == "__main__":
    setup_environment()
```

Run the setup:
```bash
python3 ~/setup_env.py
source ~/set_cpr_env.sh
```

### 3. Install Dependencies

```bash
cd ~/cpr-alert
pip3.10 install --user -r requirements.txt
```

### 4. Test the Application

```bash
# Set environment variables
source ~/.bashrc  # or source ~/set_cpr_env.sh

# Test the application
python3.10 one_click_start.py
```

### 5. Create Startup Script

Create a script to run your bot:

```bash
nano ~/start_cpr_alert.sh
```

```bash
#!/bin/bash
# CPR Alert Startup Script

# Load environment variables
source ~/.bashrc

# Navigate to project directory
cd ~/cpr-alert

# Run the alert system
python3.10 one_click_start.py
```

Make it executable:
```bash
chmod +x ~/start_cpr_alert.sh
```

### 6. Schedule with Cron (For Always-On Tasks)

**For Paid Accounts (Always-On Tasks):**

1. Go to PythonAnywhere Dashboard → Tasks
2. Create new scheduled task:

```
Command: /home/yourusername/start_cpr_alert.sh
Hour: 9 (9 AM)
Minute: 15 (9:15 AM IST)
```

**For Free Accounts:**

Free accounts can't run always-on tasks, but you can:
- Run manually during market hours
- Use external scheduler (GitHub Actions) to trigger

### 7. Web App Integration (Optional)

If you want a web interface:

```python
# app.py
import os
from flask import Flask, render_template
from cpr_bot import CPRAlertBot

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start-alerts')
def start_alerts():
    # Load environment variables
    bot = CPRAlertBot()
    # Start monitoring logic here
    return "Alerts started!"

if __name__ == '__main__':
    app.run(debug=True)
```

## 🔐 Security Best Practices for PythonAnywhere

### ✅ Do's:
- Use `.bashrc` for environment variables
- Set file permissions to 600/700
- Use `getpass` for secure input
- Keep secrets in home directory only
- Use HTTPS for all external API calls

### ❌ Don'ts:
- Don't upload .env files
- Don't hardcode secrets in web-accessible files
- Don't log sensitive information
- Don't share console access
- Don't commit secrets to Git

## 🔍 File Structure on PythonAnywhere

```
/home/yourusername/
├── .bashrc                 # Environment variables
├── cpr-alert/             # Your project code
│   ├── one_click_start.py
│   ├── cpr_bot.py
│   └── requirements.txt
├── set_cpr_env.sh         # Environment setup script
└── start_cpr_alert.sh     # Startup script
```

## 🛡️ Security Verification

**Check environment variables:**
```bash
env | grep FYERS
env | grep TELEGRAM
```

**Check file permissions:**
```bash
ls -la ~/.bashrc
ls -la ~/set_cpr_env.sh
```

**Verify secrets are not in Git:**
```bash
cd ~/cpr-alert
git log --all --grep=FYERS_SECRET_KEY
# Should return nothing
```

## 📊 PythonAnywhere Account Types

| Feature | Free | Hacker ($5/month) | Web Dev ($12/month) |
|---------|------|-------------------|---------------------|
| Always-On Tasks | ❌ | ✅ 1 task | ✅ 2 tasks |
| Scheduled Tasks | ❌ | ✅ | ✅ |
| SSH Access | ❌ | ✅ | ✅ |
| Internet Access | Limited | ✅ | ✅ |

**Recommendation:** Hacker plan ($5/month) for always-on CPR monitoring

## 🚀 Alternative: Hybrid Approach

**Free PythonAnywhere + GitHub Actions:**

1. Use GitHub Actions for scheduling (FREE)
2. Use PythonAnywhere API to trigger your script
3. Best of both worlds!

```python
# webhook.py - Simple Flask app on PythonAnywhere
from flask import Flask, request
import subprocess

app = Flask(__name__)

@app.route('/trigger-alerts', methods=['POST'])
def trigger_alerts():
    # Verify request is from GitHub Actions
    if request.headers.get('Authorization') == 'Bearer your_webhook_secret':
        subprocess.run(['/home/yourusername/start_cpr_alert.sh'])
        return "Alerts triggered!"
    return "Unauthorized", 401
```

This way you get:
- ✅ FREE scheduling (GitHub Actions)
- ✅ Secure environment (PythonAnywhere)
- ✅ Reliable execution