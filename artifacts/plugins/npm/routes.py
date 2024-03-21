from flask import Blueprint, request, session, jsonify

from auth.credentials import validate_credentials
from auth.decorators import process_basic_auth
from util.cache import no_cache

bp = Blueprint("npm", __name__)


@bp.route('/test')
def test():
    return jsonify({'ok': 'test'}), 200


@bp.route('/-/v1/login', methods=['POST'])
def login_hostname():
    """
        Example request data:
        {"hostname":"syahmed-mac"}
    """
    return jsonify({'error': 'validation method not supported'}), 401


@bp.route('/-/user/<user_id>', methods=['PUT'])
@no_cache
def login_user(user_id):
    """
    Example request:

    {
        "_id":"org.couchdb.user:admin",
        "name":"admin",
        "password":"password",
        "email":"abcd@tst.com",
        "type":"user","roles":[],
        "date":"2023-06-16T04:15:31.739Z"
    }

    example response: 201

    {
      "ok": "you are authenticated as 'test'",
      "token": "SPvNpml3LYe+Gs2aamTr7g=="
    }

    """

    user_data = request.get_json()
    username = user_data.get('name')
    password = user_data.get('password')

    if not username or not password:
        return jsonify({'error': 'Invalid username or password'}), 401

    result = validate_credentials(username, password)

    return jsonify({'ok': 'You have been authenticated', 'token': 'randomtoken'}), 201


@bp.route('/-/user/token/<token>', methods=['DELETE'])
def logout_user(token):
    # Perform any necessary logout operations
    return jsonify({'ok': 'Logged out'}), 200
