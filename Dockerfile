FROM python:3-alpine

WORKDIR /app

COPY docker/. /app/docker/
COPY *.py /app/
COPY requirements.txt /app/
COPY templates/. /app/templates/

RUN pip install -r requirements.txt

# UID to use to run the application processes. If this is not set, there will be issues with file access permissions.
# See this guide for example: https://drfrankenstein.co.uk/step-2-setting-up-a-restricted-docker-user-and-obtaining-ids/
ENV PUID=
# GID to use to run the application processes. If this is not set, there will be issues with file access permissions.
# See this guide for example: https://drfrankenstein.co.uk/step-2-setting-up-a-restricted-docker-user-and-obtaining-ids/
ENV PGID=
# default schedule is everyday at 8am, 2pm, and 8pm
ENV CRON_SCHEDULE="0 8,14,20 * * *"
# The number of days in the future to query for showtimes.
ENV LOOKAHEAD_DAYS=
# The email address to send notifications from using SMTP (only Google tested).
ENV EMAIL_SENDER=
ENV SMTP_PASSWORD=
# The email addresses, separated by a space, to send notifications to.
ENV EMAIL_RECIPIENTS=
# AMC theatres to lookup showtimes for, in order of preference. To find new theatres, go to https://www.amctheatres.com/movie-theatres, search for the theatre you are interested in and click the link to "Showtimes" for that theatre. In the URL, after "movie-theatres/" there should be a location key and a theatre key, use that portion of the URL for this argument. For example: "san-francisco/amc-metreon-16"
ENV THEATRES="san-francisco/amc-metreon-16 san-jose/amc-eastridge-15"
# Theatre formats to lookup (AMC seems to name these offerings). These values can be found by going to amctheatres.com and opening the showtimes for a theatre.  There will be an option to select different formats, the default selection is currently "Premium Offerings". Selecting a different option will put the key for the format in the URL. For example, selecting "Dolby Cinema at AMC" will result in the following value in the URL: "dolbycinemaatamcprime"
ENV OFFERINGS="dolbycinemaatamcprime"
# Timezone the script is executing in
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
