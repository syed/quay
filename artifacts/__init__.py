import importlib
import pkgutil

from artifacts.plugins_base import ArtifactNotificationManager
from flask import Blueprint
from artifacts import plugins
import sys
import logging

from artifacts.utils.registry_utils import QuayRegistryClient


ARTIFACT_URL_PREFIX = "/artifacts"

logger = logging.getLogger(__name__)

current_module = sys.modules[__name__]
current_package = current_module.__package__

plugins_bp = Blueprint("artifacts", __name__)

notification_manager = ArtifactNotificationManager()

active_plugins = {}


def discover_plugins():
    # All plugins go in the `plugins` directory and
    # each plugin exposes the `plugin` variable in its
    # __init__.py file

    return {
        pkg.name: importlib.import_module(f".plugins.{pkg.name}", package=current_package).plugin
        for pkg in pkgutil.iter_modules(plugins.__path__)
    }


def init_plugins(application):
    # TODO: check if plugin is enabled
    # TODO: pass plugin specific config
    global active_plugins
    active_plugins.update(discover_plugins())
    logger.info("🔴🟣🔴🟣🔴🟣 active_plugins: %s", active_plugins)
    for plugin_obj in active_plugins.values():
        plugin_obj.register_routes(plugins_bp)
        try:
            plugin_obj.register_handlers(notification_manager)
        except NotImplementedError:
            logger.info("No handlers registered for plugin: %s", plugin_obj.name)

    application.register_blueprint(plugins_bp, url_prefix=ARTIFACT_URL_PREFIX)
