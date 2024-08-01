import logging
import os

from active_migration import ActiveDataMigration
from app import app

logger = logging.getLogger(__name__)


def current_migration():
    logger.info(
        f"🔴🟣🔴🟣🔴🟣 ActiveDataMigration: {ActiveDataMigration}, SETUP_COMPLETE: {app.config.get('SETUP_COMPLETE', False)}"
    )
    if os.getenv("ENSURE_NO_MIGRATION", "").lower() == "true":
        raise Exception("Cannot call migration when ENSURE_NO_MIGRATION is true")

    if not app.config.get("SETUP_COMPLETE", False):
        return "head"
    else:
        if ActiveDataMigration is not None:
            return ActiveDataMigration.alembic_migration_revision
        else:
            return "head"


def main():
    print(current_migration())


if __name__ == "__main__":
    main()
