# #!/bin/bash
# # ─────────────────────────────────────────────
# # Gold Deal Finder Cron Runner
# # This script will be called by cron
# # ─────────────────────────────────────────────

# # Navigate to your project directory
# cd /Users/yashprajapati/YP-Projects/gold-deal-finder || exit 1

# # Activate virtual environment
# if [ -f "venv/bin/activate" ]; then
#     source venv/bin/activate
# else
#     echo "$(date) - ERROR: venv not found" >> "$HOME/gold_scanner_cron.log"
#     exit 1
# fi

# # Run the scanner
# python scanner.py >> "$HOME/gold_scanner_cron.log" 2>&1

# # Log the execution
# echo "$(date) - Gold scanner executed" >> "$HOME/gold_scanner_cron.log"