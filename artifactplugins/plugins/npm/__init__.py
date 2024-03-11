import logging

from .routes import bp as npm_bp
from ...plugin import BaseArtifactPlugin
from alembic import command
from alembic.config import Config



PLUGIN_NAME = "npm"

logger = logging.getLogger(__name__)


class NpmPlugin(BaseArtifactPlugin):
    def __init__(self, name):
        super().__init__(name)

    def register_routes(self, app):
        logger.info(f"Registering routes for {PLUGIN_NAME}")
        app.register_blueprint(npm_bp, url_prefix="/npm")

    def register_workers(self):
        pass

    def __str__(self):
        return self.name


plugin = NpmPlugin(PLUGIN_NAME)
