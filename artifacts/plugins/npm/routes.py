import logging
import uuid
from hashlib import sha512

from flask_login import current_user

from auth.auth_context import get_authenticated_user
from flask import Blueprint, request, session, jsonify, make_response

from artifacts.plugins.npm.auth import get_username_password
from artifacts.plugins.npm.models import create_token, NpmToken
from endpoints.api.user import conduct_signin
from util.cache import no_cache

bp = Blueprint("npm", __name__)
logger = logging.getLogger(__name__)


@bp.route('/test')
def test():
    return jsonify({'ok': 'test'}), 200


@bp.route('/-/v1/login', methods=['POST'])
def login_hostname():
    """
        Example request data:
        {"hostname":"syahmed-mac"}
    """
    logger.info(f'🔴 headers {request.headers}')
    return jsonify({'error': 'validation method not supported'}), 401


@bp.route('/-/user/org.couchdb.user:<user_id>', methods=['PUT'])
@no_cache
def login(user_id):
    """
    NPM login user
    ref: https://github.com/npm/registry/blob/master/docs/user/authentication.md#login
    """

    username, password = get_username_password()

    if not username or not password:
        return make_response(jsonify({'error': 'Invalid username or password'}), 401)

    (status, status_code, headers) =  conduct_signin(username, password)
    if 'message' in status:
        return make_response(jsonify(status), status_code)

    user = current_user.db_user()
    if not user:
        return make_response(jsonify({'error': 'Invalid username or password'}), 401)

    token_value = uuid.uuid4().hex
    token_name = f'{username}-{token_value[:-5]}'
    create_token(user, token_name, token_value, False)
    return make_response(jsonify({'ok': 'You have been authenticated', 'token': token_value}), 201)


@bp.route('/-/user/token/<token>', methods=['DELETE'])
def logout(token):
    """
    logout a user
    bearer token in the Authorization header identifies the user
    ref: https://docs.npmjs.com/cli/v7/commands/npm-logout
    ref: https://github.com/npm/registry/blob/master/docs/user/authentication.md#token-delete
    """
    # Perform any necessary logout operations
    token_key = sha512(token.encode('utf-8')).hexdigest()
    delete_token = NpmToken.delete().where(NpmToken.token_key == token_key)

    return jsonify({'ok': 'Logged out'}), 200
