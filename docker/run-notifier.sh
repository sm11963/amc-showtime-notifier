#!/bin/sh

cd /app

python main.py \
  --db-file /data/amc_showtimes.db \
  notify \
  $LOOKAHEAD_DAYS \
  $EMAIL_SENDER \
  $SMTP_PASSWORD \
  --email-to $EMAIL_RECIPIENTS \
  --theatres $THEATRES \
  --offerings $OFFERINGS
