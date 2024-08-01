import json
import logging

from peewee import fn

from artifacts.plugins.modelregistry.constants import MODELREGISTRY_ARTIFACT_TYPE, PLUGIN_NAME
from artifacts.plugins.modelregistry.modelregistry_models import (
    save_model_metadata,
    ModelRegistryMetadata,
)
from artifacts.utils.plugin_auth import generate_auth_token_for_read
from artifacts.utils.registry_utils import QuayRegistryClient
from auth.auth_context import get_authenticated_user, get_authenticated_context
from auth.validateresult import AuthKind, ValidateResult
from data.database import Manifest

logger = logging.getLogger(__name__)

quayRegistryClient = QuayRegistryClient(PLUGIN_NAME)


def handle_manifest_push(namespace_name, repo_name, tag_name, manifest: Manifest):
    logger.info(f"🔴🟣🔴🟣🔴🟣 manifest {manifest}")

    # only parse model artifacts
    manifest_parsed = json.loads(manifest.internal_manifest_bytes.as_unicode())
    artifact_type = manifest_parsed.get("artifactType")

    if not artifact_type or artifact_type != MODELREGISTRY_ARTIFACT_TYPE:
        return

    # metadata is stored in the annotations field
    annotations = manifest_parsed.get("annotations")
    config_blob_digest = manifest_parsed.get("config").get("digest")

    user = get_authenticated_user()
    auth_context = get_authenticated_context()

    auth_result = ValidateResult(AuthKind.credentials, user=user)
    grant_token = generate_auth_token_for_read(auth_result, namespace_name, repo_name)

    config_blob = quayRegistryClient.get_oci_blob(
        namespace_name, repo_name, config_blob_digest, grant_token
    )

    try:
        parsed_config = json.loads(config_blob.data)
        save_model_metadata(manifest.id, parsed_config)
    except json.JSONDecodeError:
        logger.warning(f"config {config_blob.data} is not a valid JSON")
        return
