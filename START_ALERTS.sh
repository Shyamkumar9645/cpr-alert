#!/bin/bash

# Change to the script's directory to ensure all paths are correct
cd "$(dirname "$0")"

echo "🚀 Starting CPR Alert Bot from: $(pwd)"

# Execute the main Python script
python3 main.py

echo "✅ Bot process has been started."