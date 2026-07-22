from langgraph.runtime import Runtime
from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer("校验SQL语句")
    sql = state["sql"]
    dw_repository = runtime.context["dw_mysql_repository"]
    try:
        await dw_repository.validate(sql)
        logger.info(f"[ValidateSQL] 校验通过")
        return {"error": None}
    except Exception as e:
        logger.error(f"[ValidateSQL] 校验失败: {str(e)}")
        return {"error": str(e)}