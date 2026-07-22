from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance,PointStruct

from app.conf.app_config import appconfig
from app.core.log import logger
from app.models.entity.column_info import ColumnInfo


class ColumnQdrantRepository:
    def __init__(self, client: AsyncQdrantClient):
        self.collection_name = "column_info_collection"
        self.client = client

    async def ensure_collection(self):
        exists = await self.client.collection_exists(self.collection_name)
        logger.info(f"[Qdrant] 检查 collection '{self.collection_name}' 是否存在: {exists}")
        if not exists:
            logger.info(f"[Qdrant] collection '{self.collection_name}' 不存在，正在创建...")
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=appconfig.qdrant.embedding_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"[Qdrant] collection '{self.collection_name}' 创建成功")
        else:
            logger.info(f"[Qdrant] collection '{self.collection_name}' 已存在，跳过创建")

    async def upsert(self, ids: list[str], embeddings: list[list[float]], payloads: list[dict], batch_size: int = 10):
        points: list[PointStruct] = [PointStruct(id=id, vector=embedding, payload=payload) for id, embedding, payload in zip(ids, embeddings, payloads)]
        logger.info(f"[Qdrant] 开始写入 {len(points)} 条向量数据，batch_size={batch_size}")
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            logger.info(f"[Qdrant] 写入第 {i // batch_size + 1} 批，共 {len(batch)} 条")
            await self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
        logger.info(f"[Qdrant] 向量数据写入完成")

    async def search(self, vectors, score_threshold, limit) -> list[ColumnInfo]:
        searcch_result = await self.client.query_points(
            collection_name=self.collection_name,
            query=vectors,
            with_vectors=True,
            limit=limit,
            score_threshold=score_threshold,
        )
        return [ColumnInfo(**point.payload) for point in searcch_result.points]

