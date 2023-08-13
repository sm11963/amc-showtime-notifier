from database import database, Showtime, Film
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import argparse
import requests
import re
import time
import sys
import smtplib
import backoff
import traceback

FETCH_DELAY=5
MAX_EXCEPTIONS=5
BASE_URL='https://www.amctheatres.com'
THEATRE_SHOWTIMES_URL=BASE_URL + '/movie-theatres/{location}/{theatre_key}/showtimes/all/{datestr}/{theatre_key}/{offering}'

class ShowtimeResult(object):

    def __init__(self, time, theatre, link):
        self.time = time
        self.theatre = theatre
        self.link = link

class FilmResult(object):

    def __init__(self, key, title, showtimes):
        self.key = key
        self.title = title
        self.showtimes = showtimes

    def __repr__(self):
        formatted_showtimes = ', '.join([x.time for x in self.showtimes])
        return f"FilmResult({self.key} [{self.title}], showtimes=[{formatted_showtimes}])"


# Fetch the Films with showtimes that have available tickets given a date and theatre
@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_tries=3,
                      factor=5.0)
def fetch_showtimes(location, theatre_key, datestr, offering):
    url = THEATRE_SHOWTIMES_URL.format(
        location=location,
        theatre_key=theatre_key,
        datestr=datestr,
        offering=offering
    )

    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html5lib')
    films_soup = soup.find_all(class_="ShowtimesByTheatre-film")
    films = []
    for film_soup in films_soup:
        film_title_wrapper_soup = film_soup.find(class_='MovieTitleHeader-title')
        film_url = film_title_wrapper_soup['href']
        film_key = film_url.replace('/movies/', '')
        film_title = film_title_wrapper_soup.find('h2').text
        showtimes_soup = film_soup.find_all(class_="Showtime")
        showtimes = []
        for showtime_soup in showtimes_soup:
            if 'Showtime-disabled' in showtime_soup['class']:
                continue
            a_soup = showtime_soup.find('a')
            # if there are no offerings for the given date, AMC might redirect and provide all offerings. Double check that that this showtime is for the requested offering by checking the link which should include the offering key.
            link = BASE_URL + a_soup['href']
            if offering not in link:
                continue
            showtimes.append(ShowtimeResult(a_soup.text, theatre_key, link))

        films.append(FilmResult(film_key, film_title, showtimes))

    return films

def fetch_new_showtimes(lookforward_days, theatres, offerings):
    print(f"[{str(datetime.now())}] Starting requests for {lookforward_days} days, {len(theatres)} theatres, and {len(offerings)} offerings ({args.lookforward_days * len(theatres) * len(offerings)} requests)")
    results = {
        'films': [],
        'showtimes': [],
        'exceptions': []
    }
    exceptions = []
    start_date = datetime.now()
    for i in range(0, lookforward_days):
        if len(results['exceptions']) >= MAX_EXCEPTIONS:
            break

        date = start_date + timedelta(days=i)
        datestr = date.strftime('%Y-%m-%d')

        for theatre in theatres:
            if len(results['exceptions']) >= MAX_EXCEPTIONS:
                break

            for offering in offerings:
                try:
                    (theatre_location, theatre_key) = theatre.split('/')
                    film_results = fetch_showtimes(theatre_location, theatre_key, datestr, offering)
                except Exception as err:
                    results['exceptions'].append((err, f"Encountered exception after retries requesting for {theatre}, {datestr}, {offering}"))
                    print('x', end='')
                    sys.stdout.flush()
                    if len(results['exceptions']) >= MAX_EXCEPTIONS:
                        break
                    else:
                        continue

                for film_result in (x for x in film_results if len(x.showtimes) > 0):
                    film = Film.get_or_none(key = film_result.key)
                    if film is None:
                        film = Film.create(key = film_result.key,
                                           title = film_result.title)
                        results['films'].append(film)

                    for showtime_result in film_result.showtimes:
                        showtime_date = datetime.strptime(datestr + ' ' + showtime_result.time, '%Y-%m-%d %I:%M%p')

                        s = Showtime.get_or_none(film = film,
                                                 theatre = showtime_result.theatre,
                                                 date = showtime_date)
                        if s is None:
                            s = Showtime.create(film = film,
                                                theatre = showtime_result.theatre,
                                                date = showtime_date,
                                                link = showtime_result.link)
                            results['showtimes'].append(s)
                        else:
                            s.link = showtime_result.link
                            s.save()

                print('.', end='')
                sys.stdout.flush()

                # Space out requests a bit to avoid potentially getting throttled
                time.sleep(FETCH_DELAY)

    print()
    return results


# Sends an email using Gmail SMTP (make sure to use an App Password)
def send_email(subject, body, sender, recipients, password, html=False):
    msg = MIMEText(body, 'html' if html else 'plain')
    msg['Subject'] = subject
    msg['From'] = f"AMC Showtime Notifier <{sender}>"
    msg['To'] = ', '.join(recipients)
    # Adding this header prevents emails being grouped into threads
    msg.add_header('X-Entity-Ref-ID', 'null')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, recipients, msg.as_string())


# Removes Showtimes with date older than the current date and Films with no showtimes.
def purge_old_records():
    d = datetime.combine(datetime.now().date(), datetime.min.time())

    results = {
        'showtimes': 0,
        'films': 0
    }


    q = Showtime.delete().where(Showtime.date.truncate('day') < d)
    results['showtimes'] = q.execute()

    for film in Film.select():
        if film.showtimes.count() == 0:
            results['films'] += film.delete_instance()

    return results


def gen_formated_showtimes(showtimes, theatres, html=False):
    by_films = {}
    theatre_keys = [t.split('/')[-1] for t in theatres]
    for fk in set([x.film.key for x in showtimes]):
        ts = [(t, [s for s in showtimes if s.film.key == fk and s.theatre == t]) for t in theatre_keys]
        by_films[fk] = [t for t in ts if len(t[1]) > 0]

    body = ""
    for (k, ts) in by_films.items():

        if html:
            body += f"""
            <p style="margin:0;font-size:14px"> </p>
            <p style="margin:0;font-size:14px"><strong>{k}</strong></p>
            <p style="margin:0;font-size:14px"> </p>
            """
        else:
            body += k + "\n"
        for t in ts:
            if html:
                body += f"""
                <p dir="ltr" style="margin:0;font-size:14px;margin-left:40px">{t[0]}</p>
                <ul style="line-height:1.2">
                    <li style="list-style-type:none">
                        <ul style="line-height:1.2;font-size:14px">
                """
            else:
                body += f"  {t[0]}\n"
            for s in t[1]:
                ds = s.date.strftime("%Y-%m-%d %I:%M %p")
                if html:
                    body += f"""
                                <li dir="ltr"><a href="{s.link}">{ds}</a></li>
                    """
                else:
                    body += f"    [{ds}] - {s.link}\n"
            if html:
                body += """
                        </ul>
                    </li>
                </ul>
                """
            else:
                body += "\n"

    return body


def gen_new_showtimes_email_body(showtimes, theatres):
    body = """
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
    <html><head><META http-equiv="Content-Type" content="text/html; charset=utf-8"><style>*{box-sizing:border-box}body{margin:0;padding:0}#m_MessageViewBody a{color:inherit;text-decoration:none}p{line-height:inherit}.m_desktop_hide,.m_desktop_hide table{display:none;max-height:0;overflow:hidden}.m_image_block img+div{display:none}@media (max-width:520px){.m_mobile_hide{display:none}.m_row-content{width:100%!important}.m_stack .m_column{width:100%;display:block}.m_mobile_hide{min-height:0;max-height:0;max-width:0;overflow:hidden;font-size:0}.m_desktop_hide,.m_desktop_hide table{display:table!important;max-height:none!important}}</style></head><body><u></u><div style="background-color:#fff;margin:0;padding:0"><table class="m_nl-container" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#fff"><tbody><tr><td><table class="m_row m_row-1" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#cd2323">
    <tbody><tr><td><table class="m_row-content m_stack" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="color:#000;width:500px;margin:0 auto" width="500"><tbody><tr><td class="m_column m_column-1" width="100%" style="font-weight:400;text-align:left;padding-bottom:5px;padding-top:5px;vertical-align:top;border-top:0;border-right:0;border-bottom:0;border-left:0"><table class="m_text_block m_block-1" width="100%" border="0" cellpadding="10" cellspacing="0" role="presentation" style="word-break:break-word"><tr><td class="m_pad"><div style="font-family:Verdana,sans-serif"><div style="font-size:14px;font-family:&#39;Lucida Sans Unicode&#39;,&#39;Lucida Grande&#39;,&#39;Lucida Sans&#39;,Geneva,Verdana,sans-serif;color:#555;line-height:1.8"><p style="margin:0;font-size:14px;text-align:center">
    <span style="font-size:26px;color:#ffffff"><strong>AMC Showtime</strong><strong> </strong><strong>Notifier</strong></span></p></div></div></td></tr></table></td></tr></tbody></table></td></tr></tbody></table><table class="m_row m_row-2" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"><tbody><tr><td><table class="m_row-content m_stack" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-radius:0;color:#000;width:500px;margin:0 auto" width="500"><tbody><tr><td class="m_column m_column-1" width="100%" style="font-weight:400;text-align:left;padding-bottom:5px;padding-top:5px;vertical-align:top;border-top:0;border-right:0;border-bottom:0;border-left:0"><table class="m_text_block m_block-1" width="100%" border="0" cellpadding="10" cellspacing="0" role="presentation" style="word-break:break-word"><tr><td class="m_pad"><div style="font-family:sans-serif"><div style="font-size:14px;font-family:Arial,&#39;Helvetica Neue&#39;,Helvetica,sans-serif;color:#555;line-height:1.2"><p style="margin:0;font-size:14px">Found new AMC showtimes!</p>
    """
    body += gen_formated_showtimes(showtimes, theatres, html=True)
    body += """
    </div></div></td></tr></table></td></tr></tbody></table></td></tr></tbody></table></td></tr></tbody></table><div style="background-color:transparent">
        <div style="Margin:0 auto;min-width:320px;max-width:500px;word-wrap:break-word;word-break:break-word;background-color:transparent" class="m_block-grid">
            <div style="border-collapse:collapse;display:table;width:100%;background-color:transparent">
            </div>
        </div>
    </div></div></body></html>
    """

    return body


def notify(args):
    with database:
        database.create_tables([Film, Showtime])
        new = fetch_new_showtimes(args.lookforward_days, args.theatres, args.offerings)

        if len(new['showtimes']):
            print("New showtimes:")
            print(gen_formated_showtimes(new['showtimes'], args.theatres))
            ds = datetime.now().strftime("%Y-%m-%d")
            send_email(
                f"New AMC showtimes found as of {ds}!",
                gen_new_showtimes_email_body(new['showtimes'], args.theatres),
                args.email_sender,
                args.email_to,
                args.email_password,
                html=True
            )

        if new['exceptions'] == 0:
            print('Success')
        elif len(new['exceptions']) == MAX_EXCEPTIONS:
            print(f'Failed after encountering {MAX_EXCEPTIONS} exceptions')
        else:
            print(f"Success with {len(new['exceptions'])} exceptions")

        print("\nSummary:\n")
        print(f"  Found {len(new['showtimes'])} new showtimes and {len(new['films'])} new films")
        purged = purge_old_records()
        print(f"  Purged {purged['showtimes']} old showtimes and {purged['films']} films with no showtimes\n")

        if len(new['exceptions']) > 0:
            s = f"Encountered {len(new['exceptions'])} Exceptions:\n\n"
            for e in new['exceptions']:
                s += e[1] + "\n"
            print(s)

            e = new['exceptions'][-1][0]
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
                               help="To find new theatres, go to https://www.amctheatres.com/movie-theatres, search for the theatre you are interested in and click the link to \"Showtimes\" for that theatre. In the URL, after \"movie-theatres/\" there should be a location key and a theatre key, use that portion of the URL for this argument. For example: \"san-francisco/amc-metreon-16\"")
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
    debug_parser.add_argument('--pprint-showtimes', action='store_true', default=False,
                              help='Pretty prints all showtimes in the database.')
    debug_parser.add_argument('--print-showtimes-before', default=None,
                              help='Prints all showtimes in the database with date before the provided datetime in format 2023-08-05 7:34PM')
    debug_parser.add_argument('--delete-showtimes-before', default=None,
                              help='Deletes all showtimes in the database with date before the provided datetime in format 2023-08-05 7:34PM')

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



