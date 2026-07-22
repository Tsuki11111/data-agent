import asyncio
from dataclasses import asdict
from pathlib import Path

from app.clients.embedding_client_manager import DashScopeEmbeddings
from omegaconf import OmegaConf

from app.clients.mysql_client_manager import dw_mysql_client_manager, meta_mysql_client_manager
from app.conf.meta_config import MetaConfig
from app.core.log import logger
from app.models.entity.column_info import ColumnInfo
from app.models.entity.column_metric import ColumnMetric
from app.models.entity.metric_info import MetricInfo
from app.models.entity.table_info import TableInfo
from app.models.entity.value_info import ValueInfo
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class MetaKnowledgeService:
    def __init__(self, meta_mysql_repository: MetaMysqlRepository,
                 dw_mysql_repository: DwMysqlRepository,
                 column_qdrant_repository: ColumnQdrantRepository,
                 embedding_client: DashScopeEmbeddings,
                 value_es_repository: ValueEsRepository,
                 metric_qdrant_repository: MetricQdrantRepository):
        self.meta_mysql_repository: MetaMysqlRepository = meta_mysql_repository
        self.dw_mysql_repository: DwMysqlRepository = dw_mysql_repository
        self.column_qdrant_repository: ColumnQdrantRepository = column_qdrant_repository
        self.embedding_client: DashScopeEmbeddings = embedding_client
        self.value_es_repository: ValueEsRepository = value_es_repository
        self.metric_qdrant_repository: MetricQdrantRepository = metric_qdrant_repository
    async def _save_tables_to_meta_db(self,meta_config: MetaConfig)-> list[ColumnInfo]:
        table_infos: list[TableInfo] = []
        column_infos: list[ColumnInfo] = []
        # 将表信息和字段信息保存到meta数据库中
        for table in meta_config.tables:
            logger.info(f"[Build] 处理表: {table.name}")
            table_info = TableInfo(
                id=table.name,
                name=table.name,
                role=table.role,
                description=table.description
            )
            # print(table_info.id)
            table_infos.append(table_info)
            column_types = await self.dw_mysql_repository.get_column_types(table.name)
            logger.info(f"[Build]   {table.name} 的字段类型: {column_types}")
            for column in table.columns:
                examples = await self.dw_mysql_repository.get_column_values(table.name, column.name)
                column_info = ColumnInfo(
                    id=f"{table.name}.{column.name}",
                    name=column.name,
                    type=column_types[column.name],
                    role=column.role,
                    description=column.description,
                    alias=column.alias,
                    table_id=table.name,
                    examples=examples
                )
                column_infos.append(column_info)
                logger.info(f"[Build]   -> 字段: {column_info.id}, 类型: {column_info.type}, 别名: {column_info.alias}")
        logger.info(f"[Build] 表信息和字段信息收集完成: {len(table_infos)} 个表, {len(column_infos)} 个字段")
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.clear_all()
            self.meta_mysql_repository.save_table_infos(table_infos)
            self.meta_mysql_repository.save_column_infos(column_infos)
        logger.info("[Build] MySQL 表/字段信息保存完成")
        return column_infos


    async def _save_columns_to_qdrant(self,column_infos: list[ColumnInfo]):
        logger.info("[Build] 准备创建 column Qdrant collection...")
        await self.column_qdrant_repository.ensure_collection()
        logger.info("[Build] Qdrant collection 就绪，准备构造向量点...")
        points: list[dict] = []

        for column_info in column_infos:
            import uuid
            points.append({
                'id': uuid.uuid4(),
                'embedding_text': column_info.name,
                'payload': asdict(column_info)
            })
            points.append({
                'id': uuid.uuid4(),
                'embedding_text': column_info.description,
                'payload': asdict(column_info)
            })
            for alia in column_info.alias:
                points.append({
                    'id': uuid.uuid4(),
                    'embedding_text': alia,
                    'payload': asdict(column_info)
                })
        logger.info(f"[Embedding] 共生成 {len(points)} 条待向量化的文本")
        # 批量向量化
        embeddings: list[list[float]] = []
        embedding_texts = [point['embedding_text'] for point in points]
        enbedding_batch_size = 10
        total_batches = (len(embedding_texts) + enbedding_batch_size - 1) // enbedding_batch_size
        logger.info(
            f"[Embedding] 开始调用 DashScope text-embedding-v3，batch_size={enbedding_batch_size}，共 {total_batches} 批")
        for i in range(0, len(embedding_texts), enbedding_batch_size):
            batch_num = i // enbedding_batch_size + 1
            batch_embedding_batch = embedding_texts[i:i + enbedding_batch_size]
            logger.info(f"[Embedding]   batch {batch_num}/{total_batches}, 共 {len(batch_embedding_batch)} 条")
            try:
                batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_batch)
                embeddings.extend(batch_embeddings)
                logger.info(
                    f"[Embedding]   batch {batch_num} 向量化完成，向量维度={len(batch_embeddings[0]) if batch_embeddings else 'N/A'}")
            except Exception as e:
                logger.error(f"[Embedding]   batch {batch_num} 向量化失败: {e}")
                raise
        logger.info(f"[Embedding] 全部向量化完成，共 {len(embeddings)} 条向量")
        ids = [point['id'] for point in points]
        payloads = [point['payload'] for point in points]

        logger.info(f"[Qdrant] 准备写入 {len(ids)} 条数据到 Qdrant...")
        await self.column_qdrant_repository.upsert(ids, embeddings, payloads)
        logger.info("[Qdrant] 向量数据写入完成")

    async def _save_value_to_es(self, meta_config: MetaConfig):
        logger.info("[ES] 开始处理全文索引...")
        await self.value_es_repository.ensure_index()
        value_infos: list[ValueInfo] = []
        for table in meta_config.tables:
            for column in table.columns:
                if column.sync:
                    current_column_values = await self.dw_mysql_repository.get_column_values(table.name,
                                                                                             column.name, 10000)
                    current_value_infos = [ValueInfo(id=f"{table.name}.{column.name}.{current_column_value}",
                                                     value=current_column_value,
                                                     column_id=f"{table.name}.{column.name}")
                                           for current_column_value in current_column_values]
                    value_infos.extend(current_value_infos)
        logger.info(f"[ES] 共 {len(value_infos)} 条值索引数据，开始写入 ES")
        await self.value_es_repository.index(value_infos)
        logger.info("[ES] ES 索引写入完成")
    async def _save_metrics_to_meta_db(self,meta_config: MetaConfig)-> list[MetricInfo]:
        metric_infos: list[MetricInfo] = []
        column_metrics: list[ColumnMetric] = []
        for metric in meta_config.metrics:
            metric_info = MetricInfo(
                id=metric.name,
                name=metric.name,
                description=metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias
            )
            metric_infos.append(metric_info)
            for column in metric.relevant_columns:
                column_metric = ColumnMetric(
                    column_id=column,
                    metric_id=metric.name
                )
                column_metrics.append(column_metric)
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.sav_metric_infos(metric_infos)
            await self.meta_mysql_repository.save_column_metrics(column_metrics)
            logger.info("[Build] MySQL 指标信息保存完成")
        return metric_infos
    async def _save_metrics_to_qdrant(self,metric_infos: list[MetricInfo]):
        logger.info("[Build] 准备创建 metric Qdrant collection...")
        await self.metric_qdrant_repository.ensure_collection()

        logger.info("[Build] Qdrant collection 就绪，准备构造向量点...")
        points: list[dict] = []

        for metric_info in metric_infos:
            import uuid
            points.append({
                'id': uuid.uuid4(),
                'embedding_text': metric_info.name,
                'payload': asdict(metric_info)
            })
            points.append({
                'id': uuid.uuid4(),
                'embedding_text': metric_info.description,
                'payload': asdict(metric_info)
            })
            for alia in metric_info.alias:
                points.append({
                    'id': uuid.uuid4(),
                    'embedding_text': alia,
                    'payload': asdict(metric_info)
                })
        logger.info(f"[Embedding] 共生成 {len(points)} 条待向量化的文本")
        # 批量向量化
        embeddings: list[list[float]] = []
        embedding_texts = [point['embedding_text'] for point in points]
        enbedding_batch_size = 10
        total_batches = (len(embedding_texts) + enbedding_batch_size - 1) // enbedding_batch_size
        logger.info(
            f"[Embedding] 开始调用 DashScope text-embedding-v3，batch_size={enbedding_batch_size}，共 {total_batches} 批")
        for i in range(0, len(embedding_texts), enbedding_batch_size):
            batch_num = i // enbedding_batch_size + 1
            batch_embedding_batch = embedding_texts[i:i + enbedding_batch_size]
            logger.info(f"[Embedding]   batch {batch_num}/{total_batches}, 共 {len(batch_embedding_batch)} 条")
            try:
                batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_batch)
                embeddings.extend(batch_embeddings)
                logger.info(
                    f"[Embedding]   batch {batch_num} 向量化完成，向量维度={len(batch_embeddings[0]) if batch_embeddings else 'N/A'}")
            except Exception as e:
                logger.error(f"[Embedding]   batch {batch_num} 向量化失败: {e}")
                raise
        logger.info(f"[Embedding] 全部向量化完成，共 {len(embeddings)} 条向量")
        ids = [point['id'] for point in points]
        payloads = [point['payload'] for point in points]

        logger.info(f"[Qdrant] 准备写入 {len(ids)} 条数据到 Qdrant...")
        await self.metric_qdrant_repository.upsert(ids, embeddings, payloads)
        logger.info("[Qdrant] 向量数据写入完成")

    async def build(self, config_path: Path):
        logger.info("[Build] 开始执行 build...")
        content = OmegaConf.load(config_path)
        schema = OmegaConf.structured(MetaConfig)
        meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, content))
        logger.info(f"[Build] meta_config 加载完成: tables={len(meta_config.tables) if meta_config.tables else 0}, metrics={len(meta_config.metrics) if meta_config.metrics else 0}")
        if meta_config.tables:
            logger.info(f"[Build] 开始处理 {len(meta_config.tables)} 个表")
            """
            发现问题: 过度耦合
            这里的数据类用的是继承自SqlAlchemy.DeclarativeBase的数据类，如果后面技术框架更换，会导致错误
            因此，需要对数据实体类建立类似于dto的类对象，这里将采用新建立的对象，以解除耦合
            当然，由于MetaMysqlRepository里的两个save方法里面的session.add_all()里的参数必须是
            继承自SqlAlchemy.DeclarativeBase的数据类，所以还要在方法里面做一步类型的转换
            """
            column_infos = await self._save_tables_to_meta_db(meta_config)

            # 对字段信息建立向量索引,对table_info和metric_info进行语义召回
            await self._save_columns_to_qdrant(column_infos)

            # 对指定的维度字段建立全文索引,对字段取值进行检索和匹配
            await self._save_value_to_es(meta_config)

        if meta_config.metrics:
            # 将指标信息保存到meta数据库中
            metric_infos = await self._save_metrics_to_meta_db(meta_config)
            # 对指标信息建立向量索引
            await self._save_metrics_to_qdrant(metric_infos)


if __name__ == '__main__':
    # 测试1: 查看表信息和字段信息是否获取成功(其实就是build_meta_knowledge的提前测试)
    async def test1():
        dw_mysql_client_manager.init()
        meta_mysql_client_manager.init()
        async with (
            dw_mysql_client_manager.session_factory() as dw_session,
            meta_mysql_client_manager.session_factory() as meta_session
        ):
            dw_repo = DwMysqlRepository(dw_session)
            meta_repo = MetaMysqlRepository(meta_session)
            # 这个测试只验证 MySQL 读写，不涉及 Qdrant/Embedding/ES
            # 所以传入 None 的占位
            from app.clients.qdrant_client_manager import qdrant_client_manager
            from app.clients.embedding_client_manager import embedding_client_manager
            from app.clients.es_client_manager import es_client_manager
            qdrant_client_manager.init()
            embedding_client_manager.init()
            es_client_manager.init()
            from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
            from app.repositories.es.value_es_repository import ValueEsRepository
            column_qdrant_repo = ColumnQdrantRepository(qdrant_client_manager.client)
            value_es_repo = ValueEsRepository(es_client_manager.client)
            service = MetaKnowledgeService(meta_repo, dw_repo, column_qdrant_repo, embedding_client_manager.client, value_es_repo)
            await service.build(Path('D:\\PycharmProjects\\data-agent\\conf\\meta_config.yaml'))
            await meta_mysql_client_manager.close()
            await dw_mysql_client_manager.close()


    asyncio.run(test1())
