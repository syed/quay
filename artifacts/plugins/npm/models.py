import uuid
from datetime import datetime
from hashlib import sha512

from peewee import CharField, BooleanField, DateTimeField
from playhouse.postgres_ext import ArrayField

from data.database import BaseModel, QuayUserField


class NpmToken(BaseModel):
    token_name = CharField()
    token_key = CharField()
    read_only = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    cidr_whitelist = ArrayField(CharField, null=True)
    user = QuayUserField(allows_robots=False)


def create_token(user, token_name, token_value, read_only=False):
    token_key = sha512(token_value.encode('utf-8')).hexdigest()
    token = NpmToken(token_name=token_name, token_key=token_key, read_only=read_only, user=user)
    token.save()
    return token


