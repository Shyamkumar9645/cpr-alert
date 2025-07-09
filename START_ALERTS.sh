#!/bin/bash

# ==================================================
# CPR STOCK ALERT SYSTEM - ONE CLICK START
# ==================================================
# Just run this script to start receiving stock alerts!

clear
echo "🚀 Starting CPR Stock Alert System..."
echo "===================================="

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Run the one-click launcher
python3 one_click_start.py

echo "👋 CPR Alert System stopped."