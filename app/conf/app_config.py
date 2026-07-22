from dataclasses import dataclass
from pathlib import Path
from omegaconf import OmegaConf


@dataclass
class FileConfig:
    enable: bool
    level: str
    path: str
    rotation: str
    retention: str


@dataclass
class ConsoleConfig:
    enable: bool
    level: str


@dataclass
class LoggingConfig:
    file: FileConfig
    console: ConsoleConfig


@dataclass
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    database: str




@dataclass
class QdrantConfig:
    host: str
    port: int
    embedding_size: int


@dataclass
class EmbeddingConfig:
    api_key: str
    base_url: str
    model: str
    dimensions: int


@dataclass
class EsConfig:
    host: str
    port: int
    index_name: str


@dataclass
class LlmConfig:
    model_name: str
    api_key: str
    base_url: str


@dataclass
class AppConfig:
    logging: LoggingConfig
    db_meta: DbConfig
    db_dw: DbConfig
    qdrant: QdrantConfig
    embedding: EmbeddingConfig
    es: EsConfig
    llm: LlmConfig


config_file = Path(__file__).parents[2] / "conf" / "app_config.yaml"
appconfig: AppConfig = OmegaConf.to_object(OmegaConf.merge(OmegaConf.structured(AppConfig), OmegaConf.load(config_file)))
