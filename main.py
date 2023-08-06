from bs4 import BeautifulSoup
import argparse
import requests
import re

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
    ('san-francisco', 'amc-metreon-16')
#    ('san-francisco', 'amc-dine-in-sunnyvale-12'),
#    ('san-francisco', 'amc-dine-in-sunnyvale-12'),
#    ('san-jose', 'amc-saratoga-14'),
#    ('san-jose', 'amc-eastridge-15')
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
THEATRE_SHOWTIMES_URL='https://www.amctheatres.com/movie-theatres/{location}/{theatre_key}/showtimes/all/{datestr}/{theatre_key}/{offering}'


class Film(object):

    def __init__(self, key, title, showtimes):
        self.key = key
        self.title = title
        self.showtimes = showtimes

    def __repr__(self):
        formatted_showtimes = ', '.join(self.showtimes)
        return f"Film({self.key} [{self.title}], showtimes=[{formatted_showtimes}])"


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
            showtimes.append(showtime_soup.find('a').text)

        films.append(Film(film_key, film_title, showtimes))

    return films


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Alert when new showtimes are available.')
    parser.add_argument('lookforward_days', type=int,
                        help='How many days in the future to process showtimes')
    args = parser.parse_args()


    print(fetch_showtimes(theatres[0][0], theatres[0][1], '2023-08-05', offerings[0]))


