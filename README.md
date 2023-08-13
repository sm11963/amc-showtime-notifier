# amc-showtime-notifier
A script to notify when AMC Theatres showtime tickets are available. 

This script was created specifically to identify when new showtimes are released for AMC Dobly Cinema theatres. It was designed to work with other offerings/formats from AMC but please be aware that those flows are less tested.

Running the script will fetch showtimes and store in a SQLlite database, any showtimes that are new will be emailed to the provided email.

## Usage
```
❯ cd amc-showtime-notifier
❯ python main.py notify -h
usage: main.py notify [-h] --email-to EMAIL_TO [EMAIL_TO ...] --theatres THEATRES [THEATRES ...]
                      --offerings OFFERINGS [OFFERINGS ...]
                      [--log-email-recipients LOG_EMAIL_RECIPIENTS]
                      lookforward_days email_sender email_password

positional arguments:
  lookforward_days      How many days in the future to process showtimes
  email_sender          Gmail email account to send notifications from
  email_password        App password for the Gmail email account to send notifications from

options:
  -h, --help            show this help message and exit
  --email-to EMAIL_TO [EMAIL_TO ...]
                        Recipients for the new showtimes notification email.
  --theatres THEATRES [THEATRES ...]
                        Theatres to lookup showtimes for, in order of preference. To find new theatres,
                        go to https://www.amctheatres.com/movie-theatres, search for the theatre you are
                        interested in and click the link to "Showtimes" for that theatre. In the URL,
                        after "movie-theatres/" there should be a location key and a theatre key, use
                        that portion of the URL for this argument. For example: "san-francisco/amc-
                        metreon-16"
  --offerings OFFERINGS [OFFERINGS ...]
                        Theatre formats to lookup (AMC seems to name these offerings). These values can
                        be found by going to amctheatres.com and opening the showtimes for a theatre.
                        There will be an option to select different formats, the default selection is
                        currently "Premium Offerings". Selecting a different option will put the key for
                        the format in the URL. For example, selecting "Dolby Cinema at AMC" will result
                        in the following value in the URL: "dolbycinemaatamcprime"
  --log-email-recipients LOG_EMAIL_RECIPIENTS
                        Email recipients for command logs (sent on any outcome of the command in
                        addition to new notifications). Add as many as necessary.
```

For example, my typical run will look something like this:
```
python main.py notify 90 $EMAIL_SENDER $SMTP_PASSWORD \
  --email-to $EMAIL_RECIPIENTS \
  --theatres san-francisco/amc-dine-in-sunnyvale-12 san-jose/amc-saratoga-14 san-jose/amc-eastridge-15 \
  --offerings dolbycinemaatamcprime
```

This will check for AMC Dolby Cinema showtimes up to 90 days in the future at the given 3 theatres and email any newly discovered showtimes to the given email recipients.

## Docker

Also provided are the Docker configuration files to build a Docker image which will run this script on a given cron schedule. 

This was specifically designed for my use case of continously running this script on a Synology DS918+ NAS. 

These are the steps to build and export the image to be uploaded to a Docker host:
```
❯ cd amc-showtime-notifier
❯ docker build --platform linux/amd64 -t amc-showtime-notifier:latest .
❯ docker save amc-showtime-notifier:latest | gzip > amc-showtime-notifier.tar.gz
```

When creating a container from the image, review the [Dockerfile](Dockerfile) for details on the environment variables to set which configure how the script runs.
