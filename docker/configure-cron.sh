#!/bin/sh

# Ensure we have the necessary files
touch /data/cron.log
touch /etc/crontabs/docker_internal

echo "Scheduling AMC showtime notifier with schedule: $CRON_SCHEDULE"
sed -i '/run-notifier.sh/d' /etc/crontabs/docker_internal
echo "$CRON_SCHEDULE /var/local/bin/run-notifier.sh >> /data/notifier.log 2>&1" >> /etc/crontabs/docker_internal

