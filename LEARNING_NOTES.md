# data-agent 项目学习笔记

## 项目概览

这是一个**数据库智能问答系统的元数据知识库构建工具**。核心目标是：把数据库中表、字段、指标的结构化信息，转换成向量和全文索引，让后续的 NL2SQL（自然语言转 SQL）或智能问答系统能通过语义搜索快速找到相关字段。

### 一句话概括

从 YAML 配置读取表结构 → 从 MySQL 获取字段详情 → 调用云端 Embedding API 生成向量 → 存入 Qdrant（向量数据库）+ Elasticsearch（全文索引）。

---

## 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                    build_meta_knowledge.py                       │
│                   (构建脚本，入口文件)                              │
└─────────┬────────────┬────────────┬──────────────┬──────────────┘
          │            │            │              │
          ▼            ▼            ▼              ▼
   ┌──────────┐  ┌─────────┐  ┌─────────┐   ┌────────────┐
   │MySQL     │  │MySQL    │  │Qdrant   │   │DashScope   │
   │meta 库   │  │dw 库    │  │向量数据库│   │Embedding   │
   └──────────┘  └─────────┘  └─────────┘   └────────────┘
```

### 核心业务流程

```
meta_config.yaml
     │
     ▼
  读取配置（表名、字段、别名、指标定义）
     │
     ▼
  连接 DW 库查询字段类型 + 枚举值
     │
     ├──► 存入 MySQL meta 库（关系型持久化）
     │
     ├──► 字段名/描述/别名 → DashScope text-embedding-v3 → Qdrant
     │
     ├──► 字段取值 → Elasticsearch 全文索引
     │
     └──► 指标定义 → DashScope text-embedding-v3 → Qdrant
```

---

## 项目目录结构

```
data-agent/
├── app/
│   ├── agent/                 # LangGraph 智能体
│   │   ├── graph.py           # 图定义和主流程
│   │   ├── state.py           # 状态 schema
│   │   ├── context.py         # 上下文 schema（共享资源）
│   │   ├── llm.py             # LLM 客户端
│   │   └── nodes/             # 各个图节点
│   │       ├── extract_keywords.py
│   │       ├── recall_column.py
│   │       ├── recall_value.py
│   │       ├── recall_metric.py
│   │       ├── merge_retrieved_info.py
│   │       ├── filter_table.py
│   │       ├── filter_metric.py
│   │       ├── add_extra_context.py
│   │       ├── generate_sql.py
│   │       ├── validate_sql.py
│   │       ├── correct_sql.py
│   │       └── run_sql.py
│   │
│   ├── prompts/                 # LLM prompt 模板（.prompt 文件）
│   │   ├── filter_table_info.prompt
│   │   ├── filter_metric_info.prompt
│   │   ├── generate_sql.prompt
│   │   ├── correct_sql.prompt
│   │   ├── extend_keywords_for_column_recall.prompt
│   │   ├── extend_keywords_for_metric_recall.prompt
│   │   └── extend_keywords_for_value_recall.prompt
│   │   ├── filter_table_info.prompt
│   │   ├── filter_metric_info.prompt
│   │   ├── generate_sql.prompt
│   │   ├── correct_sql.prompt
│   │   ├── extend_keywords_for_column_recall.prompt
│   │   ├── extend_keywords_for_metric_recall.prompt
│   │   └── extend_keywords_for_value_recall.prompt
│   │
│   ├── clients/               # 各种外部服务的客户端管理器
│   │   ├── mysql_client_manager.py
│   │   ├── qdrant_client_manager.py
│   │   ├── embedding_client_manager.py
│   │   └── es_client_manager.py
│   │
│   ├── conf/                  # 配置数据结构
│   │   ├── app_config.py
│   │   └── meta_config.py
│   │
│   ├── core/log.py            # 日志配置（loguru）
│   │
│   ├── models/                # 数据模型
│   │   ├── base.py            # SQLAlchemy DeclarativeBase
│   │   ├── column_info_mysql.py
│   │   ├── column_metric_mysql.py
│   │   ├── metric_info_mysql.py
│   │   ├── table_info_mysql.py
│   │   └── entity/            # 实体对象（DTO 替代）
│   │       ├── column_info.py
│   │       ├── metric_info.py
│   │       ├── table_info.py
│   │       └── value_info.py
│   │
│   ├── repositories/          # 数据访问层
│   │   ├── mysql/
│   │   │   ├── dw/dw_mysql_repository.py
│   │   │   └── meta/
│   │   │       ├── meta_mysql_repository.py
│   │   │       └── mappers/
│   │   │           ├── column_info_mapper.py
│   │   │           ├── column_metric_mapper.py
│   │   │           ├── metric_info_mapper.py
│   │   │           └── table_info_mapper.py
│   │   ├── qdrant/
│   │   │   ├── column_qdrant_repository.py
│   │   │   └── metric_qdrant_repository.py
│   │   └── es/value_es_repository.py
│   │
│   ├── scripts/
│   │   └── build_meta_knowledge.py
│   └── services/
│       └── meta_knowledge_service.py
│
├── conf/
│   ├── app_config.yaml
│   └── meta_config.yaml
│
└── docker/
    └── docker-compose.yaml
```

---

## 核心流程一：元数据知识库构建（Build）

### 1. 双层数据模型：ORM 模型 vs DTO

项目采用了 ORM 模型和 DTO 分离的设计，原因是代码里的注释说得清楚：

> 如果后面技术框架更换（比如从 SQLAlchemy 换到别的 ORM），DTO 层不受影响。

**ORM 模型**（继承 `Base`）：和数据库表结构直接对应，用在 Repository 层。
**DTO**（`@dataclass`）：纯数据容器，用在 Service 层。

两者通过 **Mapper** 转换：

```
DTO (ColumnInfo) ──to_model()──► ORM (ColumnInfoMySQL) ──写入 DB──► MySQL
DTO (ColumnInfo) ◄──to_entity()── ORM (ColumnInfoMySQL) ◄──读取 DB── MySQL
```

### 2. 配置分层结构

项目有两个配置层：

**app_config.yaml** —— 基础设施配置
```yaml
qdrant:      # 向量数据库
  host: localhost
  port: 6333

embedding:   # Embedding 服务（DashScope text-embedding-v3）
  model: text-embedding-v3
  dimensions: 1024

db_meta:     # 元数据库
db_dw:       # 数据仓库
es:          # 搜索引擎
llm:         # 大模型
```

**meta_config.yaml** —— 业务元数据配置
```yaml
tables:      # 有哪些表、字段、别名
  - name: dim_region
    columns:
      - name: province
        alias: [省份, 省]
        sync: true

metrics:     # 预定义指标
  - name: GMV
    description: 成交金额总和
    relevant_columns: [fact_order.order_amount]
```

### 3. OmegaConf 配置管理

```python
# 注意 merge 顺序：后面覆盖前面的
meta_config = OmegaConf.to_object(OmegaConf.merge(schema, content))
#                                           ~~~~~~  ~~~~~~~
#                                          默认值    YAML数据
```

> ⚠️ 踩坑：`merge(content, schema)` 会把 YAML 数据被 dataclass 默认值覆盖掉，导致 `tables=0`。

### 4. DashScope 替换本地 Embedding 服务

原来：本地 Docker 运行 HuggingFace 模型（BAAI/bge-large-zh-v1.5）  
现在：DashScope text-embedding-v3，通过 OpenAI 兼容接口直接调用

自定义轻量客户端，绕过 `langchain_openai` 的 tiktoken 依赖：

```python
# DashScope Embedding API
POST /v1/embeddings
{
    "model": "text-embedding-v3",
    "input": ["文本1", "文本2"],
    "dimensions": 1024,
    "encoding_format": "float"     # 必须传！
}
```

踩坑记录：
- **tiktoken 联网下载**：`langchain_openai` 内部依赖 tiktoken，本地网络受限会挂
- **encoding_format 必须传**：不传返回 400
- **batch_size 不超过 10**：text-embedding-v3 限制

---

### 5. 分层架构 Repository → Service → Script

```
Script 层: build_meta_knowledge.py
  │  负责：初始化所有客户端、编排流程
  ▼
Service 层: MetaKnowledgeService
  │  负责：业务流程编排（读取配置 → 处理数据 → 写入存储）
  ▼
Repository 层: *Repository
    负责：单一数据源的操作（CRUD）
```

---

## 核心流程二：NL2SQL 智能体（Agent）

LangGraph 实现的多节点、有状态的 NL2SQL 智能流水线。

### Graph 概览

```
START
  │
  ▼
extract_keywords ──────────► recall_column ──┐
  │                          recall_value  ──┤
  │                          recall_metric ──┤
  │                                           ▼
  └────────────────────────────────► merge_retrieved_info
                                           │
                                    ┌──────┴──────┐
                                    ▼              ▼
                               filter_table   filter_metric
                                    │              │
                                    └──────┬──────┘
                                           ▼
                                   add_extra_context
                                           │
                                           ▼
                                      generate_sql
                                           │
                                           ▼
                                      validate_sql
                                    ┌────┴────┐
                                    │         │
                                   ✓/error   ✗/has error
                                    │         │
                                    │         ▼
                                    │    correct_sql
                                    │         │
                                    └────┬────┘
                                         ▼
                                       run_sql
                                         │
                                         ▼
                                         END
```

### State（状态）设计

```python
class DataAgentState(TypedDict):
    error: str                     # SQL 校验错误
    query: str                     # 用户原始输入
    keywords: list[str]            # 关键词
    retrieved_column_infos: list[ColumnInfo]   # Qdrant召回的字段
    retrieved_metric_infos: list[MetricInfo]   # Qdrant召回的指标
    retrieved_value_infos: list[ValueInfo]     # ES召回的值
    table_infos: list[TableInfoState]          # 合并+筛选后的表信息
    metric_infos: list[MetricInfoState]        # 合并+筛选后的指标信息
```

**设计要点**：
- 用 `TypedDict` 定义，比 `dataclass` 更适合 LangGraph 的 state 更新机制
- Node 返回值必须是 **dict**，LangGraph 会自动 merge 到 state
- `context` 中存放**只读的共享资源**（各种 Repository 客户端），不在 node 间传递

### Context（上下文）设计

```python
class DataAgentContext(TypedDict):
    column_qdrant_repository: ColumnQdrantRepository
    metric_qdrant_repository: MetricQdrantRepository
    embedding_client: DashScopeEmbeddings
    value_es_repository: ValueEsRepository
    meta_mysql_repository: MetaMysqlRepository
```

**与 State 的区别**：
| State | Context |
|-------|---------|
| 节点间传递、可修改 | 只读，全局共享 |
| 存业务数据（关键词、召回结果） | 存基础设施（客户端、连接） |
| 用 return 更新 | 通过 `runtime.context` 读取 |

### 各 Node 职责

#### 1. extract_keywords（关键词抽取）

```python
# 用 jieba 分词，按词性过滤（名词、地名、动词等）
keywords = jieba.analyse.extract_tags(query, allowPOS=allow_pos)
```

只依赖 jieba，不调用 LLM，速度很快。把 query 本身也加入关键词列表。

#### 2. recall_column（字段向量召回）

1. 调用 LLM 扩展关键词（`extend_keywords_for_column_recall` prompt）
2. 用 `aembed_documents` 批量向量化所有关键词
3. 逐个向量到 Qdrant 做相似度搜索（`score_threshold=0.6, limit=10`）
4. 字典去重后写入 `retrieved_column_infos`

```python
vectors = await embedding_client.aembed_documents(keywords)
for vector in vectors:
    results = await column_qdrant_repository.search(vector, score_threshold=0.6, limit=10)
```

**注意**：`query_points` 的 `query` 参数只接受单条向量，不能传列表。误传列表会报 `"Conversion between multi and regular vectors failed"`。

#### 3. recall_value（字段值全文召回）

从 ES 全文索引中召回字段的具体取值（如"华北"、"广东省"等）。步骤类似：
1. LLM 扩展关键词
2. 逐个关键词调 ES 搜索（`multi_match` 查询）
3. 去重后写入 `retrieved_value_infos`

#### 4. recall_metric（指标语义召回）

同 recall_column，但搜索的是 `metric_info_collection`。

#### 5. merge_retrieved_info（信息聚合—三路召回合并）

合并三个召回路径（column + value + metric）的结果，从 MySQL 补充表的完整信息，输出 `table_infos` 和 `metric_infos`。

**处理流程**：
1. 将召回的字段信息 `retrieved_column_infos` 按 ID 字典化去重
2. 遍历 `retrieved_metric_infos`，补充指标关联的字段（`relevant_columns`）
3. 遍历 `retrieved_value_infos`，将字段取值加入对应字段的 `examples` 中
4. 按 `table_id` 对字段分组
5. 强制为每张表添加主外键字段（通过 `get_key_columns_by_table_id`）
6. 组装成 `TableInfoState` 和 `MetricInfoState`

**已修复的 Bug**：
- `get_key_columns_by_table_id` 对某些表返回 `None`，导致 `TypeError: 'NoneType' object is not iterable`
- 修复：添加 `if key_columns is None: continue` 守卫

#### 6. filter_table / filter_metric（筛选—LLM 裁剪）

已实现 LLM 筛选逻辑，不再是占位节点。

**filter_table 细节**：
- 将 `table_infos` 用 YAML 格式化后传给 LLM（`sort_keys=False` 保持字段顺序）
- LLM 返回 JSON：`{"表名1": ["字段1", "字段2"], ...}`
- 代码按 LLM 结果裁剪字段：`table_info["columns"] = [col for col in table_info["columns"] if col["name"] in result[table_info["name"]]]`
- 选中字段为空时，整表被剔除
- 返回 `{"table_infos": filtered_table_infos}`

**filter_metric 细节**：
- 将 `metric_infos` 用 YAML 格式化后传给 LLM
- LLM 返回 JSON 数组：`["指标名1", "指标名2"]`
- 代码过滤：`[m for m in metric_infos if m["name"] in result]`
- 返回 `{"metric_infos": filtered_metric_infos}`

#### 7. add_extra_context（添加上下文）

当前为占位节点（`asyncio.sleep(2)`）。

#### 8. generate_sql（SQL 生成）

当前为占位节点（`asyncio.sleep(2)`）。

#### 9. validate_sql（SQL 校验）

当前为占位校验：直接返回 `{"error": None}`，视为 SQL 校验通过。

**条件边决策**：`error` 为 `None` → 走 `run_sql`；有内容 → 走 `correct_sql`。

#### 10. correct_sql（SQL 修正）

当前为占位节点。

#### 11. run_sql（执行 SQL）

当前为占位节点（`asyncio.sleep(2)`）。

### Node 编写规范

```python
async def node_name(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    # 1. 读取 state
    # 2. 读取 context 中的 client/repository
    # 3. 业务逻辑
    # 4. 返回 dict（LangGraph 自动 merge 到 state）
    return {"state_key": value}
```

常见踩坑：
- **Node 返回必须是 dict**，直接返回 list 会报 `Expected dict, got [...]`
- **`chain.invoke()` 是同步方法**，不要加 `await`
- **`async def` 方法必须 `await`**，忘了就报 `coroutine' object is not iterable`

### 日志与流式输出

```python
# 1. loguru 日志 — 持久化到文件 + 控制台
from app.core.log import logger
logger.info(f"[NodeName] 关键信息: {data}")

# 2. runtime.stream_writer — 实时推送到前端/流
writer = runtime.stream_writer
writer("正在生成SQL语句")     # 会作为 stream_mode='custom' 的一个 chunk 输出
```

**设计原因**：
- `logger` 写在日志文件里，调试用
- `stream_writer` 用于给用户展示实时进度（LangGraph 的 `astream` 模式下可见）

---

## 关键技术点

### 1. Embedding 批量向量化

```python
# embedding_client_manager.py - 自定义轻量客户端
class DashScopeEmbeddings:
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        async with aiohttp.ClientSession() as session:
            # 内部已处理 batch_size=10 分片
            ...
```

**`embed_query` vs `aembed_documents`**：
- `embed_query(text)`：同步，单条。适用于搜索场景
- `aembed_documents(texts)`：异步，批量。适用于构建/召回场景

### 2. Qdrant 向量搜索

```python
# ColumnQdrantRepository
async def search(self, vector, score_threshold, limit) -> list[ColumnInfo]:
    result = await self.client.query_points(
        collection_name=self.collection_name,
        query=vector,               # 单条向量，不是列表
        limit=limit,
        score_threshold=score_threshold,
    )
    return [ColumnInfo(**point.payload) for point in result.points]
```

- 向量维度 1024（与 text-embedding-v3 对齐）
- 距离计算：余弦相似度（Cosine）
- `score_threshold` 控制召回精度，建议 0.75 以上

### 3. ES 字段值搜索

```python
# ValueEsRepository
async def search(self, keyword: str, limit: int = 10) -> list[ValueInfo]:
    query = {
        "query": {"multi_match": {"query": keyword, "fields": ["value"]}}
    }
```

ES 存储字段的实际取值（如省份名、会员等级），用 IK 分词器做中文分词。

### 4. Prompt 加载

```python
def load_prompt(name: str):
    prompt_path = Path(__file__).parents[2] / "prompts" / f"{name}.prompt"
    return prompt_path.read_text(encoding="utf-8")  # 必须指定 utf-8！
```

- 路径从调用文件往上 3 级（`parents[2]` 是项目根目录），再进 `prompts/` 目录
- prompt 文件使用 `.prompt` 扩展名，纯文本格式，支持 `{placeholder}` 模板变量

> ⚠️ Windows 上 `read_text()` 默认用 GBK 编码，prompt 文件是 UTF-8，会报 `UnicodeDecodeError`。必须显式指定 `encoding="utf-8"`。

### 5. 资源生命周期管理

```python
async with meta_mysql_client_manager.session_factory() as meta_session:
    # 整个 graph 运行期间 session 保持打开
    async for chunk in graph.astream(...):
        ...

# graph 结束后统一关闭所有连接
await qdrant_client_manager.close()
await meta_mysql_client_manager.close()
```

确保：
- **session 的 `async with` 包裹了整个 graph 的运行过程**，不要提前退出
- 所有 client manager 在结束时都调 `close()`

---

## Qdrant 数据设计

| Collection | 内容 | 每条向量对应 |
|------------|------|-------------|
| `column_info_collection` | 字段向量 | 字段名、描述、别名各一条 |
| `metric_info_collection` | 指标向量 | 指标名、描述、别名各一条 |

每个字段生成多条记录的规则：
| 来源 | 条数 | 示例 |
|------|------|------|
| 字段名 | 1 | `province` |
| 字段描述 | 1 | "订单所属的省份名称" |
| 每个别名 | N | `省份`, `省`, `所在省份` |

共 24 个字段 × （2 + 平均别名数）= ~98 条。

---

## 踩坑记录

| 问题 | 现象 | 原因 | 解决 |
|------|------|------|------|
| Collection 不存在 | Qdrant 里空的 | 未运行构建脚本 | `python build_meta_knowledge.py` |
| `tables=0` | 配置没加载到 | `merge` 顺序反了 | 保证 `merge(schema, content)` |
| API 401 | Unauthorized | API Key 是占位符 | 环境变量 `${oc.env:KEY}` |
| API 400 | 请求格式错误 | 没传 `encoding_format` | 加上 `"encoding_format": "float"` |
| batch_size 错误 | "not be larger than 10" | 超 text-embedding-v3 限制 | 设为 `batch_size=10` |
| MySQL 主键冲突 | Duplicate entry | 重复运行未清旧数据 | 加 `clear_all()` 先删后插 |
| payload 序列化失败 | dict 类型错误 | dataclass 直接传 Qdrant | 用 `asdict()` 转 dict |
| `coroutine` not iterable | TypeError | 忘记 `await` | 加上 `await` |
| class 传了类本身 | 类型不匹配 | `TableInfoMySQL()` 带括号 | 去掉括号：`TableInfoMySQL` |
| Node 返回 list | Expected dict | node 直接 return list | 改为 `return {"key": value}` |
| prompt 加载乱码 | UnicodeDecodeError | 默认 GBK 编码 | 指定 `encoding="utf-8"` |
| multi-vector 转换失败 | 400 Bad Request | query 传了向量列表 | 每次只传单个向量 |
| `None` not iterable | TypeError | `get_key_columns_by_table_id` 返回 `None` | 加 `if key_columns is None: continue` 守卫 |
| `merge_retrieved_info` 返回缺少 `table_infos`/`metric_infos` | state 中没有对应字段 | node 只返回了 `retrieved_*` 等原始数据，未组装成最终格式 | 确保 node 输出直接是 `{"table_infos": ..., "metric_infos": ...}` |
| 筛选后 table 数据未覆盖 state | 下游拿到的仍是全量数据 | `filter_table` 只打印了日志，未更新 state | 加上 `return {"table_infos": filtered_table_infos}` |

---

## 运行和验证

```bash
# 构建知识库
$env:DASHSCOPE_API_KEY="sk-你的Key"
python app/scripts/build_meta_knowledge.py

# 运行 NL2SQL 智能体
python app/agent/graph.py
```

| 存储 | 验证方式 |
|------|----------|
| Qdrant | http://localhost:6333/dashboard |
| MySQL | `select * from meta.column_info;` |
| ES | `GET /value_index/_search` |
