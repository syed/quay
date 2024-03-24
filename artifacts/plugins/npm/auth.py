from flask import request


def get_bearer_token():
    return request.headers.get('Authorization').split(' ')[1] if request.headers.get('Authorization') else None


def get_username_password():
    user_data = request.get_json()
    username = user_data.get('name')
    password = user_data.get('password')
    return username, password


