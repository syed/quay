import logging

from flask import Blueprint, abort, jsonify, make_response, request
from peewee import fn

from artifacts.plugins.modelregistry import PLUGIN_NAME, URL_PREFIX, hf_utils
from artifacts.plugins.modelregistry.hf_utils import (
    check_proxy_cache_revision,
    download_model_resolve_metadata_from_huggingface,
    get_revision_sha_from_huggingface,
    has_proxy_cache,
    update_registry_manifest_from_hf,
    validate_hf_token,
)
from artifacts.plugins.modelregistry.modelregistry_models import ModelRegistryMetadata
from artifacts.utils.plugin_auth import (
    generate_auth_token_for_read,
    generate_auth_token_for_write,
    validate_plugin_auth,
)

from app import app
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


@bp.route("/api/models")
def hf_model_list():
    return jsonify([]), 200


@bp.route("<namespace>/api/models/<hf_repo>")
def hf_model_info(namespace, hf_repo):
    revision = "main"  # default to main
    logger.info(f"🔴🟣🔴🟣🔴🟣 hf_model_info {namespace}, {hf_repo}")
    return hf_model_info_by_revision(namespace, hf_repo, revision)


@bp.route("<namespace>/api/models/<hf_namespace>/<hf_repo_name>/revision/<revision>")
@validate_plugin_auth(validate_hf_token)
@check_proxy_cache_revision
def hf_model_info_by_revision(auth_result, namespace, hf_namespace, hf_repo_name, revision):
    # revision can be a tag or a commit hash
    # try with tag first
    hf_repo = f"{hf_namespace}/{hf_repo_name}"
    token = generate_auth_token_for_read(auth_result, namespace, hf_repo)
    revision_sha = hf_utils.get_revision_sha_from_manifest(namespace, hf_repo, revision, token)

    logger.info(
        f"🔴🟣🔴🟣🔴🟣 hf_model_info_by_revision {namespace}, repo:{hf_repo}, revision:{revision}, sha:{revision_sha}"
    )
    if not revision_sha:
        return jsonify({"error": "revision not found"}), 404

    model_info = {
        "id": f"{hf_repo}",
        "modelId": f"{hf_repo}",
        "sha": revision_sha,
        "siblings": [
            {"rfilename": filename}
            for filename in hf_utils.get_model_filenames(namespace, hf_repo, revision, token)
        ],
    }

    return jsonify(model_info), 200


@bp.route(
    "/<namespace>/<hf_namespace>/<hf_repo>/resolve/<revision>/<path:filename>", methods=["HEAD"]
)
@validate_plugin_auth(validate_hf_token)
def head_hf_model_file(auth_result, namespace, hf_namespace, hf_repo, revision, filename):
    tag = revision
    hf_repo = f"{hf_namespace}/{hf_repo}"
    token = generate_auth_token_for_write(auth_result, namespace, hf_repo)
    response = hf_utils.head_model_file(namespace, hf_repo, tag, filename, token)

    logger.info(f"🔴🟣🔴🟣🔴🟣 head_hf_model_file {namespace}, {hf_repo}, {tag}, {filename}, {response}")

    if not response:
        return {"error": "manifest not found"}, 404

    logger.info(
        f"🔴🟣🔴🟣🔴🟣 head_hf_model_file {namespace}, {hf_repo}, {tag}, {filename}, {response.status_code}"
    )

    return response


#     if response.status_code == 200:
#         return response
#

# if tag fails, try with commit hash
# manifest = hf_utils.get_manifest_for_commit_hash(namespace, repo, revision, token)


@bp.route("/<namespace>/<hf_namespace>/<hf_repo_name>/resolve/<revision>/<path:filename>")
@validate_plugin_auth(validate_hf_token)
def fetch_hf_model_file(auth_result, namespace, hf_namespace, hf_repo_name, revision, filename):
    hf_repo = f"{hf_namespace}/{hf_repo_name}"
    token = generate_auth_token_for_write(auth_result, namespace, hf_repo)
    return hf_utils.get_model_file(namespace, hf_repo, revision, filename, token)


# END: Huggingface compatible API for fetching models (EXPERIMENTAL)

# STEP2
# Cross repo query
# browsing models available to consume
# eg: description contains "llm", "code completion", etc


# UI
# show diff between two model configs
