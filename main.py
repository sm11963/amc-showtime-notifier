import argparse
import sys
import traceback
from config import MAX_EXCEPTIONS
from database import database, Showtime, Film, purge_old_records
from datetime import datetime, timedelta
from fetch_showtimes import fetch_new_showtimes, fetch_showtimes
from outputs import send_email, gen_formated_showtimes, gen_new_showtimes_html, gen_formated_film_results


def notify(args):
    with database:
        database.create_tables([Film, Showtime])

        def post_request_callback(err):
            if err is not None:
                print('x', end='')
            else:
                print('.', end='')
            sys.stdout.flush()

        print(f"[{str(datetime.now())}] Starting requests for {args.lookforward_days} days, {len(args.theatres)} theatres, and {len(args.offerings)} offerings ({args.lookforward_days * len(args.theatres) * len(args.offerings)} requests)")
        new = fetch_new_showtimes(args.lookforward_days, args.theatres, args.offerings, post_request_callback)
        print()

        if len(new.showtimes):
            print("New showtimes:")
            print(gen_formated_showtimes(new.showtimes, args.theatres))
            send_email(
                f"New AMC showtimes found!",
                gen_new_showtimes_html(new.showtimes, args.theatres),
                args.email_sender,
                args.email_to,
                args.email_password,
                html=True
            )

        if new.exceptions == 0:
            print('Success')
        elif len(new.exceptions) == MAX_EXCEPTIONS:
            print(f'Failed after encountering {MAX_EXCEPTIONS} exceptions')
        else:
            print(f"Success with {len(new.exceptions)} exceptions")

        print("\nSummary:\n")
        print(f"  Found {len(new.showtimes)} new showtimes and {len(new.films)} new films")
        purged = purge_old_records()
        print(f"  Purged {purged.showtimes} old showtimes and {purged.films} films with no showtimes\n")

        if len(new.exceptions) > 0:
            s = f"Encountered {len(new.exceptions)} Exceptions:\n\n"
            for e in new.exceptions:
                s += e[1] + "\n"
            print(s)

            e = new.exceptions[-1][0]
            e_str = ''.join(traceback.TracebackException.from_exception(e).format())

            if args.log_email_recipients:
                send_email(
                    "AMC Showtime Notifier Exception",
                    f"At {str(datetime.now())} AMC Showtime notifier encountered exceptions!\n\n{s}\n\nLatest exception:\n{e_str}",
                    args.email_sender,
                    args.log_email_recipients,
                    args.email_password
                )

            print("Raising latest exception...")
            raise e
        else:
            if args.log_email_recipients:
                send_email(
                    "AMC Showtime Notifier Success",
                    f"Successfully completed at {str(datetime.now())}",
                    args.email_sender,
                    args.log_email_recipients,
                    args.email_password
                )


def email(args):
    send_email(args.subject, args.body, args.send_from, args.recipients, args.smtp_password)


def debug(args):
    with database:

        if args.drop_tables:
            database.drop_tables([Film, Showtime])

        if args.delete_film is not None:
            q = Film.delete().where(Film.key == args.delete_film)
            q.execute()

            q = Showtime.delete().where(Showtime.film == args.delete_film)
            q.execute()

        if args.purge_old_records:
            results = purge_old_records()
            print(f"Removed {results['showtimes']} showtimes and {results['films']} films")

        if args.clear_links:
            for showtime in Showtime.select():
                showtime.link = ""
                showtime.save()

        if args.print_films:
            for film in Film.select():
                print(f'{film.title} [{film.key}] {film.showtimes.count()} showtimes')

        if args.print_showtimes:
            for showtime in Showtime.select():
                print(f'{showtime.date} - {showtime.theatre} - {showtime.film} ({showtime.link})')

        if args.pprint_showtimes:
            theatres = set((x.theatre for x in Showtime.select(Showtime.theatre)))
            print(gen_formated_showtimes(list(Showtime.select()), theatres))

        if args.print_showtimes_html:
            theatres = set((x.theatre for x in Showtime.select(Showtime.theatre)))

            print(gen_new_showtimes_html(list(Showtime.select()), theatres))

        if args.print_showtimes_before:
            d = datetime.strptime(args.print_showtimes_before, '%Y-%m-%d %I:%M%p')
            for showtime in Showtime.select().where(Showtime.date < d):
                print(f'{showtime.date} - {showtime.film}')

        if args.delete_showtimes_before:
            d = datetime.strptime(args.delete_showtimes_before, '%Y-%m-%d %I:%M%p')
            q = Showtime.delete().where(Showtime.date < d)
            count_removed = q.execute()
            print(f'{count_removed} records removed')

        if args.purge_theatre:
            q = Showtime.delete().where(Showtime.theatre == args.purge_theatre)
            count_removed = q.execute()
            print(f'{count_removed} records removed')


def fetch(args):
    (theatre_location, theatre_key) = args.theatre.split('/')
    films = fetch_showtimes(theatre_location, theatre_key, args.datestr, args.offering)
    print(gen_formated_film_results(films))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Alert when new showtimes are available.')

    parser.add_argument('--db-file', default='amc_showtimes.db',
                        help='Customize the location of the SQLLite database file to use. By default its \'amc_showtimes.db\'')

    subparsers = parser.add_subparsers(required=True)

    notify_parser = subparsers.add_parser('notify', help='Check for and notify if there are new showtimes')
    notify_parser.set_defaults(func=notify)
    notify_parser.add_argument('lookforward_days', type=int,
                                help='How many days in the future to process showtimes')
    notify_parser.add_argument('email_sender',
                               help='Gmail email account to send notifications from')
    notify_parser.add_argument('email_password',
                               help='App password for the Gmail email account to send notifications from')
    notify_parser.add_argument('--email-to', nargs='+', required=True,
                               help='Recipients for the new showtimes notification email.')
    notify_parser.add_argument('--theatres', nargs='+', required=True,
                               help="Theatres to lookup showtimes for, in order of preference. To find new theatres, go to https://www.amctheatres.com/movie-theatres, search for the theatre you are interested in and click the link to \"Showtimes\" for that theatre. In the URL, after \"movie-theatres/\" there should be a location key and a theatre key, use that portion of the URL for this argument. For example: \"san-francisco/amc-metreon-16\"")
    notify_parser.add_argument('--offerings', nargs='+', required=True,
                               help="Theatre formats to lookup (AMC seems to name these offerings). These values can be found by going to amctheatres.com and opening the showtimes for a theatre. There will be an option to select different formats, the default selection is currently \"Premium Offerings\". Selecting a different option will put the key for the format in the URL. For example, selecting \"Dolby Cinema at AMC\" will result in the following value in the URL: \"dolbycinemaatamcprime\"")
    notify_parser.add_argument('--log-email-recipients', action='append',
                               help='Email recipients for command logs (sent on any outcome of the command in addition to new notifications). Add as many as necessary.')


    debug_parser = subparsers.add_parser('debug', help='Debug database')
    debug_parser.set_defaults(func=debug)
    debug_parser.add_argument('--drop-tables', action='store_true', default=False,
                              help='Drops the tables.')
    debug_parser.add_argument('--delete-film', default=None,
                              help='Delete the film and showtimes with the given film key')
    debug_parser.add_argument('--purge-theatre', default=None,
                              help='Delete all showtimes for the given theatre key.')
    debug_parser.add_argument('--purge-old-records', action='store_true', default=False,
                              help='Removes showtimes older than the current datetime and any films with no showtimes.')
    debug_parser.add_argument('--clear-links', action='store_true', default=False,
                              help='Replaces all the Showtime links with empty string')
    debug_parser.add_argument('--print-films', action='store_true', default=False,
                              help='Prints all films in the database.')
    debug_parser.add_argument('--print-showtimes', action='store_true', default=False,
                              help='Prints all showtimes in the database.')
    debug_parser.add_argument('--print-showtimes-html', action='store_true', default=False,
                              help='Prints all showtimes in the database using the html email format.')
    debug_parser.add_argument('--pprint-showtimes', action='store_true', default=False,
                              help='Pretty prints all showtimes in the database.')
    debug_parser.add_argument('--print-showtimes-before', default=None,
                              help='Prints all showtimes in the database with date before the provided datetime in format 2023-08-05 7:34PM')
    debug_parser.add_argument('--delete-showtimes-before', default=None,
                              help='Deletes all showtimes in the database with date before the provided datetime in format 2023-08-05 7:34PM')

    fetch_parser = subparsers.add_parser('fetch', help='Fetch showtimes from AMC')
    fetch_parser.set_defaults(func=fetch)
    fetch_parser.add_argument('datestr', default=None,
                              help='Fetches showtimes for the given date in format 2023-08-05')
    fetch_parser.add_argument('--theatre', required=True,
                               help="Theatre to lookup showtimes for, in order of preference. To find new theatres, go to https://www.amctheatres.com/movie-theatres, search for the theatre you are interested in and click the link to \"Showtimes\" for that theatre. In the URL, after \"movie-theatres/\" there should be a location key and a theatre key, use that portion of the URL for this argument. For example: \"san-francisco/amc-metreon-16\"")
    fetch_parser.add_argument('--offering', required=True,
                               help="Theatre format to lookup (AMC seems to name these offerings). These values can be found by going to amctheatres.com and opening the showtimes for a theatre. There will be an option to select different formats, the default selection is currently \"Premium Offerings\". Selecting a different option will put the key for the format in the URL. For example, selecting \"Dolby Cinema at AMC\" will result in the following value in the URL: \"dolbycinemaatamcprime\"")


    email_parser = subparsers.add_parser('email', help='Send email with the given parameters through gmail SMTP (used for testing).')
    email_parser.set_defaults(func=email)
    email_parser.add_argument('send_from',
                              help='Email account to send with')
    email_parser.add_argument('smtp_password',
                              help='SMTP password')
    email_parser.add_argument('subject',
                              help='Subject of message')
    email_parser.add_argument('body',
                              help='Body of message')
    email_parser.add_argument('recipients', nargs='+',
                              help='Recipients for the new showtimes notification email.')

    args = parser.parse_args()

    database.init(args.db_file)

    args.func(args)



