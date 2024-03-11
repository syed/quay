from peewee import CharField

from data.database import BaseModel


class NpmPackage(BaseModel):
    name = CharField()
    version = CharField()
