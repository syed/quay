from enum import Enum
from types import FunctionType

from flask.testing import FlaskClient

from data.registry_model import registry_model
from endpoints.v2 import NameUnknown
import logging

logger = logging.getLogger(__name__)


class EventType(Enum):
    PUSH_REPO = "push_repo"
    DELETE_REPO = "delete_repo"

    @classmethod
    def from_str(cls, event_name):
        return cls.__dict__[event_name.upper()]


class ArtifactNotificationManager(object):
    def __init__(self):
        self.handlers = {
            EventType.PUSH_REPO: [],
            EventType.DELETE_REPO: [],
        }

    def register_handler(self, event_name: EventType, handler: FunctionType):
        self.handlers[event_name].append(handler)

    def notify_plugins(self, event_name, *args, **kwargs):
        event = EventType.from_str(event_name)
        if event not in self.handlers:
            return

        for handler in self.handlers[event]:
            try:
                handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in handler: {handler} with error: {e}")


class BaseArtifactPlugin(object):
    def __init__(self, plugin_name: str):
        self.name = plugin_name

    def register_routes(self, app):
        raise NotImplementedError("You must implement the register_routes method")

    def register_handlers(self, notification_handler: ArtifactNotificationManager):
        raise NotImplementedError("You must implement the notify method")

    def register_workers(self):
        raise NotImplementedError("You must implement the register_workers method")

    def __str__(self):
        return self.name


def get_artifact_repository(namespace_name, artifact_name):
    repository_ref = registry_model.lookup_repository(namespace_name, artifact_name)
    if repository_ref is None:
        raise NameUnknown("repository not found")
    return repository_ref


class ArtifactPluginQuayClient(FlaskClient):
    def __init__(self, plugin_name: str, *args, **kwargs):
        self.name = plugin_name
        super().__init__(*args, **kwargs)

    def create_artifact_repository(self, namespace_name, artifact_name):
        pass

    def create_artifact_manifest(self):
        pass

    def push_artifact_manifest(self):
        pass

    def tag_artifact_manifest(self):
        pass

    def upload_artifact(self):
        pass

    def get_artifact_repo(artifact_name: str):
        pass

    def get_artifact_manifest(artifact_name: str):
        pass

    def get_artifact_blob_url(self, artifact_digest: str):
        pass
