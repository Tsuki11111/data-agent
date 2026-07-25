from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.models.entity.metric_info import MetricInfo
from app.prompt.prompt_loader import load_prompt


async def recall_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回指标信息", "status": "running"})
    try:
        keywords = state["keywords"]
        query = state["query"]
        embedding_client = runtime.context["embedding_client"]
        metric_qdrant_repository = runtime.context["metric_qdrant_repository"]

        prompt = PromptTemplate(
            template=load_prompt("extend_keywords_for_metric_recall"),
            input_variables=["query"]
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = chain.invoke({"query": query})
        keywords = list(set(keywords + result))
        logger.info(f"[RecallMetric] 关键词扩展完成: {keywords}")
        metric_info_map: dict[str, MetricInfo] = {}

        # 批量向量化所有关键词
        logger.info(f"[RecallMetric] 正在向量化 {len(keywords)} 个关键词...")
        vectors = await embedding_client.aembed_documents(keywords)
        logger.info(f"[RecallMetric] 向量化完成，开始向量检索...")

        for vector in vectors:
            current_metric_infos: list[MetricInfo] = await metric_qdrant_repository.search(vector, score_threshold=0.6,
                                                                                           limit=10)
            for metric_info in current_metric_infos:
                if metric_info.id not in metric_info_map:
                    metric_info_map[metric_info.id] = metric_info
        retrieved_metric_infos = list(metric_info_map.values())
        logger.info(f"[RecallMetric] 检索完成: {len(retrieved_metric_infos)} 个指标 (去重后)")
        writer({"type": "progress", "step": "召回指标信息", "status": "success"})
        return {"retrieved_metric_infos": retrieved_metric_infos}
    except Exception as e:
        logger.error(f"[RecallMetric] 召回指标信息失败: {e}")
        writer({"type": "progress", "step": "召回指标信息", "status": "error"})
        writer({"type": "error", "message": str(e)})
        raise