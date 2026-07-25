import io
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
    # 强制 stdout 使用 UTF-8，确保中文日志正常显示
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    logger.add(
        sink=sys.stdout,
        level=appconfig.logging.console.level,
    )