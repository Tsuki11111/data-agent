import asyncio
from pathlib import Path

from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.clients.embedding_client_manager import embedding_client_manager
from app.core.log import logger
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.services.meta_knowledge_service import MetaKnowledgeService


async def build(config_path: Path):
    logger.info("=" * 50)
    logger.info("开始构建知识库...")
    logger.info("=" * 50)
    logger.info(f"[配置] 加载配置: {config_path}")
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    logger.info("[MySQL] meta 连接已初始化")
    logger.info("[MySQL] dw 连接已初始化")
    qdrant_client_manager.init()
    logger.info(f"[Qdrant] 连接已初始化: {qdrant_client_manager._get_url()}")
    embedding_client_manager.init()
    logger.info(f"[Embedding] 客户端已初始化: model={embedding_client_manager.config.model}")
    es_client_manager.init()
    logger.info("[ES] 连接已初始化")
    async with (meta_mysql_client_manager.session_factory() as meta_session,
                dw_mysql_client_manager.session_factory() as dw_session):
        logger.info("[MySQL] 数据库会话已创建")
        meta_mysql_repository = MetaMysqlRepository(meta_session)
        dw_mysql_repository = DwMysqlRepository(dw_session)
        column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
        value_es_repository = ValueEsRepository(es_client_manager.client)
        metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.client)
        meta_knowledge_service = MetaKnowledgeService(meta_mysql_repository, dw_mysql_repository, column_qdrant_repository, embedding_client_manager.client, value_es_repository, metric_qdrant_repository)
        logger.info("[Service] MetaKnowledgeService 已初始化，开始执行 build...")

        await meta_knowledge_service.build(config_path)

        logger.info("[完成] 知识库构建完成！")
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
    await qdrant_client_manager.close()
    await es_client_manager.close()
    logger.info("[清理] 所有连接已关闭")

if __name__ == '__main__':
    asyncio.run(build(config_path=Path(__file__).parents[2] / "conf" / "meta_config.yaml"))