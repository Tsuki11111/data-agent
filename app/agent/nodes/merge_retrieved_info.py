from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoState, ColumnInfoState, MetricInfoState
from app.models.entity.column_info import ColumnInfo
from app.models.entity.metric_info import MetricInfo
from app.models.entity.value_info import ValueInfo
from app.core.log import logger


async def merge_retrieved_info(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "合并召回信息", "status": "running"})
    try:
        # 依赖注入
        retrieved_column_infos: list[ColumnInfo] = state["retrieved_column_infos"]
        retrieved_metric_infos: list[MetricInfo] = state["retrieved_metric_infos"]
        retrieved_value_infos: list[ValueInfo] = state["retrieved_value_infos"]
        meta_mysql_repository = runtime.context["meta_mysql_repository"]
        # 处理表信息
        # 将指标信息相关的字段信息添加到字段信息中
        # 字典化去重
        retrieved_column_info_map: dict[str, ColumnInfo] = {retrieved_column_info.id: retrieved_column_info for retrieved_column_info in retrieved_column_infos}
        for retrieved_metric_info in retrieved_metric_infos:
            for relevant_column in retrieved_metric_info.relevant_columns:
                if relevant_column not in retrieved_column_info_map:
                    column_info: ColumnInfo | None = await meta_mysql_repository.get_column_info_by_id(relevant_column)
                    if column_info is not None:
                        retrieved_column_info_map[relevant_column] = column_info

        # 将字段取值加入到所属字段的example中
        for retrieved_value_info in retrieved_value_infos:
            value = retrieved_value_info.value
            column_id = retrieved_value_info.column_id
            if column_id not in retrieved_column_info_map:
                column_info: ColumnInfo | None = await meta_mysql_repository.get_column_info_by_id(column_id)
                if column_info is not None:
                    retrieved_column_info_map[column_id] = column_info
            if column_id in retrieved_column_info_map and value not in retrieved_column_info_map[column_id].examples:
                retrieved_column_info_map[column_id].examples.append(value)

        # 按照表对字段信息进行分组，整理成目标格式
        table_to_columns_map: dict[str, list[ColumnInfo]] = {}
        for retrieved_column_info in retrieved_column_info_map.values():
            table_id = retrieved_column_info.table_id
            if table_id not in table_to_columns_map:
                table_to_columns_map[table_id] = []
            table_to_columns_map[table_id].append(retrieved_column_info)

        logger.info(f"[MergeRetrievedInfo] 字段按表分组: {len(table_to_columns_map)} 张表")

        # 强制为每个表添加主外键字段
        for table_id in table_to_columns_map.keys():
            key_columns: list[ColumnInfo] | None = await meta_mysql_repository.get_key_columns_by_table_id(table_id)
            if key_columns is None:
                continue
            column_ids = [column_info.id for column_info in table_to_columns_map[table_id]]
            for key_column in key_columns:
                if key_column.id not in column_ids:
                    table_to_columns_map[table_id].append(key_column)

        table_infos: list[TableInfoState] = []
        for table_id, column_infos in table_to_columns_map.items():
            table_info = await meta_mysql_repository.get_table_info_by_id(table_id)
            if table_info is None:
                logger.warning(f"[MergeRetrievedInfo] 表信息不存在: {table_id}")
                continue
            columns = [ColumnInfoState(
                name=column_info.name,
                type=column_info.type,
                role=column_info.role,
                description=column_info.description,
                examples=column_info.examples,
                alias=column_info.alias,
            ) for column_info in column_infos]
            table_info_state = TableInfoState(
                name=table_info.name,
                role=table_info.role,
                discription=table_info.description,
                columns=columns
            )
            table_infos.append(table_info_state)
        # 处理指标信息
        metric_infos: list[MetricInfoState] = [
            MetricInfoState(
                name=metric_info.name,
                description=metric_info.description,
                relevant_columns=metric_info.relevant_columns,
                alias=metric_info.alias,
            ) for metric_info in retrieved_metric_infos
        ]
        logger.info(f"[MergeRetrievedInfo] 合并完成: {len(table_infos)} 张表, {len(metric_infos)} 个指标")
        writer({"type": "progress", "step": "合并召回信息", "status": "success"})
        return {
            "table_infos": table_infos,
            "metric_infos": metric_infos,
        }
    except Exception as e:
        logger.error(f"[MergeRetrievedInfo] 合并召回信息失败: {e}")
        writer({"type": "progress", "step": "合并召回信息", "status": "error"})
        writer({"type": "error", "message": str(e)})
        raise
