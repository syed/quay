import logging

from flask import Blueprint, request, jsonify, make_response, abort

from artifacts.plugins.modelregistry import PLUGIN_NAME

bp = Blueprint(PLUGIN_NAME, __name__)
logger = logging.getLogger(__name__)


@bp.route("/ping")
def ping():
    return jsonify({"ok": "test"}), 200


@bp.route("/-/v1/search")
def search():
    """
    Example request data:
    {"hostname":"syahmed-mac"}
    """
    pass
