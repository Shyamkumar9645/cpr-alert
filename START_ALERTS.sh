#!/bin/bash

echo "--- Starting CPR Stock Alert System ---"

# Activate virtual environment if you have one
# source /path/to/your/venv/bin/activate

# Check if dependencies are installed
if ! python -c "import pkg_resources; pkg_resources.require(open('requirements.txt', 'r'))" &> /dev/null; then
    echo "Dependencies not met. Installing from requirements.txt..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error installing dependencies. Exiting."
        exit 1
    fi
fi

# Run the main application
python main.py

echo "--- CPR Stock Alert System has stopped ---"