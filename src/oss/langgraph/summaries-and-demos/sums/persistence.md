# Persistence(持久化)速读笔记

> 源文件: `src/oss/langgraph/persistence.mdx`
> 一句话: Persistence 让 LangGraph 应用把信息保留到单次 graph 运行之外; 由 **checkpointer**(thread 级 short-term memory) 和 **store**(跨 thread long-term memory) 两套互补体系组成。

## 核心概念

LangGraph 提供两套互补的 persistence 体系:

| 体系 | 作用 | 典型用途 |
|------|------|----------|
| Checkpointer | 把 thread 的 graph state 持久化为 checkpoint | 对话连续性、human-in-the-loop、time travel、容错 |
| Store | 把应用自定义数据持久化到 graph state 之外 | 用户偏好、事实、共享知识 |

大多数应用两者并用: checkpointer 追踪当前 thread, store 追踪跨 thread 的信息。

## 快速开始

用一个 checkpointer、一个 store, 或两者一起编译 graph:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

checkpointer = InMemorySaver()
store = InMemoryStore()

graph = builder.compile(checkpointer=checkpointer, store=store)

result = graph.invoke(
    {"messages": [{"role": "user", "content": "Hi, my name is Bob."}]},
    {"configurable": {"thread_id": "thread-1"}},
)
```

- 用 checkpointer 时, 调用必须提供 `thread_id`。
- 用 store 时, 通过 node 里的 `runtime.store` 读写。
- 使用 Agent Server 时无需手动配置 checkpointer 或 store, 服务端在幕后处理。

## Checkpointer 与 Store 对比

| 维度 | Checkpointer | Store |
|------|--------------|-------|
| 持久化内容 | Graph state snapshot | 应用自定义的键值数据 |
| 作用域 | 单个 thread | 跨 thread |
| memory 类型 | short-term、thread 作用域 | long-term、跨线程 |
| 适用场景 | 对话连续性、HITL、time travel、容错 | 用户偏好、事实、共享知识 |
| 访问方式 | config 中传入 `thread_id` | 从 node 或应用代码读写条目 |
| 完整指南 | checkpointers.mdx | stores.mdx |

## 排查常见问题

### 1. PostgresSaver 的 `thread_id` 过长

`thread_id` 会被存进长度有限的列, 超长会报数据库错误。

修复: 取值保持在 255 字符以内; 需要确定性 ID 时用 UUID 或哈希:

```python
import uuid

config = {"configurable": {"thread_id": str(uuid.uuid4())[:255]}}
```

### 2. `MemorySaver` / `InMemorySaver` 重启后数据丢失

它们把 checkpoint 存在 RAM 中, 进程重启即全部丢失。

修复: 生产环境改用持久化 checkpointer:
- `PostgresSaver`: 支持 async 的 PostgreSQL
- `SqliteSaver`: 面向开发环境的本地文件存储

### 3. checkpoint 无限增长

长对话中 checkpoint 不断累积, 增加延迟与存储成本。

修复: 定期裁剪旧 checkpoint, 或设置保留策略:

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string("postgresql://...")
checkpointer.setup()  # 创建带索引的表
# 可加 cron job 删除 N 天前的 checkpoint
```

### 4. 父 graph 访问不到 subgraph 的 state

每个 subgraph 管理自己独立的 checkpoint namespace, 父 graph 可能不会立即看到变更。

修复: 跨 graph 边界的数据用 Store 共享; 或配置 subgraph 写入父 graph 的 checkpoint。

## 易错点 / 注意事项

- **两者不是替代关系**: checkpointer 只管 thread 内 state, store 才能跨 thread。想让"另一个 thread 也能读到同一用户的信息", 必须用 store。
- **`InMemorySaver` / `MemorySaver` 只适合开发测试**, 生产必须换成持久化实现。
- subgraph 有自己的 checkpoint namespace, 父 graph 不会自动看到其内部变更。
- `thread_id` 长度有数据库层限制(255), 用 UUID 更安全。

## 心智模型

> 一次 graph 运行 = 一条时间线(thread); checkpointer 是这条时间线的录像带, store 是挂在时间线之外、所有 thread 都能读的共享白板。

## 下一步

- checkpointers.mdx: 用 checkpointer 持久化并查看 thread state。
- stores.mdx: 用 store 跨 thread 持久化数据。
