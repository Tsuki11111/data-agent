import asyncio

import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.llm import llm
from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.prompt.prompt_loader import load_prompt


async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "校正SQL语句", "status": "running"})
    try:
        error = state.get("error")
        sql = state.get("sql")
        table_infos = state["table_infos"]
        metric_infos = state["metric_infos"]
        date_info = state["date_info"]
        db_info = state["db_info"]
        query = state["query"]
        prompt = PromptTemplate(
            template=load_prompt("correct_sql"),
            input_variables=["query", "table_infos", "metric_infos", "date_info", "db_info", "error","sql"]
        )
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke(
            {
                "query": query,
                "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
                "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
                "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
                "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
                "error": error,
                "sql": sql
            }
        )
        logger.info(f"[CorrectSQL] 开始修正SQL, 错误信息: {error}")
        logger.info(f"[CorrectSQL] 修正后的SQL: {result}")
        writer({"type": "progress", "step": "校正SQL语句", "status": "success"})
        return {"sql": result}
    except Exception as e:
        logger.error(f"[CorrectSQL] 校正SQL语句失败: {e}")
        writer({"type": "progress", "step": "校正SQL语句", "status": "error"})
        writer({"type": "error", "message": str(e)})
        raise


