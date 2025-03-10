from peewee import CharField, ForeignKeyField, TextField
from playhouse.postgres_ext import BinaryJSONField

from data.database import BaseModel, Manifest


class ModelRegistryMetadata(BaseModel):
    manifest = ForeignKeyField(Manifest)
    metadata = BinaryJSONField()
    git_hash = TextField(null=True)


def get_model_metadata(manifest_id):
    try:
        result = ModelRegistryMetadata.select(ModelRegistryMetadata.metadata).where(
            ModelRegistryMetadata.manifest.id == manifest_id
        )
        if not result:
            return None

        return [r.metadata for r in result]
    except ModelRegistryMetadata.DoesNotExist:
        return None


def upsert_model_metadata(manifest_id, metadata, git_hash):
    # check if there's an existing record
    existing = ModelRegistryMetadata.get_or_none(ModelRegistryMetadata.git_hash == git_hash)
    if existing:
        existing.metadata = metadata
        existing.manifest_id = manifest_id
        existing.save()
    else:
        ModelRegistryMetadata(manifest_id=manifest_id, metadata=metadata, git_hash=git_hash).save()


def delete_model_metadata(manifest_id):
    ModelRegistryMetadata.delete().where(manifest_id=manifest_id).execute()


#### HF UTILS ####
def get_manifest_sha_for_git_hash(git_hash):
    result = ModelRegistryMetadata.get_or_none(ModelRegistryMetadata.git_hash == git_hash)

    return result.manifest.digest if result else None
