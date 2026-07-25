from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.models.entity.column_info import ColumnInfo
from app.prompt.prompt_loader import load_prompt
from app.core.log import logger


async def recall_column(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回字段信息", "status": "running"})
    try:
        query = state["query"]
        keywords = state["keywords"]
        column_qdrant_repository = runtime.context["column_qdrant_repository"]
        embedding_client = runtime.context["embedding_client"]
        # 用llm扩展关键词，提高召回效果

        prompt = PromptTemplate(
            template=load_prompt("extend_keywords_for_column_recall"),
            input_variables=["query"]
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = chain.invoke({"query": query})
        keywords = list(set(keywords + result))
        logger.info(f"[RecallColumn] 关键词: {keywords}")

        # 从Qdrant中检索字段信息
        column_info_map: dict[str, ColumnInfo] = {}
        # 批量向量化所有关键词
        logger.info(f"[RecallColumn] 正在向量化 {len(keywords)} 个关键词...")
        vectors = await embedding_client.aembed_documents(keywords)
        logger.info(f"[RecallColumn] 向量化完成，开始向量检索...")

        for vector in vectors:
            current_column_infos: list[ColumnInfo] = await column_qdrant_repository.search(vector, score_threshold=0.6, limit=10)
            for column_info in current_column_infos:
                if column_info.id not in column_info_map:
                    column_info_map[column_info.id] = column_info
        retrieved_column_infos = list(column_info_map.values())
        logger.info(f"[RecallColumn] 检索完成: {len(retrieved_column_infos)} 个字段 (去重后)")
        writer({"type": "progress", "step": "召回字段信息", "status": "success"})
        return {"retrieved_column_infos": retrieved_column_infos}
    except Exception as e:
        logger.error(f"[RecallColumn] 召回字段信息失败: {e}")
        writer({"type": "progress", "step": "召回字段信息", "status": "error"})
        writer({"type": "error", "message": str(e)})
        raise



