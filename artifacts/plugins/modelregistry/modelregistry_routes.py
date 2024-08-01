import logging

from flask import Blueprint, request, jsonify, make_response, abort

from artifacts.plugins.modelregistry import PLUGIN_NAME, URL_PREFIX
from artifacts.plugins.modelregistry.modelregistry_models import ModelRegistryMetadata
from auth.decorators import process_oauth
from peewee import fn

from data.database import db

bp = Blueprint(PLUGIN_NAME, __name__)
logger = logging.getLogger(__name__)


@bp.route("/ping")
def ping():
    return jsonify({"ok": PLUGIN_NAME}), 200


@bp.route("/<namespace>/<repo>/search", methods=["POST"])
@process_oauth
def search(namespace, repo):
    """
    query format: https://www.postgresql.org/docs/current/functions-json.html#FUNCTIONS-SQLJSON-FILTER-EX-TABLE
    """

    query = request.json.get("query")
    if not query:
        abort(400, "json path query is required")

    rows = ModelRegistryMetadata.select(
        ModelRegistryMetadata.manifest,
        fn.jsonb_path_query(ModelRegistryMetadata.metadata, query),
    ).execute(db)
    res = [r.manifest.digest for r in rows]
    return jsonify(res), 200


# STEP2
# Cross repo query
# browsing models available to consume
# eg: description contains "llm", "code completion", etc


# UI
# show diff between two model configs
