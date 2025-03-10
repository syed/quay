import functools
import hashlib
import io
import json
import logging
import tarfile
from collections import namedtuple

import requests
import yaml
from flask import Response, request, stream_with_context
from huggingface_hub import hf_hub_url

from artifacts.plugins.modelregistry import PLUGIN_NAME
from artifacts.plugins.modelregistry.constants import MODELREGISTRY_ARTIFACT_TYPE
from artifacts.plugins.modelregistry.modelregistry_models import (
    ModelRegistryMetadata,
    get_manifest_sha_for_git_hash,
    upsert_model_metadata,
)
from artifacts.utils.plugin_auth import generate_auth_token_for_write
from artifacts.utils.registry_utils import (
    OCIArtifactManifest,
    OCIEmptyConfigLayer,
    OCILayer,
    QuayRegistryClient,
    calc_sha256digest,
    get_blob_data,
)

from app import app
from auth.credentials import validate_credentials
from auth.validateresult import AuthKind, ValidateResult
from data.database import Manifest
from data.model.repository import set_description

logger = logging.getLogger(__name__)

client = QuayRegistryClient(PLUGIN_NAME)

HF_BASE_URL = "https://huggingface.co"
HF_MODEL_METADATA_URL = f"{HF_BASE_URL}/api/models/%s/revision/%s"  # hf_repo, revision
HF_FILE_METADATA_URL = f"{HF_BASE_URL}/%s/resolve/%s/%s"  # hf_repo, revision, filename/path

EMPTY_LAYER_HASH = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

FileInfo = namedtuple("FileInfo", ["filename", "git_sha", "uncompressed_size"])


def get_revision_sha_from_manifest(namespace, repo, revision, token):
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

    logger.info(f"🔴🟣🔴🟣🔴🟣 auth {auth}, username: {auth.username}, password: {auth.password}")
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
            logger.info(f"🔴🟣🔴🟣🔴🟣 manifest not found {namespace}, {repo}, {revision} NONE")
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


def get_model_file(namespace, hf_repo, revision, filename, token):
    # Pull the manifest
    # fetch the layer which has the filename
    manifest_json = get_manifest_by_tag_or_git_hash(namespace, hf_repo, revision, token)
    if not manifest_json:
        return None

    manifest = OCIArtifactManifest.from_dict(manifest_json)
    manifest_git_hash = manifest_json.get("annotations", {}).get("git-hash")

    layers = manifest.layers
    for layer_num, layer in enumerate(layers):
        annotations = layer.annotations
        if annotations and annotations.get("filename") == filename:
            # if proxy cache is enabled, check huggingface for the file
            # if the file size is 0 in the layer, then we need
            # to download the file from huggingface
            file_git_hash = annotations.get("git-hash")
            return download_file(
                namespace,
                hf_repo,
                manifest,
                layer_num,
                file_git_hash,
                manifest_git_hash,
                revision,
                token,
            )

    return None


class ModelRegistryException(Exception):
    pass


def update_manifest_with_layer_and_retag(
    namespace, hf_repo, manifest, layer_idx, final_digest, final_size, tag, token
):
    layer = manifest.layers[layer_idx]
    layer.digest = final_digest
    layer.size = final_size

    # update manifest and tag
    response = client.upload_oci_artifact_manifest(namespace, hf_repo, manifest, tag, token)
    if response.status_code != 201:
        raise ModelRegistryException("manifest update failed")


def stream_file_to_registry_and_client(
    namespace, hf_repo, manifest, layer_idx, file_git_hash, manifest_git_hash, revision, token
):
    """
    Download the file from huggingface and stream it to both the
    client and the registry (blob chunk upload)
    """

    layer = manifest.layers[layer_idx]
    upload_response = client.start_upload_blob(namespace, hf_repo, token)
    upload_location = upload_response.headers.get("Location")
    logger.info(f"🔴🟣🔴🟣🔴🟣 upload location {upload_location}")
    if not upload_location:
        raise ModelRegistryException("upload location not found")

    download_url = (
        HF_BASE_URL
        + f"/{hf_repo}/resolve/{manifest_git_hash}/{layer.to_dict()['annotations']['filename']}"
    )
    response = requests.get(download_url, stream=True)
    if response.status_code != 200:
        return None

    final_length = int(response.headers.get("Content-Length"))

    sha256_hash = hashlib.sha256()

    def stream_fn():
        nonlocal upload_location
        nonlocal upload_response
        chunk_offset = 0
        for chunk in response.iter_content(chunk_size=102400):
            sha256_hash.update(chunk)
            upload_response = client.upload_oci_blob_chunk(
                namespace, hf_repo, upload_location, chunk, chunk_offset, token
            )

            upload_location = upload_response.headers.get("Location")
            if not upload_location:
                raise ModelRegistryException("upload location not found")
            chunk_offset += len(chunk)

            yield chunk

        # upload complete, finalize the blob
        final_digest = f"sha256:{sha256_hash.hexdigest()}"
        final_response = client.finalize_oci_blob_upload(
            namespace, hf_repo, upload_location, final_digest, token
        )
        logger.info(
            f"🔴🟣🔴🟣🔴🟣 finalize upload {final_response.status_code} {final_response.headers.get('Location')}"
        )
        update_manifest_with_layer_and_retag(
            namespace, hf_repo, manifest, layer_idx, final_digest, final_length, revision, token
        )

    return Response(
        stream_with_context(stream_fn()),
        headers={
            "etag": f'"{file_git_hash}"',
            "x-repo-commit": manifest_git_hash,
            "Content-Length": final_length,
        },
    )


def download_file(
    namespace, hf_repo, manifest, layer_idx, file_git_hash, manifest_git_hash, revision, token
):
    """
    if the file has not yet been downloaded, get the file from
    huggingface and store it in the registry at the same time
    stream the file to the client
    """

    layer = manifest.layers[layer_idx]
    if app.config.get("FEATURE_PROXY_CACHE") and layer.to_dict().get("size") == 0:
        return stream_file_to_registry_and_client(
            namespace,
            hf_repo,
            manifest,
            layer_idx,
            file_git_hash,
            manifest_git_hash,
            revision,
            token,
        )
    else:
        resp = client.get_oci_blob(namespace, hf_repo, layer.digest, token, follow_cdn=False)
        logger.info(f"🔴🟣🔴🟣🔴🟣 fetching blob {layer.digest} resp: {resp.status_code} {resp.headers}")
        headers = {
            "etag": f'"{file_git_hash}"',
            "x-repo-commit": manifest_git_hash,
            "Location": resp.headers.get("Location"),
        }
        del resp.headers["Accept-Ranges"]  # Do not support range requests (bug in HF lib)

        return Response(resp.data, headers=headers, status=resp.status_code)


def stream_file_from_huggingface():
    pass


def head_model_file(namespace, repo, tag, filename, token):
    # respond with the headers of the file
    # etag and x-repo-commit
    manifest = get_manifest_by_tag_or_git_hash(namespace, repo, tag, token)
    logger.info(f"🔴🟣🔴🟣🔴🟣 head_model_file {manifest}")
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
            upsert_model_metadata(
                manifest_id, metadata, manifest_parsed.get("annotations", {}).get("git-hash")
            )

            if remaining_markdown:
                # update repository description
                set_description(manifest.repository, remaining_markdown)


def proxy_huggingface_request(repo, filename):
    pass


def download_model_resolve_metadata_from_huggingface(hf_model_name, revision):
    response = requests.get(HF_MODEL_METADATA_URL % (hf_model_name, revision), allow_redirects=True)
    if response.status_code != 200:
        return None
    return response.json()
    pass


def download_file_metadata_from_huggingface(hf_model_name, revision, filename):
    response = requests.head(
        HF_FILE_METADATA_URL % (hf_model_name, revision, filename), allow_redirects=True
    )
    if response.status_code != 200:
        return None
    return FileInfo(
        filename=filename,
        git_sha=response.headers.get("etag"),
        uncompressed_size=response.headers.get("Content-Length"),
    )


def get_revision_sha_from_huggingface(hf_repo, revision):
    """ """
    response = download_model_resolve_metadata_from_huggingface(hf_repo, revision)
    if not response:
        return None
    return response.get("sha")


def push_manifest_to_registry(namespace, hf_repo, manifest, tag, token):
    client.upload_oci_artifact_manifest(namespace, hf_repo, manifest, tag, token)


def update_registry_manifest_from_hf(namespace, hf_repo, revision, token):
    """ """
    response = download_model_resolve_metadata_from_huggingface(hf_repo, revision)
    if not response:
        return None

    revision_git_sha = response.get("sha")
    filenames = [s.get("rfilename") for s in response.get("siblings")]
    file_mdata = []
    # gather metadata for all the files
    for filename in filenames:
        mdata = download_file_metadata_from_huggingface(hf_repo, revision, filename)
        file_mdata.append(mdata)

    manifest = build_empty_manifest(revision_git_sha, file_mdata)
    push_manifest_to_registry(namespace, hf_repo, manifest, revision, token)


def build_empty_manifest(git_sha, file_mdata: list[FileInfo]):
    config_layer = OCIEmptyConfigLayer()

    layers = []
    for mdata in file_mdata:
        layers.append(
            OCILayer(
                media_type="application/vnd.oci.image.layer.v1.tar",
                digest=EMPTY_LAYER_HASH,
                size=0,
                annotations={
                    "filename": mdata.filename,
                    "git-hash": mdata.git_sha,
                    "uncompressed-size": mdata.uncompressed_size,
                },
            )
        )

    manifest_annotations = {
        "git-hash": git_sha,
    }
    manifest = OCIArtifactManifest(
        MODELREGISTRY_ARTIFACT_TYPE, config_layer, layers, manifest_annotations
    )
    return manifest


def download_model_file_from_huggingface(hf_model_name, revision, filename):
    download_url = HF_BASE_URL + f"/{hf_model_name}/resolve/{revision}/{filename}"
    response = requests.get(download_url, stream=True)
    if response.status_code != 200:
        return None
    return response.content


def has_proxy_cache(namespace):
    return True


def check_proxy_cache_revision(func):
    """
    Update the OCI manifest of the local model repo
    if upstream has changed
    """

    @functools.wraps(func)
    def wrapper(auth_result, namespace, hf_namespace, hf_repo_name, revision, *args, **kwargs):
        if app.config.get("FEATURE_PROXY_CACHE") and has_proxy_cache(namespace):
            # check if upstream has changed, and if so, download and update the upstream model
            hf_repo = f"{hf_namespace}/{hf_repo_name}"
            token = generate_auth_token_for_write(auth_result, namespace, hf_repo)
            hf_sha = get_revision_sha_from_huggingface(hf_repo, revision)
            logger.info(
                f"🔴🟣🔴🟣🔴🟣 checking for cache in {namespace}, {hf_repo}, {revision}, "
                f"local_sha: {revision} remote_sha: {hf_sha}"
            )
            local_sha = get_revision_sha_from_manifest(namespace, hf_repo, revision, token)

            if not local_sha or hf_sha != local_sha:
                # start downloading a new model and update the sha
                logger.info("🔴🟣🔴🟣🔴🟣 updating local manifest downlading from huggingface")
                update_registry_manifest_from_hf(namespace, hf_repo, revision, token)

        return func(auth_result, namespace, hf_namespace, hf_repo_name, revision, *args, **kwargs)

    return wrapper
