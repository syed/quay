import logging

from flask import Blueprint, abort, jsonify, make_response, request
from peewee import fn

from artifacts.plugins.modelregistry import PLUGIN_NAME, URL_PREFIX, hf_utils
from artifacts.plugins.modelregistry.modelregistry_models import ModelRegistryMetadata

from auth.decorators import process_oauth
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

    query = request.get_json().get("query")
    if not query:
        abort(400, "json path query is required")

    rows = ModelRegistryMetadata.select(
        ModelRegistryMetadata.manifest,
        fn.jsonb_path_query(ModelRegistryMetadata.metadata, query),
    ).execute(db)
    res = [r.manifest.digest for r in rows]
    return jsonify(res), 200


# START: Huggingface compatible API for fetching models (EXPERIMENTAL)
@bp.route("/api/models/<namespace>/<repo>")
def hf_model_info(namespace, repo):
    revision = "main"  # default to main
    return hf_model_info_by_revision(namespace, repo, revision)


@bp.route("/api/models/<namespace>/<repo>/revision/<revision>")
def hf_model_info_by_revision(namespace, repo, revision):
    tag = revision
    model_info = {
        "id": f"{namespace}/{repo}",
        "modelId": f"{namespace}/{repo}",
        "sha": hf_utils.get_revision_sha(namespace, repo, tag),
    }
    return jsonify(model_info), 200


# END: Huggingface compatible API for fetching models (EXPERIMENTAL)

# STEP2
# Cross repo query
# browsing models available to consume
# eg: description contains "llm", "code completion", etc


# UI
# show diff between two model configs
