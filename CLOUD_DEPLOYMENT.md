# Secure Cloud Deployment Guide

## Overview
This guide shows how to securely deploy the CPR Alert System to various cloud platforms WITHOUT exposing secrets.

## ⚠️ NEVER DO THIS:
```bash
# DON'T upload .env files!
scp .env server:/app/
git add .env
docker COPY .env /app/
```

## ✅ SECURE DEPLOYMENT METHODS:

### 1. GitHub Actions (FREE)

**Step 1: Add Secrets to Repository**
1. Go to: Repository → Settings → Secrets and Variables → Actions
2. Click "New repository secret"
3. Add each secret:

```
Name: FYERS_APP_ID
Value: VAC70PGA10-100

Name: FYERS_SECRET_KEY  
Value: your_secret_key_here

Name: TELEGRAM_BOT_TOKEN
Value: your_bot_token_here

Name: TELEGRAM_CHAT_ID
Value: your_chat_id_here
```

**Step 2: Workflow File**
```yaml
# .github/workflows/cpr-alert.yml
name: CPR Stock Alert Bot

on:
  schedule:
    - cron: '40 3 * * 1-5'  # 9:10 AM IST, Mon-Fri

jobs:
  run-alerts:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run CPR Alert Bot
      env:
        FYERS_APP_ID: ${{ secrets.FYERS_APP_ID }}
        FYERS_SECRET_KEY: ${{ secrets.FYERS_SECRET_KEY }}
        TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
      run: |
        python one_click_start.py
```

### 2. Render Deployment

**Step 1: Create Render Account**
- Go to render.com
- Connect your GitHub repository

**Step 2: Add Environment Variables**
1. Service → Environment Variables
2. Add each variable:

```
FYERS_APP_ID = your_app_id_here
FYERS_SECRET_KEY = your_secret_key_here  
TELEGRAM_BOT_TOKEN = your_bot_token_here
TELEGRAM_CHAT_ID = your_chat_id_here
```

**Step 3: Deploy**
- Render automatically detects changes
- Environment variables are injected at runtime
- No .env file needed!

### 3. Heroku Deployment

```bash
# Install Heroku CLI
heroku login

# Create app
heroku create your-cpr-alert-bot

# Set environment variables
heroku config:set FYERS_APP_ID=your_app_id_here
heroku config:set FYERS_SECRET_KEY=your_secret_key_here
heroku config:set TELEGRAM_BOT_TOKEN=your_bot_token_here
heroku config:set TELEGRAM_CHAT_ID=your_chat_id_here

# Deploy
git push heroku main
```

### 4. AWS Lambda

**Using AWS Secrets Manager:**
```python
import boto3
import json

def get_secret(secret_name):
    session = boto3.session.Session()
    client = session.client('secretsmanager', region_name='us-east-1')
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        raise e

# In your Lambda function
secrets = get_secret('cpr-alert-secrets')
fyers_app_id = secrets['FYERS_APP_ID']
```

### 5. Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Environment variables will be injected at runtime
CMD ["python", "one_click_start.py"]
```

**Run with environment variables:**
```bash
docker run -e FYERS_APP_ID=your_app_id \
           -e FYERS_SECRET_KEY=your_secret \
           -e TELEGRAM_BOT_TOKEN=your_token \
           -e TELEGRAM_CHAT_ID=your_chat_id \
           your-cpr-alert-image
```

## 🔐 Security Best Practices

### ✅ Do's:
- Use platform-provided secret management
- Rotate secrets regularly
- Use different secrets for different environments
- Monitor secret access logs
- Use IAM roles where possible

### ❌ Don'ts:
- Never commit .env files
- Don't hardcode secrets in Docker images
- Don't log sensitive environment variables
- Don't share secrets via chat/email
- Don't use same secrets across environments

## 🔍 Verification

**Check that secrets are NOT in your repository:**
```bash
git log --all --grep=FYERS_SECRET_KEY
git log --all --grep=TELEGRAM_BOT_TOKEN

# Should return no results
```

**Check .gitignore is working:**
```bash
git status --ignored | grep .env
# Should show .env as ignored
```

## 📊 Security Comparison

| Method | Security Level | Ease of Use | Cost |
|--------|---------------|-------------|------|
| GitHub Secrets | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | FREE |
| Render Env Vars | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | FREE Tier |
| AWS Secrets Manager | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | $0.40/secret/month |
| Heroku Config Vars | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | $7/month |
| Docker Env Vars | ⭐⭐⭐ | ⭐⭐⭐ | Varies |

**Recommendation:** Start with GitHub Actions (FREE + most secure)