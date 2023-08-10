FROM python:3-alpine

WORKDIR /app

COPY docker/. /app/docker/
COPY requirements.txt /app/
COPY main.py /app/

RUN pip install -r requirements.txt

# UID to use to run the application processes. If this is not set, there will be issues with file access permissions.
# See this guide for example: https://drfrankenstein.co.uk/step-2-setting-up-a-restricted-docker-user-and-obtaining-ids/
ENV PUID=
# GID to use to run the application processes. If this is not set, there will be issues with file access permissions.
# See this guide for example: https://drfrankenstein.co.uk/step-2-setting-up-a-restricted-docker-user-and-obtaining-ids/
ENV PGID=
# default schedule is everyday at 8am, 2pm, and 8pm
ENV CRON_SCHEDULE="0 8,14,20 * * *"
ENV LOOKAHEAD_DAYS=
ENV EMAIL_SENDER=
ENV SMTP_PASSWORD=
ENV EMAIL_RECIPIENTS=
ENV THEATRES="san-francisco/amc-metreon-16 san-jose/amc-eastridge-15"
ENV OFFERINGS="dolbycinemaatamcprime"

ENV TZ="America/Los_Angeles"


# Setup configuration scripts
COPY ./docker/configure-app.sh /var/local/bin/configure-app.sh
RUN chmod +x /var/local/bin/configure-app.sh
COPY ./docker/configure-cron.sh /var/local/bin/configure-cron.sh
RUN chmod +x /var/local/bin/configure-cron.sh
COPY ./docker/run-notifier.sh /var/local/bin/run-notifier.sh
RUN chmod +x /var/local/bin/run-notifier.sh

# Setup our application run file
COPY ./docker/run.sh /var/local/bin/run.sh
RUN chmod +x /var/local/bin/run.sh

CMD ["/var/local/bin/run.sh"]
