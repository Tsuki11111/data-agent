import json

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.clients.embedding_client_manager import DashScopeEmbeddings
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class QueryService:
    def __init__(self, mata_mysql_repository: MetaMysqlRepository,
                 column_qdrant_repository: ColumnQdrantRepository,
                 metric_qdrant_repository: MetricQdrantRepository,
                 value_es_repository: ValueEsRepository,
                 dw_mysql_repository: DwMysqlRepository,
                 embedding_client: DashScopeEmbeddings):
        self.mata_mysql_repository = mata_mysql_repository
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.embedding_client = embedding_client
    async def query(self,query: str):

        state = DataAgentState(query=query)
        context = DataAgentContext(column_qdrant_repository=self.column_qdrant_repository,
                                   embedding_client=self.embedding_client,
                                   metric_qdrant_repository=self.metric_qdrant_repository,
                                   value_es_repository=self.value_es_repository,
                                   meta_mysql_repository=self.mata_mysql_repository,
                                   dw_mysql_repository=self.dw_mysql_repository)
        try:
            async for chunk in graph.astream(input=state, context=context, stream_mode='custom'):
                yield f"data: {json.dumps(chunk, ensure_ascii=False,default=str)}\n\n" # SSE协议格式
        except Exception as e:
            error = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error, ensure_ascii=False,default=str)}\n\n" # SSE协议格式
            raise e
