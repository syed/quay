import json
import logging

from peewee import fn

from artifacts.plugins.modelregistry.constants import (
    MODELREGISTRY_ARTIFACT_TYPE,
    PLUGIN_NAME,
)
from artifacts.plugins.modelregistry.hf_utils import save_huggingface_metadata
from artifacts.plugins.modelregistry.modelregistry_models import (
    ModelRegistryMetadata,
    upsert_model_metadata,
)
from artifacts.utils.plugin_auth import generate_auth_token_for_read
from artifacts.utils.registry_utils import QuayRegistryClient

from auth.auth_context import get_authenticated_context, get_authenticated_user
from auth.validateresult import AuthKind, ValidateResult
from data.database import Manifest

logger = logging.getLogger(__name__)

quayRegistryClient = QuayRegistryClient(PLUGIN_NAME)


def handle_manifest_push(namespace_name, repo_name, tag_name, manifest: Manifest):
    logger.info(f"🔴🟣🔴🟣🔴🟣 handle manifest push {manifest}")

    # only parse model artifacts
    manifest_parsed = json.loads(manifest.internal_manifest_bytes.as_unicode())
    artifact_type = manifest_parsed.get("artifactType")

    if not artifact_type or artifact_type != MODELREGISTRY_ARTIFACT_TYPE:
        return

    logger.info(f"🔴🟣🔴🟣🔴🟣 MATCH {manifest_parsed}")

    # save_config_blob_metadata(manifest.id, manifest_parsed, namespace_name, repo_name)
    # Experiment: Huggingface integration
    save_huggingface_metadata(manifest)


def save_config_blob_metadata(manifest_id, manifest_parsed, namespace_name, repo_name):
    # metadata is stored in the annotations field
    annotations = manifest_parsed.get("annotations")
    config_blob_digest = manifest_parsed.get("config").get("digest")
    config_blob = get_blob_data(namespace_name, repo_name, config_blob_digest, quayRegistryClient)

    try:
        config_parsed = json.loads(config_blob.data)
        git_hash = manifest_parsed.get("annotations", {}).get("git-hash")
        upsert_model_metadata(manifest_id, config_parsed, git_hash)
    except json.JSONDecodeError:
        logger.warning(f"config {config_blob.data} is not a valid JSON")
        return
