#!/bin/sh

# Ensure we have the necessary files
touch /data/cron.log
touch /etc/crontabs/docker_internal

echo "Scheduling AMC showtime notifier with schedule: $CRON_SCHEDULE"
sed -i '/python main.py/d' /etc/crontabs/docker_internal
echo "$CRON_SCHEDULE cd /app && python main.py --db-file /data/amc_showtimes.db notify $LOOKAHEAD_DAYS $EMAIL_SENDER $SMTP_PASSWORD $EMAIL_RECIPIENTS >> /data/notifier.log 2>&1" >> /etc/crontabs/docker_internal

