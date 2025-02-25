#!/bin/bash

# Export environment variables for cron
env | grep -v "no_proxy" > /tmp/env.sh
chmod +x /tmp/env.sh

# Update crontab to source environment variables
echo "$(cat /tmp/env.sh)
$(crontab -l)" | crontab -

# Run the initial check immediately
cd /app && python src/main.py

# Start cron daemon (runs as root but executes jobs as appuser)
sudo /usr/sbin/cron -f
