import asyncio

from langgraph.runtime import Runtime
from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState


async def run_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "执行SQL语句", "status": "running"})
    try:
        sql = state.get("sql")
        dw_mysql_repository = runtime.context["dw_mysql_repository"]
        logger.info(f"[RunSQL] 执行SQL: {sql}")
        result = await dw_mysql_repository.run(sql)
        logger.info(f"[RunSQL] SQL执行结果: {result}")
        writer({"type": "progress", "step": "执行SQL语句", "status": "success"})
        writer({"type": "result", "data": {"sql": sql, "data": result}})
        return {"result": result}
    except Exception as e:
        logger.error(f"[RunSQL] 执行SQL语句失败: {e}")
        writer({"type": "progress", "step": "执行SQL语句", "status": "error"})
        writer({"type": "error", "message": str(e)})
        raise


