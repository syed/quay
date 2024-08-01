from peewee import CharField, ForeignKeyField
from playhouse.postgres_ext import BinaryJSONField

from data.database import BaseModel, Manifest


class ModelRegistryMetadata(BaseModel):
    manifest = ForeignKeyField(Manifest)
    metadata = BinaryJSONField()


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


def save_model_metadata(manifest_id, metadata):
    ModelRegistryMetadata(manifest_id=manifest_id, metadata=metadata).save()


def delete_model_metadata(manifest_id):
    ModelRegistryMetadata.delete().where(manifest_id=manifest_id).execute()
