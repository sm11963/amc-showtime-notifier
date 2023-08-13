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

