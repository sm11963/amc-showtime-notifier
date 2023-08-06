from peewee import SqliteDatabase, Model, CharField, DateTimeField, ForeignKeyField
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import argparse
import requests
import re
import time
import sys

# To find new theatres, go to:
#
#   https://www.amctheatres.com/movie-theatres
#
# Search for the theatre you are interested in and click the link to "Showtimes" for that theatre.
# The URL should be something like:
#
#   https://www.amctheatres.com/movie-theatres/{location}/{theatre-key}/showtimes/all/{date}/{theatre-key}/all
#
# For example:
#
#   https://www.amctheatres.com/movie-theatres/san-francisco/amc-metreon-16/showtimes/all/2023-08-05/amc-metreon-16/all
#
# Results in:
#
#  `('san-francisco', 'amc-metreon-16'),`
#
theatres = [
    # ({location}, {theatre_key})
    ('san-francisco', 'amc-metreon-16'),
    ('san-francisco', 'amc-dine-in-sunnyvale-12'),
    ('san-jose', 'amc-saratoga-14'),
    ('san-jose', 'amc-eastridge-15')
]

# Theatre formats to lookup (AMC seems to name these offerings). These values can be found by going to amctheatres.com and opening the showtimes for a theatre.
# There will be an option to select different formats, the default selection is currently "Premium Offerings". Selecting a different option will put the key for the format in the URL. For example, selecting "Dolby Cinema at AMC" will result in the following URL:
#
#   https://www.amctheatres.com/movie-theatres/{location}/{theatre-key}/showtimes/all/{date}/{theatre-key}/all
#
# This script was intially written to specifically find when new Dobly Cinema showtimes are released and so we only filter for this format.
offerings = [
    'dolbycinemaatamcprime'
]

#
BASE_URL='https://www.amctheatres.com'
THEATRE_SHOWTIMES_URL=BASE_URL + '/movie-theatres/{location}/{theatre_key}/showtimes/all/{datestr}/{theatre_key}/{offering}'

db = SqliteDatabase('amc_showtimes.db')


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


class BaseModel(Model):
    class Meta:
        database = db


class Film(BaseModel):
    key = CharField(unique=True, primary_key=True)
    title = CharField()


class Showtime(BaseModel):
    film = ForeignKeyField(Film, backref='showtimes')
    theatre = CharField()
    date = DateTimeField()
    link = CharField()


# Fetch the Films with showtimes that have available tickets given a date and theatre
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

def fetch_new_showtimes(lookforward_days):
    print(f"Starting requests for {lookforward_days} days, {len(theatres)} theatres, and {len(offerings)} offerings ({args.lookforward_days * len(theatres) * len(offerings)} requests)")
    results = {
        'films': [],
        'showtimes': []
    }
    start_date = datetime.now()
    for i in range(0, lookforward_days):
        date = start_date + timedelta(days=i)
        datestr = date.strftime('%Y-%m-%d')

        for theatre in theatres:
            for offering in offerings:
                film_results = fetch_showtimes(theatre[0], theatre[1], datestr, offering)

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
                time.sleep(0.75)

    print()
    return results


def notify(args):
    with db:
        db.create_tables([Film, Showtime])
        new = fetch_new_showtimes(args.lookforward_days)

        if len(new['showtimes']):
            print("New showtimes:")
            for showtime in new['showtimes']:
                print(f'{showtime.date} - {showtime.film} ({showtime.link})')

        print("\nSummary:\n")
        print(f"  Found {len(new['showtimes'])} new showtimes and {len(new['films'])} films")
        purged = purge_old_records()
        print(f"  Purged {purged['showtimes']} old showtimes and {purged['films']} films with no showtimes\n")


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


def debug(args):
    with db:

        if args.drop_tables:
            db.drop_tables([Film, Showtime])

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

        if args.print_showtimes_before:
            d = datetime.strptime(args.print_showtimes_before, '%Y-%m-%d %I:%M%p')
            for showtime in Showtime.select().where(Showtime.date < d):
                print(f'{showtime.date} - {showtime.film}')

        if args.delete_showtimes_before:
            d = datetime.strptime(args.delete_showtimes_before, '%Y-%m-%d %I:%M%p')
            q = Showtime.delete().where(Showtime.date < d)
            count_removed = q.execute()
            print(f'{count_removed} records removed')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Alert when new showtimes are available.')
    subparsers = parser.add_subparsers()

    notify_parser = subparsers.add_parser('notify', help='Check for and notify if there are new showtimes')
    notify_parser.set_defaults(func=notify)
    notify_parser.add_argument('lookforward_days', type=int,
                                help='How many days in the future to process showtimes')


    debug_parser = subparsers.add_parser('debug', help='Debug database')
    debug_parser.set_defaults(func=debug)
    debug_parser.add_argument('--drop-tables', action='store_true', default=False,
                              help='Drops the tables.')
    debug_parser.add_argument('--delete-film', default=None,
                              help='Delete the film and showtimes with the given film key')
    debug_parser.add_argument('--purge-old-records', action='store_true', default=False,
                              help='Removes showtimes older than the current datetime and any films with no showtimes.')
    debug_parser.add_argument('--clear-links', action='store_true', default=False,
                              help='Replaces all the Showtime links with empty string')
    debug_parser.add_argument('--print-films', action='store_true', default=False,
                              help='Prints all films in the database.')
    debug_parser.add_argument('--print-showtimes', action='store_true', default=False,
                              help='Prints all showtimes in the database.')
    debug_parser.add_argument('--print-showtimes-before', default=None,
                              help='Prints all showtimes in the database with date before the provided datetime in format 2023-08-05 7:34PM')
    debug_parser.add_argument('--delete-showtimes-before', default=None,
                              help='Deletes all showtimes in the database with date before the provided datetime in format 2023-08-05 7:34PM')

    args = parser.parse_args()

    args.func(args)



