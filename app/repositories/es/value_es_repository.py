from dataclasses import asdict

from elasticsearch import AsyncElasticsearch

from app.models.entity.value_info import ValueInfo


class ValueEsRepository:
    index_name = "value_index"

    def __init__(self, client: AsyncElasticsearch):
        self.index_mappings = {
            "properties": {
                "id": {"type": "keyword"},
                "value": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_max_word"},
                "column_id": {"type": "keyword"},
            }
        }
        self.es_client = client

    async def ensure_index(self):
        if not await self.es_client.indices.exists(index=self.index_name):
            await self.es_client.indices.create(
                index=self.index_name,
                mappings=self.index_mappings,
                                                )

    async def index(self, value_infos,batch_size=20):
        # 批处理
        for i in range(0, len(value_infos), batch_size):
            batch_value_infos = value_infos[i:i + batch_size]
            batch_operations = []
            for value_info in batch_value_infos:
                operation = {
                    "index": {
                        "_index": self.index_name,
                        "_id": value_info.id,
                    }
                }
                batch_operations.append(operation)
                batch_operations.append(asdict(value_info))
            await self.es_client.bulk(body=batch_operations)

    async def search(self, keyword: str, score_threshold: float= 0.6, limit: int = 20):
        resp = await self.es_client.search(
            index=self.index_name,
            query={
                "match": {
                    "value": keyword,
                }
            },
            size=limit,
            min_score=score_threshold,
        )
        return [ValueInfo(**hit['_source']) for hit in resp['hits']['hits']]
