from artifacts.plugins.python.constants import (
    PLUGIN_NAME,
    PYTHON_SDIST_MEDIA_TYPE,
    PYTHON_WHEEL_MEDIA_TYPE,
)
from artifacts.utils.registry_utils import (
    OCIArtifactManifest,
    OCILayer,
    QuayRegistryClient,
)

quayRegistryClient = QuayRegistryClient(PLUGIN_NAME)


def get_layer_media_type(filetype):
    if filetype == "bdist_wheel":
        return PYTHON_WHEEL_MEDIA_TYPE
    elif filetype == "sdist":
        return PYTHON_SDIST_MEDIA_TYPE


def get_python_packages_for_repo(namespace, repo_name, grant_token):
    """
    pypi is a bad protocol. It requests all the versions for a package
    and then decides which one to download instead of just asking the server
    to give a specific version or the latest version
    """
    all_tags = quayRegistryClient.get_all_tags(namespace, repo_name, grant_token)
    for tag_name in all_tags:
        print(f"🟣🟣🟣🔴🔴🔴🔴 getting tag for  {namespace}/{repo_name}:{tag_name}")
        manifest_response = quayRegistryClient.get_oci_manifest(
            namespace, repo_name, tag_name, grant_token
        )
        print(f"🟣🟣🟣🔴🔴🔴🔴 manifest response {manifest_response}")
        if manifest_response.status_code != 200:
            continue

        manifest = manifest_response.get_json()

        python_pkg = {
            "name": repo_name,
            "files": [],
        }

        for layer in manifest["layers"]:
            python_pkg["files"].append(
                {
                    "filename": layer["annotations"]["filename"],
                    "requires-python": layer["annotations"]["requires-python"],
                    "url": f'/artifacts/python/download/{namespace}/{repo_name}/{layer["digest"]}/{layer["annotations"]["filename"]}',
                    "hashes": {"sha256": layer["digest"].replace("sha256:", "")},
                }
            )

        return python_pkg


def update_manifest_with_new_layer(manifest: OCIArtifactManifest, layer: OCILayer):
    for i, l in enumerate(manifest.layers):
        if l.annotations.get("filename") == layer.annotations.get("filename"):
            manifest.layers[i] = layer
            return

    manifest.layers.append(layer)
