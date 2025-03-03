import io
import json
import logging
import tarfile

import yaml
from flask import Response, request

from artifacts.plugins.modelregistry import PLUGIN_NAME
from artifacts.plugins.modelregistry.modelregistry_models import (
    ModelRegistryMetadata,
    get_manifest_sha_for_git_hash,
    save_model_metadata,
)
from artifacts.utils.registry_utils import QuayRegistryClient, get_blob_data

from auth.credentials import validate_credentials
from auth.validateresult import AuthKind, ValidateResult
from data.database import Manifest
from data.model.repository import set_description

logger = logging.getLogger(__name__)

client = QuayRegistryClient(PLUGIN_NAME)


def get_revision_sha(namespace, repo, revision, token):
    # Pull the manifest
    # and return the sha of the model which is
    # stored as an annotation

    client = QuayRegistryClient(PLUGIN_NAME)
    manifest_response = client.get_oci_manifest(namespace, repo, revision, token)
    manifest = manifest_response.json
    return manifest.get("annotations", {}).get("git-hash")


def validate_hf_token():
    """
    Bearer token auth with username and password
    the token is a combination of username and password
    eg: Authorization: Bearer username=admin, password=secret
    """
    auth = request.authorization
    if not auth:
        # could be anonymous
        return ValidateResult(AuthKind.credentials, missing=True)
    username = auth.parameters.get("username")
    password = auth.parameters.get("password")

    if not username or not password:
        return ValidateResult(AuthKind.credentials, missing=True)

    auth_result, _auth_kind = validate_credentials(username, password)
    return auth_result.with_kind(AuthKind.credentials)


def get_manifest_by_tag_or_git_hash(namespace, repo, revision, token):
    # Pull the manifest
    # revision can be a tag or a commit hash
    # check if it is a git hash
    # if it is a git hash, get the manifest sha
    # and then pull the manifest
    client = QuayRegistryClient(PLUGIN_NAME)
    digest = get_manifest_sha_for_git_hash(revision)
    if digest:
        manifest_response = client.get_oci_manifest(namespace, repo, digest, token)
        if manifest_response.status_code != 200:
            return None
        manifest = manifest_response.json
        return manifest

    manifest_response = client.get_oci_manifest(namespace, repo, revision, token)
    if manifest_response.status_code != 200:
        return None

    manifest = manifest_response.json
    return manifest


def get_model_filenames(namespace, repo, tag, token):
    # Pull the manifest
    # and return the siblings of the model which is

    client = QuayRegistryClient(PLUGIN_NAME)
    manifest = get_manifest_by_tag_or_git_hash(namespace, repo, tag, token)

    if not manifest:
        return []

    layers = manifest.get("layers", [])
    filenames = []
    for layer in layers:
        annotation = layer.get("annotations", {})
        filename = annotation.get("filename")
        filenames.append(filename)
    return filenames


def get_model_file(namespace, repo, tag, filename, token):
    # Pull the manifest
    # fetch the layer which has the filename
    manifest = get_manifest_by_tag_or_git_hash(namespace, repo, tag, token)
    if not manifest:
        return None

    manifest_git_hash = manifest.get("annotations", {}).get("git-hash")

    layers = manifest.get("layers", [])
    client = QuayRegistryClient(PLUGIN_NAME)
    for layer in layers:
        annotation = layer.get("annotations", {})
        if annotation.get("filename") == filename:
            resp = client.get_oci_blob(namespace, repo, layer["digest"], token, follow_cdn=True)
            logger.info(
                f"🔴🟣🔴🟣🔴🟣 fetching blob {layer['digest']} resp: {resp.status_code} {resp.headers}"
            )
            headers = {}
            headers["etag"] = f'"{annotation.get("git-hash")}"'
            headers["x-repo-commit"] = manifest_git_hash
            del resp.headers["Accept-Ranges"]  # Do not support range requests (bug in HF lib)

            return Response(resp.data, headers=headers)
    return None


def head_model_file(namespace, repo, tag, filename, token):
    # respond with the headers of the file
    # etag and x-repo-commit
    manifest = get_manifest_by_tag_or_git_hash(namespace, repo, tag, token)
    if not manifest:
        return None

    resp_headers = {"x-repo-commit": manifest.get("annotations", {}).get("git-hash")}

    layers = manifest.get("layers", [])
    for layer in layers:
        annotation = layer.get("annotations", {})
        if annotation.get("filename") == filename:
            resp_headers["etag"] = f'"{annotation.get("git-hash")}"'
            resp_headers["Content-Length"] = int(annotation.get("uncompressed-size", 0))
            break

    return Response(headers=resp_headers)


def extract_metdata_from_modelcard(modelcard_data):
    lines = modelcard_data.splitlines()

    # Check for YAML front matter delimited by '---' at the start and end
    if lines[0].strip() == "---":
        # Find where the YAML block ends
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                yaml_content = "\n".join(lines[1:i])
                remaining_content = "\n".join(lines[i + 1 :])
                try:
                    metadata = yaml.safe_load(yaml_content)
                    return json.dumps(metadata, indent=4), remaining_content
                except yaml.YAMLError as e:
                    return None, None
        return None, None

    return None, None


def untar_response_data(tar_data):
    tar_buffer = io.BytesIO(tar_data)
    with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
        member = tar.getmembers()[0]  # Get the only member
        file_content = tar.extractfile(member).read()
    return file_content


def save_huggingface_metadata(manifest: Manifest):
    logger.info(f"🔴🟣🔴🟣🔴🟣 save_huggingface_metadata {manifest}")

    manifest_id = manifest.id
    manifest_parsed = json.loads(manifest.internal_manifest_bytes.as_unicode())

    for layer in manifest_parsed.get("layers", []):
        annotation = layer.get("annotations", {})
        if annotation.get("filename") == "README.md":
            # repository = manifest.repository
            # modelcard_data = get_blob_data(
            #     repository., repository.name, layer["digest"], client
            # )
            # metadata, remaining_markdown = extract_metdata_from_modelcard(modelcard_data)
            # if not metadata:
            metadata = {}
            remaining_markdown = None

            logger.info(f"🔴🟣🔴🟣🔴🟣 metadata {metadata}, remaining_markdown {remaining_markdown}")
            save_model_metadata(
                manifest_id, metadata, manifest_parsed.get("annotations", {}).get("git-hash")
            )

            if remaining_markdown:
                # update repository description
                set_description(manifest.repository, remaining_markdown)
