from elasticsearch import AsyncElasticsearch

from app.conf.app_config import EsConfig, appconfig


class ESClientManager:
    def __init__(self,config: EsConfig):
        self.client: AsyncElasticsearch | None = None
        self.config: EsConfig = config

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.client = AsyncElasticsearch(self._get_url())

    async def close(self):
        await self.client.close()
es_client_manager = ESClientManager(config=appconfig.es)