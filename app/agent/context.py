from typing import TypedDict

from app.clients.embedding_client_manager import DashScopeEmbeddings
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class DataAgentContext(TypedDict):
    column_qdrant_repository: ColumnQdrantRepository
    metric_qdrant_repository: MetricQdrantRepository
    embedding_client: DashScopeEmbeddings
    value_es_repository: ValueEsRepository
    meta_mysql_repository: MetaMysqlRepository
    dw_mysql_repository: DwMysqlRepository