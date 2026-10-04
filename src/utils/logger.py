import sys

from loguru import logger

from src.utils.env_wrapper import get_env_var

logger.remove(0)
logger.add(
    sys.stderr,
    level=get_env_var("LOG_LEVEL", "INFO").upper(),
    colorize=True,
    format="<m>{time:YYYY-MM-DD HH:mm:ss}</m> | <level>{level: <8}</level> | <c>{file}</c>:<c>{function}</c>:<c>{line}</c> - <level>{message}</level>",
)


def get_logger(name: str):
    return logger.bind(module=name)