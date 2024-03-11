
class BaseArtifactPlugin(object):
    def __init__(self, plugin_name: str):
        self.name = plugin_name

    def register_routes(self, app):
        raise NotImplementedError("You must implement the init_routes method")

    def run_db_migrations(self, db_url: str):
        raise NotImplementedError("You must implement the init_db method")

    def register_workers(self):
        raise NotImplementedError("You must implement the init_workers method")

    def __str__(self):
        return self.name
