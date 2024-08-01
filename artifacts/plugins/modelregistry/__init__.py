import logging

from .constants import PLUGIN_NAME, URL_PREFIX
from .modelregistry_routes import bp as modelregistry_bp
from artifacts.plugins_base import BaseArtifactPlugin, EventType
from .modelregistry_utils import handle_manifest_push

logger = logging.getLogger(__name__)


class ModelRegistryPlugin(BaseArtifactPlugin):
    def __init__(self, name):
        super().__init__(name)

    def register_routes(self, app):
        app.register_blueprint(modelregistry_bp, url_prefix=URL_PREFIX)

    def register_handlers(self, notification_manager):
        notification_manager.register_handler(EventType.PUSH_REPO, handle_manifest_push)

    def register_workers(self):
        pass

    def __str__(self):
        return self.name


plugin = ModelRegistryPlugin(PLUGIN_NAME)
