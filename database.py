from datetime import datetime
from peewee import SqliteDatabase, Model, CharField, DateTimeField, ForeignKeyField


database = SqliteDatabase(None)


class BaseModel(Model):
    class Meta:
        database = database


class Film(BaseModel):
    key = CharField(unique=True, primary_key=True)
    title = CharField()


class Showtime(BaseModel):
    film = ForeignKeyField(Film, backref='showtimes')
    theatre = CharField()
    date = DateTimeField()
    link = CharField()


class PurgeOldRecordsResult(object):

    def __init__(self):
        self.showtimes = 0
        self.films = 0


# Removes Showtimes with date older than the current date and Films with no showtimes.
def purge_old_records():
    d = datetime.combine(datetime.now().date(), datetime.min.time())

    result = PurgeOldRecordsResult()

    q = Showtime.delete().where(Showtime.date.truncate('day') < d)
    result.showtimes = q.execute()

    for film in Film.select():
        if film.showtimes.count() == 0:
            result.films += film.delete_instance()

    return result


