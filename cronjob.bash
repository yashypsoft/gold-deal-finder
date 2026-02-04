# Navigate to your project directory
cd /Users/yashprajapati/YP-Projects/gold-deal-finder/

# Make main.py executable
chmod +x main.py

# If main.py doesn't have shebang, add it at the top of main.py:
# Add this as the first line: #!/usr/bin/env python3

#!/bin/bash

# Gold Deal Finder Runner
# This script will be called by cron

# Navigate to your project directory
cd /Users/yashprajapati/YP-Projects/gold-deal-finder/

# Activate virtual environment (if you have one)
source venv/bin/activate

# Run the scanner
python scanner.py

# Log the execution
echo "$(date): Gold scanner executed" >> ~/gold_scanner_cron.log