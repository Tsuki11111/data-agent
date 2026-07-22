import json
from typing import Optional
from urllib.parse import urljoin

import aiohttp
import requests

from app.conf.app_config import EmbeddingConfig, appconfig


class DashScopeEmbeddings:
    """轻量级 DashScope embedding 客户端，直接调用 OpenAI 兼容接口，不依赖 tiktoken"""

    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_url(self) -> str:
        return urljoin(self.base_url + "/", "embeddings")

    def _build_payload(self, texts: list[str]) -> dict:
        return {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimensions,
            "encoding_format": "float",
        }

    def embed_query(self, text: str) -> list[float]:
        """同步调用：单条文本向量化"""
        response = requests.post(
            self._build_url(),
            headers=self._headers,
            json=self._build_payload([text]),
        )
        response.raise_for_status()
        result = response.json()
        return result["data"][0]["embedding"]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """异步调用：批量文本向量化"""
        async with aiohttp.ClientSession() as session:
            payload = self._build_payload(texts)
            async with session.post(
                self._build_url(),
                headers=self._headers,
                json=payload,
            ) as response:
                if not response.ok:
                    body = await response.text()
                    raise RuntimeError(
                        f"Embedding API 错误: status={response.status}, "
                        f"body={body}"
                    )
                result = await response.json()
                # 返回结果按输入顺序排列
                embeddings = [item["embedding"] for item in result["data"]]
                return embeddings


class EmbeddingClientManager:
    def __init__(self, config: EmbeddingConfig):
        self.client: Optional[DashScopeEmbeddings] = None
        self.config = config

    def init(self):
        self.client = DashScopeEmbeddings(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model=self.config.model,
            dimensions=self.config.dimensions,
        )

    async def close(self):
        pass


embedding_client_manager = EmbeddingClientManager(appconfig.embedding)
if __name__ == '__main__':
    embedding_client_manager.init()
    client = embedding_client_manager.client
    text = "Attention is all you need"
    print(client.embed_query(text))
