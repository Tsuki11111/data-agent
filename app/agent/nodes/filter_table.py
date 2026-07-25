import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, TableInfoState
from app.prompt.prompt_loader import load_prompt


async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "过滤表信息", "status": "running"})
    try:
        query = state["query"]
        table_infos: list[TableInfoState] = state["table_infos"]
        prompt = PromptTemplate(
            template=load_prompt("filter_table_info"),
            input_variables=["query", "table_infos"]
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke(
            {"query": query,
             "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False)}
        )
        filtered_table_infos = []
        for table_info in table_infos:
            if table_info["name"] in result:
                table_info["columns"] = [column_info for column_info in table_info["columns"] if column_info["name"] in result[table_info["name"]]]
                filtered_table_infos.append(table_info)
        logger.info(f"[FilterTable] 过滤后的表信息: {[filtered_table_info['name'] for filtered_table_info in filtered_table_infos]}")
        logger.info(f"[FilterTable] 输入 {len(table_infos)} 张表 → 输出 {len(filtered_table_infos)} 张表")
        writer({"type": "progress", "step": "过滤表信息", "status": "success"})
        return {"table_infos": filtered_table_infos}
    except Exception as e:
        logger.error(f"[FilterTable] 过滤表信息失败: {e}")
        writer({"type": "progress", "step": "过滤表信息", "status": "error"})
        writer({"type": "error", "message": str(e)})
        raise
