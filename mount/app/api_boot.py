from app.common import logger
from app.common import settings
from app.api import init_api

logger.init_logging(settings.LOG_LEVEL)

api = init_api()