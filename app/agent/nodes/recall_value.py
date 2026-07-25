from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.models.entity.value_info import ValueInfo
from app.prompt.prompt_loader import load_prompt


async def recall_value(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回字段取值", "status": "running"})
    try:
        keywords = state["keywords"]
        query = state["query"]
        value_es_repository = runtime.context["value_es_repository"]

        prompt = PromptTemplate(
            template=load_prompt("extend_keywords_for_value_recall"),
            input_variables=["query"]
        )

        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = chain.invoke({"query": query})
        keywords = list(set(keywords + result))
        logger.info(f"[RecallValue] 关键词扩展完成: {keywords}")
        value_infos_map: dict[str, ValueInfo] = {}
        for keyword in keywords:
            current_value_infos: list[ValueInfo] = await value_es_repository.search(keyword)
            for current_value_info in current_value_infos:
                if current_value_info.id not in value_infos_map:
                    value_infos_map[current_value_info.id] = current_value_info
        retrieved_value_infos = list(value_infos_map.values())
        logger.info(f"[RecallValue] 检索完成: {len(retrieved_value_infos)} 个字段取值 (去重后)")
        writer({"type": "progress", "step": "召回字段取值", "status": "success"})
        return {"retrieved_value_infos": retrieved_value_infos}
    except Exception as e:
        logger.error(f"[RecallValue] 召回字段取值失败: {e}")
        writer({"type": "progress", "step": "召回字段取值", "status": "error"})
        writer({"type": "error", "message": str(e)})
        raise
