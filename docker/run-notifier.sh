#!/bin/sh

cd /app

python main.py \
  --db-file /data/amc_showtimes.db \
  notify \
  $LOOKAHEAD_DAYS \
  $EMAIL_SENDER \
  $SMTP_PASSWORD \
  $EMAIL_RECIPIENTS
