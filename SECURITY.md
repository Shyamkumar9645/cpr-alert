# Security Guide

## Overview
This guide covers security best practices for the CPR Stock Alert System.

## Environment Variables Setup

### 1. Create .env File
```bash
cp .env.example .env
```

### 2. Fill in Your Credentials
Edit the `.env` file with your actual values:

```bash
# Fyers API Configuration
FYERS_APP_ID=your_actual_app_id
FYERS_SECRET_KEY=your_actual_secret_key

# Telegram Bot Configuration  
TELEGRAM_BOT_TOKEN=your_actual_bot_token
TELEGRAM_CHAT_ID=your_actual_chat_id
```

## Security Best Practices

### ✅ Do's
- **Use environment variables** for all sensitive data
- **Never commit** `.env` files to version control
- **Regularly rotate** API keys and tokens
- **Use HTTPS** for all API communications
- **Validate inputs** from external sources
- **Monitor logs** for suspicious activity
- **Keep dependencies updated**

### ❌ Don'ts
- **Never hardcode** API keys or tokens in source code
- **Don't share** `.env` files via email/chat
- **Don't commit** config files with real credentials
- **Don't log** sensitive information
- **Don't run** with unnecessary privileges

## File Permissions
```bash
chmod 600 .env          # Read/write for owner only
chmod 700 logs/         # Full access for owner only
```

## Git Security
The `.gitignore` file already excludes:
- `.env` files
- `config*.json` files
- Log files
- Database files

## API Security

### Rate Limiting
- Respects Fyers API rate limits (180 calls/minute)
- Implements backoff strategies
- Monitors API usage

### Token Management
- Tokens are encrypted in transit
- Access tokens are refreshed automatically
- Old tokens are invalidated

## Monitoring

### Log Monitoring
Check logs for:
- Failed authentication attempts
- Unusual API usage patterns
- Error rates

### Alert Setup
Monitor for:
- Rate limit exceeded
- Authentication failures
- Unexpected API responses

## Incident Response

If you suspect a security breach:

1. **Immediately revoke** all API keys
2. **Change all passwords**
3. **Review logs** for suspicious activity
4. **Update credentials** with new secure values
5. **Monitor accounts** for unauthorized activity

## Dependencies

Keep these packages updated:
- `requests` - HTTP security
- `fyers-apiv3` - API client security
- `cryptography` - Encryption libraries

```bash
pip install --upgrade requests fyers-apiv3
```

## Contact

For security issues, please contact the repository maintainer privately.