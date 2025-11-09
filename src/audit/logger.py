import sys
from loguru import logger


def configure_logging():
    logger.remove()
    logger.add(sys.stderr, level="INFO", backtrace=True, diagnose=False, serialize=True)
    return logger