import sys
from pathlib import Path

from loguru import logger

from app.conf.app_config import appconfig
logger.remove()
# 使用默认format
if appconfig.logging.file.enable:
    path = Path(appconfig.logging.file.path)
    path.mkdir(parents=True, exist_ok=True)
    logger.add(
        sink=path / "app.log",
        rotation=appconfig.logging.file.rotation,
        retention=appconfig.logging.file.retention,
        level=appconfig.logging.file.level,
        encoding="utf-8"
    )
if appconfig.logging.console.enable:
    logger.add(
        sink=sys.stdout,
        level=appconfig.logging.console.level,
    )