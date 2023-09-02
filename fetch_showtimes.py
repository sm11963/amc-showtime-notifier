import backoff
import requests
import time
from bs4 import BeautifulSoup
from config import FETCH_DELAY, MAX_EXCEPTIONS, BASE_URL, THEATRE_SHOWTIMES_URL
from database import Showtime, Film
from datetime import datetime, timedelta


class ShowtimeResult(object):

    def __init__(self, datetime, theatre, link):
        self.datetime = datetime
        self.theatre = theatre
        self.link = link


class FilmResult(object):

    def __init__(self, key, title, showtimes):
        self.key = key
        self.title = title
        self.showtimes = showtimes

    def __repr__(self):
        formatted_showtimes = ', '.join([str(x.datetime) for x in self.showtimes])
        return f"FilmResult({self.key} [{self.title}], showtimes=[{formatted_showtimes}])"


class NewShowtimesResult(object):

    def __init__(self):
        self.films = []
        self.showtimes = []
        self.exceptions = []

    def append(self, other_result):
        self.films += other_result.films
        self.showtimes += other_result.showtimes
        self.exceptions += other_result.exceptions


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

            status_soup = showtime_soup.find(class_="ShowtimeButtons-status")
            if status_soup is not None and status_soup.text.lower() == "available soon":
                continue
            a_soup = showtime_soup.find('a')
            # if there are no offerings for the given date, AMC might redirect and provide all offerings. Double check that that this showtime is for the requested offering by checking the link which should include the offering key.
            link = BASE_URL + a_soup['href']
            if offering not in link:
                continue

            dt = datetime.strptime(datestr + ' ' + a_soup.text, '%Y-%m-%d %I:%M%p')
            showtimes.append(ShowtimeResult(dt, theatre_key, link))

        if len(showtimes) > 0:
            films.append(FilmResult(film_key, film_title, showtimes))

    return films


def process_film_result(film_result):
    new = NewShowtimesResult()

    film = Film.get_or_none(key = film_result.key)
    if film is None:
        film = Film.create(key = film_result.key,
                           title = film_result.title)
        new.films.append(film)

    for showtime_result in film_result.showtimes:
        s = Showtime.get_or_none(film = film,
                                 theatre = showtime_result.theatre,
                                 date = showtime_result.datetime)
        if s is None:
            s = Showtime.create(film = film,
                                theatre = showtime_result.theatre,
                                date = showtime_result.datetime,
                                link = showtime_result.link)
            new.showtimes.append(s)
        else:
            s.link = showtime_result.link
            s.save()

    return new


def fetch_new_showtimes(lookforward_days, theatres, offerings, post_request_callback):
    result = NewShowtimesResult()
    exceptions = []
    first_fetch = True
    start_date = datetime.now()

    for i in range(0, lookforward_days):
        if len(result.exceptions) >= MAX_EXCEPTIONS:
            break

        date = start_date + timedelta(days=i)
        datestr = date.strftime('%Y-%m-%d')

        for theatre in theatres:
            if len(result.exceptions) >= MAX_EXCEPTIONS:
                break

            for offering in offerings:
                if not first_fetch:
                    # Space out requests a bit to avoid potentially getting throttled
                    time.sleep(FETCH_DELAY)

                try:
                    (theatre_location, theatre_key) = theatre.split('/')
                    film_results = fetch_showtimes(theatre_location, theatre_key, datestr, offering)
                except Exception as err:
                    result.exceptions.append((err, f"Encountered exception after retries requesting for {theatre}, {datestr}, {offering}"))
                    post_request_callback(err)
                    if len(result.exceptions) >= MAX_EXCEPTIONS:
                        break
                    else:
                        continue

                post_request_callback(None)

                for film_result in (x for x in film_results if len(x.showtimes) > 0):
                    n = process_film_result(film_result)
                    result.append(n)

                first_fetch = False

    return result
