import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader, select_autoescape

jenv = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape()
)

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


def gen_formated_showtimes(showtimes, theatres):
    by_films = {}
    theatre_keys = [t.split('/')[-1] for t in theatres]
    for fk in set([x.film.key for x in showtimes]):
        ts = [(t, [s for s in showtimes if s.film.key == fk and s.theatre == t]) for t in theatre_keys]
        by_films[fk] = [t for t in ts if len(t[1]) > 0]

    body = ""
    for (k, ts) in by_films.items():

        body += k + "\n"
        for t in ts:
            body += f"  {t[0]}\n"
            for s in t[1]:
                ds = s.date.strftime("%Y-%m-%d %I:%M %p")
                body += f"    [{ds}] - {s.link}\n"
            body += "\n"

    return body


def gen_new_showtimes_html(showtimes, theatres):
    template = jenv.get_template("email.html.jinja")

    by_films = {}
    theatre_keys = [t.split('/')[-1] for t in theatres]
    for fk in set([x.film.key for x in showtimes]):
        ts = [(t, [s for s in showtimes if s.film.key == fk and s.theatre == t]) for t in theatre_keys]
        by_films[fk] = [t for t in ts if len(t[1]) > 0]
    return template.render(by_films=by_films,
                           now=datetime.now().strftime('%Y-%d-%m %H:%M'))

