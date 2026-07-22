
import datetime

from langgraph.runtime import Runtime
from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DbInfoState, DateInfoState


async def add_extra_context(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer("添加额外的上下文")
    dw_mysql_repository = runtime.context["dw_mysql_repository"]
    today = datetime.date.today()
    date_str = today.strftime("%Y-%m-%d")
    weekday = today.strftime("%A")
    quarter = f"{(today.month-1) // 3 + 1}"
    db = await dw_mysql_repository.get_db_info()
    date_info = DateInfoState(date=date_str, weekday=weekday, quarter=quarter)
    db_info = DbInfoState(**db)
    logger.info(f"[AddExtraContext] 数据库信息: {db_info}")
    logger.info(f"[AddExtraContext] 日期信息: {date_info}")
    return {
        "date_info": date_info,
        "db_info": db_info,
    }


