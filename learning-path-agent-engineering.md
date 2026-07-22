# Agent 后端工程能力补齐路线

> 本文档基于生产级 Agent 的开发经验，梳理从"能跑 demo"到"能上线"需要补齐的后端工程能力，以及具体的学习路径和练习方法。

---

## 一、前置认知：Agent 不是聊天机器人

生产环境一个 Agent 拆开来看，**没有一个是 Agent 独有的组件**：

| Agent 组件 | 本质对应 | 后端概念 |
|---|---|---|
| LLM 推理 | 计算节点 | 服务编排 |
| 工具调用 | RPC 调用 | 网络通信、认证、超时、重试 |
| 短期记忆（上下文窗口） | 内存管理 | 缓存淘汰策略 |
| 长期记忆（向量库） | 持久化 + 检索 | 数据库 + 搜索引擎 |
| 多 Agent 协作 | 分布式系统 | 消息队列、一致性、死锁 |
| 编排逻辑（loop） | 工作流引擎 | 状态机、DAG 调度 |

核心结论：**模型决定 Agent 能做多酷的事，工程决定 Agent 能不能持续做多酷的事。前者决定上限，后者决定下限。**

---

## 二、能力清单（按优先级排列）

### 第一梯队：不补就出事

#### 1. 异步编程

| 项目 | 说明 |
|---|---|
| **为什么需要** | LLM 流式输出 + 多工具并发调用 + 多用户请求，同步阻塞代码会导致全服务卡死 |
| **知识要点** | `async/await`、事件循环、协程 vs 线程、`asyncio.gather` / `asyncio.create_task`、`asyncio.Queue`、信号量（Semaphore） |
| **踩坑案例** | 某个工具调用里同步查数据库，连接池被打满 → 其他所有请求排队等待 → 用户感觉"卡死" |
| **练习方法** | 把 Agent 调 LLM 的地方从 `requests.post()` 改成 `httpx.AsyncClient`；用 `Semaphore` 控制最大并发数 |

#### 2. 超时控制

| 项目 | 说明 |
|---|---|
| **为什么需要** | LLM 可能卡住、工具接口可能 hang、网络可能抖动。每一层没有超时，整个请求可能无限等待 |
| **知识要点** | 三层超时：工具级（如 5s）→ 任务级（如 30s）→ 会话级（如 5min）；`asyncio.timeout`、`asyncio.wait_for` |
| **练习方法** | 给每层封装一个 timeout wrapper，超时后捕获 `asyncio.TimeoutError`，返回兜底回复 |

#### 3. 重试 + 幂等

| 项目 | 说明 |
|---|---|
| **为什么需要** | LLM 可能返回格式错、工具可能 500、网络可能闪断。不重试就是直接失败，重试不做幂等就是数据脏 |
| **知识要点** | 指数退避（exponential backoff）+ jitter（随机抖动）；区分可重试错误（500/超时）vs 不可重试（400/认证失败）；幂等键（idempotency key）设计 |
| **踩坑案例** | 下单接口没做幂等，LLM 超时自动重试三次 → 用户付了一份钱下了三份单 → 后端连夜对账 |
| **练习方法** | 用 `tenacity` 库封装 RetryWrapper；给写操作（INSERT/UPDATE/DELETE）加幂等键 |

#### 4. 日志 + 追踪

| 项目 | 说明 |
|---|---|
| **为什么需要** | Agent 是个黑盒，一次请求可能调了 LLM 三次、五个工具、两次向量库。出问题不知道哪步炸的 |
| **知识要点** | 结构化日志（`structlog` / `loguru`）、Trace ID 贯穿、`OpenTelemetry`、关键节点（LLM 调用、工具入出、检索结果）必须打点 |
| **练习方法** | 每条日志带 `trace_id` + `step_name` + `duration_ms`；实现一个装饰器自动为每个工具调用打日志 |

#### 5. 成本监控

| 项目 | 说明 |
|---|---|
| **为什么需要** | LLM 按 token 计费，单次看着少，乘上用户量每月是吓人的数字 |
| **踩坑案例** | 上线没做成本监控，月底账单是预期的五倍，单个用户平均消耗远超预期 |
| **练习方法** | 每次 LLM 调用记录 token 消耗（prompt_tokens + completion_tokens），按用户/会话聚合，超出阈值告警 |

---

### 第二梯队：用户一多就出事

#### 6. 限流

| 项目 | 说明 |
|---|---|
| **为什么需要** | LLM 行为不确定，这一轮调一次工具下一轮调五次，可能一个会话把 API 额度跑光 |
| **知识要点** | 用户级限流（token/min）、工具级限流（调用次数/min）、令牌桶算法、漏桶算法 |
| **练习方法** | 给每个 API key 封装一个限流器；实现用户级 Token bucket |

#### 7. 连接池管理

| 项目 | 说明 |
|---|---|
| **为什么需要** | 多用户并发时重复创建连接是巨大的浪费，且可能打满系统句柄 |
| **知识要点** | HTTP 连接池（`httpx` / `aiohttp`）、DB 连接池（`asyncpg` / `psycopg_pool`）、Redis 连接池 |
| **练习方法** | 检查项目里是否有每次调用都 `connect()` / `disconnect()` 的地方，改为全局连接池复用 |

#### 8. 降级 + 熔断

| 项目 | 说明 |
|---|---|
| **为什么需要** | 依赖的工具全挂了，Agent 还在空转重试，资源全浪费 |
| **知识要点** | 熔断器三状态：Closed → Open（连续失败达阈值）→ Half-Open（试探恢复）；降级策略：兜底回复、缓存结果、转人工 |
| **练习方法** | 实现一个熔断器：连续 5 次失败后熔断 30s，Half-Open 允许一次试探请求 |

---

### 第三梯队：复杂了就出事

#### 9. 上下文窗口管理

| 项目 | 说明 |
|---|---|
| **为什么需要** | 窗口有限，塞满后要么截断要么压缩。不能全丢，也不能无脑保留 |
| **知识要点** | 滑动窗口策略、Summary 压缩策略（把早期消息压缩成一句摘要）、混合策略、token 计数 |
| **练习方法** | 实现一个 ContextManager：超过 4K token 时将最早的消息压缩为摘要 |

#### 10. 向量存储 + 检索

| 项目 | 说明 |
|---|---|
| **为什么需要** | 长期记忆的核心，但 embedding 选型、chunk 策略、索引方式、rerank 每一步都有坑 |
| **知识要点** | Chunk 策略（固定长度 vs 语义分割）、Embedding 模型选型、向量库（chromadb / pgvector / milvus）、检索 + Rerank 流程 |
| **练习方法** | 把历史 SQL 查询存入向量库；用户问相似问题时检索作为 few-shot 示例 |

#### 11. 多 Agent 编排

| 项目 | 说明 |
|---|---|
| **为什么需要** | 一旦进入多 Agent（规划、执行、Review），立刻进入分布式系统。死循环、死锁、活锁全都是真实问题 |
| **知识要点** | 消息驱动的编排、超时终止、循环检测、DAG 调度、最终一致性 |
| **踩坑案例** | 三个 Agent 互相发消息发到死循环，CPU 拉满——这就是活锁 |
| **练习方法** | 读 `langgraph` 或 `crewai` 的编排源码，理解它们的终止条件和循环控制 |

#### 12. Agent 评估体系

| 项目 | 说明 |
|---|---|
| **为什么需要** | LLM 输出不确定，不能简单断言"输入 A 必须输出 B"，线上出问题可能根本发现不了 |
| **知识要点** | 离线 Eval Set 构造、LLM-as-judge 评估、在线 A/B、回归测试 |
| **练习方法** | 为一个固定的 NL2SQL 场景构造 20 个测试用例，离线评估准确率 |

---

## 三、学习路线（4 阶段）

### 阶段一：异步编程 + 超时控制（2 周）

**学习资源：**
- [Real Python - Async IO in Python](https://realpython.com/async-io-python/)
- [Python asyncio 官方文档](https://docs.python.org/3/library/asyncio.html)
- [Aiohttp 官方教程](https://docs.aiohttp.org/en/stable/) —— 看客户端部分即可

**项目动手：**
1. 把 Agent 调 LLM 的地方从同步改成异步
2. 给每个工具调用加 `asyncio.timeout`，超时返回兜底
3. 用 `Semaphore` 控制最大并发数
4. 复现"同步查 DB 卡死"的场景然后修掉

**检验标准：** 能写一个同时调 10 个工具、等最快的 3 个就返回的并发函数。

---

### 阶段二：重试 + 幂等 + 熔断（2 周）

**学习资源：**
- [The Retry Pattern - Microsoft](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry)
- [Circuit Breaker Pattern - Microsoft](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
- 读 `tenacity` 源码（Python 重试库，约 1500 行，核心逻辑极其清晰）
- [Resilience4j 文档](https://resilience4j.readme.io/)（Java 库但模式讲得最好）

**项目动手：**
1. 封装 `RetryWrapper`，支持配置重试次数 + 退避策略 + 错误类型过滤
2. 模拟超时报错，验证重试生效且幂等键防止重复写入
3. 实现熔断器：3 状态切换 + 半开试探

**检验标准：** 能给任意工具调用加一行装饰器实现重试 + 熔断。

---

### 阶段三：可观测性（1 周）

**学习资源：**
- [OpenTelemetry Python Quickstart](https://opentelemetry.io/docs/languages/python/)
- `structlog` 文档
- [12 Factor App - Logs](https://12factor.net/logs)

**项目动手：**
1. 全部替换成结构化日志（`structlog`）
2. 入口生成 `trace_id`，贯穿所有子调用
3. 记录每次 LLM 调用的 token 消耗 + 耗时
4. 实现一个"单次执行报告"——走了几步、调了什么工具、耗时多少、花了多少 token

**检验标准：** 出问题后看日志能 30s 内定位到是第几步炸的。

---

### 阶段四：状态 + 向量存储（2 周）

**学习资源：**
- [Anthropic Context Engineering 指南](https://docs.anthropic.com/en/docs/build-with-claude/context-engineering) —— 不是教程，是工程实践
- LangChain [Memory 模块源码](https://github.com/langchain-ai/langchain/tree/master/libs/core/langchain_core/memory) —— 读源码比看文档快
- [ChromaDB 文档](https://docs.trychroma.com/) —— 最易上手的向量库

**项目动手：**
1. 实现 ContextManager：超 token 阈值时自动压缩早期消息为摘要
2. 接入向量库（chromadb），历史 SQL 存入
3. 检索历史 SQL 作为 few-shot 示例的 pipeline
4. 用户级 token 预算 + 告警

**检验标准：** 一个 20 轮的对话不会因为上下文爆掉而丢失关键上下文。

---

## 四、建议的每周节奏

```
周一至周三   →   学理论 + 读文档/源码
周四至周六   →   在项目里实践、造 bug 再修掉
周日         →   整理踩坑记录，形成面试案例
```

**核心原则：** 每学一个概念，当天就在项目里造一个 bug 然后修掉。你以后面试能讲的故事，全部来自这些"修过什么 bug"的经历。

---

## 五、在你项目里的具体切入点

项目类型：NL2SQL Agent

### 今天就能做的

1. 找到调 LLM 的地方，把 `requests.post()` 改成 `httpx.AsyncClient`
2. 最外层加 `asyncio.timeout`
3. 用 `structlog` 替换 `print`，每条日志带 `trace_id`

### 这周能做的

4. 工具调用层封装 `retry decorator` + 指数退避
5. 写操作（INSERT / UPDATE / DELETE）加幂等键

### 下个月能做的

6. 上下文窗口满时自动压缩历史为摘要
7. 历史 SQL 检索做 few-shot
8. 用户级 token 预算 + 告警

---

## 六、面试可以讲的"修 Bug"案例

| Bug 场景 | 原因 | 解决方案 |
|---|---|---|
| 用户多问几句就卡死 | 同步阻塞查 DB，连接池打满 | 改为异步 + 连接池复用 |
| 下单扣了三次钱 | 重试 + 接口无幂等 | 加幂等键 + 对账 |
| 月底账单五倍预期 | 无 token 成本监控 | 按用户聚合 + 阈值告警 |
| Agent 死循环空转 | 无熔断，工具挂了还在重试 | 加熔断器 + 降级兜底 |
| 出问题找不到原因 | 没有 trace id 串联 | 结构化日志 + trace id 贯穿 |

---

## 七、推荐阅读清单

### 必读（按顺序）

1. **《Designing Data-Intensive Applications》**（DDIA）—— 读第 1、8、9 章，分布式系统的底层直觉全在这里
2. **《Patterns of Distributed Systems》** —— 重试、超时、熔断的论文级阐述
3. **Azure Architecture Center 的可靠性模式** —— Retry、Circuit Breaker、Throttling、Queue-Based Load Leveling

### 项目源码（读比写快）

4. `tenacity` —— 约 1500 行的重试库，核心逻辑极其清晰
5. `LangChain` 的 Memory 模块 —— 多种记忆策略的实现
6. `LangGraph` —— 多 Agent 编排的状态机实现
7. `OpenTelemetry Python SDK` —— 可观测性的行业标准实现

---

> **最后一句：** 短期看模型，长期看工程。模型换代越来越快，但 TCP 不会变、幂等不会变、异步不会变、分布式系统的那些约束不会变。投在工程上的时间，五年后还值钱。
