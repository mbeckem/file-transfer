import logging
logging.basicConfig(level=logging.DEBUG)

import os
import sys

from app.main import Application, ApplicationType

logger = logging.getLogger(__name__)


def get_app_type():
    v = os.environ["TYPE"]
    if v == "":
        logger.critical("Invalid run type: Use 'dev' or 'prod'")
        sys.exit(1)

    if v == "dev":
        return ApplicationType.dev
    elif v == "prod":
        return ApplicationType.prod
    else:
        logger.critical("Invalid run type: %r", v)
        sys.exit(1)


def main():
    app = Application(apptype=get_app_type())
    app.run()

if __name__ == "__main__":
    main()
