# Data-Agent 项目架构手册

## 一、整体架构

**Text2SQL 数据智能体** — 用户用自然语言（中文）提问，系统通过多轮 LangGraph Agent 流程自动理解问题、召回相关元数据、生成 SQL、校验并执行，返回查询结果。

### 技术栈
| 组件 | 选型 | 用途 |
|------|------|------|
| 运行时 | Python 3.13+, FastAPI + Uvicorn | Web 服务 |
| ORM | SQLAlchemy 2.0 async + asyncmy | MySQL 异步 ORM |
| LLM 编排 | LangGraph (StateGraph) + LangChain | Agent 工作流 |
| LLM | 通义千问 qwen-plus (DashScope) | 关键词扩展、SQL 生成 |
| Embedding | DashScope text-embedding-v3, 1024 维 | 向量化 |
| 向量数据库 | Qdrant v1.16, COSINE 距离, 1024 维 | 语义召回 |
| 搜索引擎 | Elasticsearch 8.19.10 + IK 分词 | 全文检索 |
| 关系数据库 | MySQL 8.0 utf8mb4, 两个库: meta + dw | 元数据 + 数据仓库 |
| 配置 | OmegaConf (YAML + dataclass 结构化) | 配置管理 |
| 日志 | Loguru | 日志 |
| 中文分词 | jieba | 关键词提取 |
| 包管理 | uv | 依赖管理 |

### 分层架构

```
FastAPI (main.py)
  └── Router (query_router.py)
        └── Service (QueryService / MetaKnowledgeService)
              ├── Agent (LangGraph, 12 Nodes)
              ├── Repository (MetaMysqlRepo / DwMysqlRepo / ColumnQdrantRepo / MetricQdrantRepo / ValueEsRepo)
              └── Client (MySQLClientManager / QdrantClientManager / ESClientManager / EmbeddingClientManager)
```

## 二、项目目录结构

```
D:\PycharmProjects\data-agent/
├── main.py                          # FastAPI 入口
├── pyproject.toml                   # 依赖
├── conf/
│   ├── app_config.yaml              # 运行配置（DB, Qdrant, ES, LLM, Embedding, Logging）
│   └── meta_config.yaml             # 元数据定义（表、字段、指标、别名）
├── docker/
│   ├── docker-compose.yaml          # MySQL + ES + Kibana + Qdrant
│   ├── mysql/
│   │   ├── meta.sql                 # meta 库初始化（4 张元数据表）
│   │   └── dw.sql                   # dw 库初始化（星型模型 + 测试数据）
│   └── elasticsearch/
│       ├── Dockerfile               # 安装 IK 分词插件
│       └── plugins/
├── prompts/                         # 7 个 .prompt 文件
├── static/
│   └── index.html                   # 前端聊天界面（Tailwind CSS）
├── logs/
│   └── app.log                      # 运行时日志
└── app/
    ├── conf/
    │   ├── app_config.py            # OmegaConf 加载运行配置
    │   └── meta_config.py           # OmegaConf 加载元数据配置
    ├── core/
    │   └── log.py                   # Loguru 初始化
    ├── clients/
    │   ├── mysql_client_manager.py  # async engine + session_factory
    │   ├── qdrant_client_manager.py # AsyncQdrantClient 单例
    │   ├── es_client_manager.py     # AsyncElasticsearch 单例
    │   └── embedding_client_manager.py  # DashScopeEmbeddings 客户端
    ├── models/
    │   ├── base.py                  # SQLAlchemy DeclarativeBase
    │   ├── table_info_mysql.py      # ORM: table_info 表
    │   ├── column_info_mysql.py     # ORM: column_info 表
    │   ├── metric_info_mysql.py     # ORM: metric_info 表
    │   ├── column_metric_mysql.py   # ORM: column_metric 表
    │   └── entity/                  # 纯 dataclass DTO
    │       ├── table_info.py
    │       ├── column_info.py
    │       ├── metric_info.py
    │       ├── value_info.py
    │       └── column_metric.py
    ├── repositories/
    │   ├── mysql/
    │   │   ├── meta/
    │   │   │   ├── meta_mysql_repository.py
    │   │   │   └── mappers/         # ORM ↔ Entity 转换
    │   │   │       ├── table_info_mapper.py
    │   │   │       ├── column_info_mapper.py
    │   │   │       ├── metric_info_mapper.py
    │   │   │       └── column_metric_mapper.py
    │   │   └── dw/
    │   │       └── dw_mysql_repository.py
    │   ├── qdrant/
    │   │   ├── column_qdrant_repository.py
    │   │   └── metric_qdrant_repository.py
    │   └── es/
    │       └── value_es_repository.py
    ├── services/
    │   ├── query_service.py         # Agent 编排 + SSE 流式输出
    │   └── meta_knowledge_service.py # 知识库构建 ETL
    ├── agent/
    │   ├── state.py                 # DataAgentState TypedDict
    │   ├── context.py               # DataAgentContext TypedDict
    │   ├── graph.py                 # LangGraph StateGraph 定义
    │   ├── llm/__init__.py          # LLM 初始化（qwen-plus）
    │   └── nodes/                   # 12 个 Agent Node
    │       ├── extract_keywords.py
    │       ├── recall_column.py
    │       ├── recall_metric.py
    │       ├── recall_value.py
    │       ├── merge_retrieved_info.py
    │       ├── filter_table.py
    │       ├── filter_metric.py
    │       ├── add_extra_context.py
    │       ├── generate_sql.py
    │       ├── validate_sql.py
    │       ├── correct_sql.py
    │       └── run_sql.py
    ├── api/
    │   ├── lifespan.py              # 5 个 Client 的 init/close
    │   ├── dependencies.py          # FastAPI Depends 注入链
    │   ├── schemas/query_schema.py  # Pydantic 请求模型
    │   └── router/query_router.py   # POST /api/query (SSE)
    └── scripts/
        └── build_meta_knowledge.py  # 知识库构建入口
```

## 三、数据库搭建

### 3.1 Docker Compose（docker-compose.yaml）

| 服务 | 镜像 | 端口 | 数据卷 | 备注 |
|------|------|------|--------|------|
| mysql | mysql:8.0 | 3306 | mysql_data | 用户 tsuk1, 密码 chenhu123, utf8mb4 |
| elasticsearch | 自定义 Dockerfile(8.19.10 + IK) | 9200 | es_data | 单节点, 禁用安全认证 |
| kibana | kibana:8.19.10 | 5601 | - | 关联 ES |
| qdrant | qdrant/qdrant:v1.16 | 6333/6334 | qdrant_data | HTTP + gRPC |

启动：`docker compose -f docker/docker-compose.yaml up -d`

### 3.2 meta 库（数据库：meta）

存储元数据知识，共 4 张表：

```sql
table_info     -- 表元数据: id(PK), name, role(fact/dim), description
column_info    -- 字段元数据: id(PK), name, type, role(pk/fk/measure/dimension),
                              examples(JSON), description, alias(JSON), table_id
metric_info    -- 指标定义: id(PK), name, description, relevant_columns(JSON), alias(JSON)
column_metric  -- 字段-指标关联: column_id(PK), metric_id(PK)
```

### 3.3 dw 库（数据库：dw）

数据仓库，星型模型，5 张表含测试数据：

- **维度表**: `dim_region`(地区), `dim_customer`(客户), `dim_product`(商品), `dim_date`(时间)
- **事实表**: `fact_order`(订单) — order_quantity(销量), order_amount(销售额)

### 3.4 元数据配置（conf/meta_config.yaml）

人工维护的字段级别业务元数据：

```yaml
tables:
  - name: dim_region
    role: dim
    description: 地区维度表
    columns:
      - name: province
        role: dimension
        alias: [省份, 省]
        sync: true     # 是否同步取值到 ES
```

字段角色类型：`primary_key`, `foreign_key`, `dimension`, `measure`
指标例如：GMV（成交总额）、AOV（平均订单金额）

## 四、配置系统

### OmegaConf 双层配置加载

```python
# app/conf/app_config.py
from omegaconf import OmegaConf
from dataclasses import dataclass

# 1. 定义带类型和默认值的 dataclass
# 2. 用 OmegaConf.structured() 创建 schema
# 3. 加载 YAML 文件
# 4. merge 合并（YAML 覆盖 dataclass 默认值）
# 5. to_object() 转回 dataclass 实例

appconfig: AppConfig = OmegaConf.to_object(
    OmegaConf.merge(OmegaConf.structured(AppConfig), OmegaConf.load(config_file))
)
```

### app_config.yaml 完整配置项

| 配置节 | 关键字段 | 说明 |
|--------|---------|------|
| `logging.file` | enable, level, path, rotation, retention | 文件日志 |
| `logging.console` | enable, level | 控制台日志 |
| `db_meta` | host, port, user, password, database | meta 库连接 |
| `db_dw` | host, port, user, password, database | dw 库连接 |
| `qdrant` | host, port, embedding_size | 向量数据库 |
| `embedding` | api_key, base_url, model, dimensions | Embedding 模型 |
| `es` | host, port, index_name | 搜索引擎 |
| `llm` | model_name, api_key, base_url | LLM 配置 |

### 环境变量
- `DASHSCOPE_API_KEY` — 通义千问 API 密钥，被 LLM 和 Embedding 共享
- YAML 中通过 `${oc.env:DASHSCOPE_API_KEY}` 引用

## 五、日志系统（Loguru）

```python
# app/core/log.py
logger.remove()  # 移除默认 handler

# 文件日志
logger.add(sink="logs/app.log", rotation="10 MB", retention="7 days",
           level="INFO", encoding="utf-8")

# 控制台日志（强制 stdout UTF-8）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
logger.add(sink=sys.stdout, level="INFO")
```

- 日志路径：`logs/app.log`
- 轮转：10 MB
- 保留：7 天
- 编码：UTF-8（中文支持）
- 日志分类标识：`[Build]`, `[MySQL]`, `[Qdrant]`, `[Embedding]`, `[ES]`, `[ExtractKeywords]`, `[RecallColumn]` 等

## 六、向量数据库（Qdrant）

### 连接配置
- Host: `localhost:6333`, HTTP 协议
- Embedding 维度: 1024, 距离算法: COSINE

### 两个 Collection

| Collection | Payload 类型 | 用途 |
|-----------|-------------|------|
| `column_info_collection` | ColumnInfo dataclass | 字段语义召回 |
| `metric_info_collection` | MetricInfo dataclass | 指标语义召回 |

### 知识库构建流程（build_meta_knowledge.py → MetaKnowledgeService）

1. 加载 `meta_config.yaml`
2. **从 dw 库实时抓取**字段类型和示例值
3. 写入 meta 库 MySQL
4. **向量化**：对每个字段/指标的 name、description、每个 alias 分别生成向量点（UUID 作为点 ID）
5. 批量写入 Qdrant（batch_size=10）
6. 对 `sync: true` 的维度字段，将其取值写入 ES

### 召回模式
- LLM 扩展关键词 → 批量向量化所有关键词 → 对每个向量去 Qdrant search（score_threshold=0.6, limit=10）→ 按 id 去重合并

## 七、搜索引擎（Elasticsearch）

### 索引配置
- 索引名: `value_index`
- mappings: `id`(keyword), `value`(text, ik_max_word 分词), `column_id`(keyword)
- 搜索: match 查询, min_score=0.6, limit=20
- IK 分词插件: 通过 Dockerfile 安装 `elasticsearch-analysis-ik-8.19.0.zip`

### 同步规则
- 仅 `meta_config.yaml` 中 `sync: true` 的维度字段会同步到 ES
- 从 dw 库抓取去重值（limit 10000）, 构建 `ValueInfo(id=f"{table}.{column}.{value}", value, column_id)` 批量写入

## 八、客户端管理器（Client Manager 单例模式）

每个外部服务对应一个 `*ClientManager` 类，遵循统一的 init/close 生命周期：

| Client Manager | 创建连接 | 关闭 | 单例变量 |
|---------------|---------|------|---------|
| `MySQLClientManager` | `create_async_engine()` | `engine.dispose()` | `meta_mysql_client_manager`, `dw_mysql_client_manager` |
| `QdrantClientManager` | `AsyncQdrantClient(url)` | `client.close()` | `qdrant_client_manager` |
| `ESClientManager` | `AsyncElasticsearch(url)` | `client.close()` | `es_client_manager` |
| `EmbeddingClientManager` | `DashScopeEmbeddings(...)` | pass | `embedding_client_manager` |

所有 Client 通过 FastAPI lifespan 统一初始化和关闭：

```python
# app/api/lifespan.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()
    dw_mysql_client_manager.init()
    meta_mysql_client_manager.init()
    yield
    # 关闭所有连接
```

## 九、数据模型设计（双层解耦模式）

采用 **ORM 模型 ↔ 纯 Entity** 双层设计，通过 Mapper 转换，解除对 SQLAlchemy 的耦合：

```
MySQL 表 ←→ SQLAlchemy ORM Model ←→ Mapper ←→ dataclass Entity ←→ 业务代码
```

- **ORM 模型**：`app/models/*_mysql.py`，继承 `Base(DeclarativeBase)`，带 SQLAlchemy 注解
- **Entity 实体**：`app/models/entity/*.py`，纯 `@dataclass`，无框架依赖
- **Mapper**：`app/repositories/mysql/meta/mappers/*.py`，每个有 `to_entity()` 和 `to_model()` 两个静态方法

### ORM 模型规范
- 表名 snake_case
- 主键 `id` 统一为 `String(64)`（UUID/编码）
- 中文注释用 `comment` 参数
- JSON 字段用 `JSON` 类型
- 使用 `Mapped[type]` 类型注解 + `mapped_column()`

### Entity 规范
- `@dataclass` 装饰器
- 所有字段显式类型标注
- 字段名与 ORM 模型一致
- 用于 Repository 和 Service 之间的数据传输

## 十、Repository 模式

每个数据源对应一个 Repository 类，构造函数接收 client/session：

| Repository | 数据源 | 关键方法 |
|-----------|-------|---------|
| `MetaMysqlRepository` | meta MySQL | `clear_all()`, `save_*()`, `get_*_by_id()`, `get_key_columns_by_table_id()` |
| `DwMysqlRepository` | dw MySQL | `get_column_types()`, `get_column_values()`, `get_db_info()`, `validate()`, `run()` |
| `ColumnQdrantRepository` | Qdrant column 集合 | `ensure_collection()`, `upsert()`, `search(threshold=0.6, limit=10)` |
| `MetricQdrantRepository` | Qdrant metric 集合 | `ensure_collection()`, `upsert()`, `search(threshold=0.6, limit=10)` |
| `ValueEsRepository` | ES value 索引 | `ensure_index()`, `index()`, `search(threshold=0.6, limit=20)` |

### DwMysqlRepository 注意事项
- `validate(sql)` 执行 `EXPLAIN {sql}` 做语法校验，非实际执行
- `run(sql)` 执行 SQL 返回 `list[dict]`
- SQL 拼接时**注意防注入风险**（当前使用 f-string 拼接表名和字段名）

## 十一、Agent 工作流（LangGraph）

### 12 个 Node 的有向图

```
START
  │
extract_keywords ──── jieba 分词 + POS 过滤
  │
  ├──→ recall_column  ──→ Qdrant 语义召回字段信息
  ├──→ recall_value   ──→ ES 全文检索字段取值
  └──→ recall_metric  ──→ Qdrant 语义召回指标信息
  │
  └──→ merge_retrieved_info ──→ 去重、按表分组、补全主外键
         │
    ┌────┴────┐
    │         │
filter_table  filter_metric  ──→ LLM 过滤无关表和字段
    │         │
    └────┬────┘
         │
    add_extra_context ──→ 当前日期 + 数据库版本/方言
         │
    generate_sql ──→ LLM 根据过滤后的 Schema 生成 SQL
         │
    validate_sql ──→ EXPLAIN 校验
         │
    ┌────┴────┐
    │         │
 (错误)     (通过)
    │         │
correct_sql  run_sql ──→ 执行 SQL, 返回结果
    │         │
    └────┬────┘
         │
        END
```

### Node 统一编码模式

```python
async def node_name(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "节点名称", "status": "running"})
    try:
        # 业务逻辑
        # 依赖注入: runtime.context["repository_name"]
        logger.info(f"[NodeName] 日志内容")
        writer({"type": "progress", "step": "节点名称", "status": "success"})
        return {"field_name": value}  # 更新 DataAgentState
    except Exception as e:
        logger.error(f"[NodeName] 错误信息: {e}")
        writer({"type": "progress", "step": "节点名称", "status": "error"})
        writer({"type": "error", "message": str(e)})
        raise
```

### State 和 Context

**DataAgentState**（TypedDict, 13 个字段）：
```
error, query, keywords, retrieved_column_infos, retrieved_metric_infos,
retrieved_value_infos, table_infos, metric_infos, date_info, db_info, sql
```

**DataAgentContext**（TypedDict, 6 个引用）：
```
column_qdrant_repository, metric_qdrant_repository, embedding_client,
value_es_repository, meta_mysql_repository, dw_mysql_repository
```

## 十二、依赖注入（FastAPI Depends）

```python
get_meta_session → get_meta_mysql_repository → ┐
get_dw_session   → get_dw_mysql_repository   → ┤
get_column_qdrant_repository                   → ┤  get_query_service
get_metric_qdrant_repository                   → ┤
get_value_es_repository                         → ┤
get_embedding_client                            → ┘
```

## 十三、SSE 事件流

所有 Agent Node 通过 `runtime.stream_writer` 发送 SSE 事件，由 `QueryService` 包装为 `StreamingResponse`：

```
事件格式:
  data: {"type": "progress", "step": "...", "status": "running|success|error"}\n\n
  data: {"type": "result", "data": {"sql": "...", "data": [...]}}\n\n
  data: {"type": "error", "message": "..."}\n\n
```

API 端点：`POST /api/query`，body: `{"query": "统计华北地区的销售总额"}`

## 十四、LLM 配置

- 模型: `qwen-plus`（通义千问）
- API: DashScope，OpenAI 兼容接口
- Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- API Key: 环境变量 `DASHSCOPE_API_KEY`
- LangChain 初始化方式: `init_chat_model(model_provider="openai")`

## 十五、提示词管理

所有 prompt 文件在 `prompts/` 目录，`.prompt` 扩展名：

| 文件名 | 用途 |
|-------|------|
| `extend_keywords_for_column_recall.prompt` | 为字段召回扩展关键词 |
| `extend_keywords_for_metric_recall.prompt` | 为指标召回扩展关键词 |
| `extend_keywords_for_value_recall.prompt` | 为值检索扩展关键词 |
| `filter_table_info.prompt` | 过滤无关表/字段 |
| `filter_metric_info.prompt` | 过滤无关指标 |
| `generate_sql.prompt` | 生成 SQL |
| `correct_sql.prompt` | 修正错误的 SQL |

加载方式：
```python
# app/prompt/prompt_loader.py
def load_prompt(name: str):
    path = Path(__file__).parents[2] / "prompts" / f"{name}.prompt"
    return path.read_text(encoding="utf-8")
```

## 十六、关键依赖

| 包 | 版本 | 用途 |
|----|------|------|
| fastapi[standard] | >=0.136.3 | Web 框架 |
| langgraph | >=1.2.1 | Agent 有向图 |
| langchain | >=1.3.1 | LLM 编排 |
| langchain-openai | >=0.2.0 | OpenAI 兼容接口 |
| sqlalchemy | >=2.0.50 | ORM |
| asyncmy | >=0.2.11 | 异步 MySQL 驱动 |
| qdrant-client | >=1.18.0 | Qdrant 客户端 |
| elasticsearch[async] | >=8,<9 | ES 异步客户端 |
| loguru | >=0.7.3 | 日志 |
| omegaconf | >=2.3.0 | 配置管理 |
| jieba | >=0.42.1 | 中文分词 |
| openai | >=2.38.0 | OpenAI SDK |
| cryptography | >=48.0.0 | MySQL SSL 支持 |

## 十七、常用命令

```bash
# 启动开发服务器
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 构建知识库（需要 Docker 服务运行中）
python -m app.scripts.build_meta_knowledge

# 启动所有基础设施
docker compose -f docker/docker-compose.yaml up -d

# 停服务
docker compose -f docker/docker-compose.yaml down
```

## 十八、常见注意事项

1. **SQLAlchemy 异步模式**：`expire_on_commit=False` 必须设置，否则访问过期对象会触发隐式查询（而异步中不允许在非 await 处做查询）
2. **Embedding batch 限制**：API 每批最多 10 条，`DashScopeEmbeddings.aembed_documents()` 内置了自动分批逻辑
3. **控制台日志编码**：Windows 下必须强制 `sys.stdout` 为 UTF-8，否则中文会乱码
4. **SQL 拼接安全**：`DwMysqlRepository` 中表名/字段名使用 f-string 拼接（因 SQLAlchemy 无法参数化标识符），需注意 SQL 注入风险
5. **MetaMysqlRepository 方法名 typo**：`sav_metric_infos` 少了个 e，调用时注意
6. **ES IK 分词插件版本**：8.19.0 版本对应 ES 8.19.10，升级 ES 时记得同步升级
