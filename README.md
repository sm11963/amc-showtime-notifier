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

### Running on Docker on Synology NAS
For clarity, here is my process to run this image on Docker on my Synology DS918+ NAS:
1. On Synology DSM, create a new shared folder. In my case, I created a general scriptsdata shared folder to be used by any low security scripts like this one.
2. Follow [this guide](https://drfrankenstein.co.uk/step-2-setting-up-a-restricted-docker-user-and-obtaining-ids/) to create a new user / group and retrieve the UIDs. In my case, I created a general user I can use for low security scripts, scriptsrunner and a group scriptsrunner. The access of the new user should be very limited.
3. Give the new user/group read/write access to the shared folder you created in step 1.
4. Make your user account a member of the new group you created. Note, that before you do this, make sure you haven't explicitly denyed access to anything like that group, otherwise adding your primary user account to the new group could cause loss of access (been there, done that!).
5. Open Docker on the NAS and upload the docker image (you can use the instructions above to build and export the image).
6. Create a container from the image. Open the advanced settings and fill out the environment variables including setting the UID and GID of the new user and group.
7. Map a directory in the new shared folder you created in the previous steps to the path `/data` in the new container.
8. Run the container. You can check the logs that will be output in the directoy you mapped to `/data`, check the logs in the docker UI for the container, and/or create a shell in the container (create a new shell using `/bin/sh`) to find out what is going on in the container.
