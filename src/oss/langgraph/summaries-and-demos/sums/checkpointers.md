# Checkpointers(检查点)速读笔记

> 源文件: `src/oss/langgraph/checkpointers.mdx`
> 一句话: checkpointer 在每个 super-step 把 graph state 存成 snapshot, 按 thread 组织, 用于 human-in-the-loop、memory、time travel 与容错。

## 为什么需要 checkpointer

| 能力 | 说明 |
|------|------|
| Human-in-the-loop | 人可检查 / interrupt / 批准 graph 步骤, 更新 state 后 graph 能恢复执行 |
| Memory | 交互之间保留 "memory", 后续消息发到同一 thread 即可保留对先前消息的记忆 |
| Time travel | 重放先前执行以审查 / 调试; 可在任意 checkpoint 处对 state 分叉 |
| Fault-tolerance | 某 node 在 superstep 失败时, 可从上一个成功步骤重启 |
| Pending writes | node 执行到一半失败时, LangGraph 保存同 super-step 中已成功 node 的写入; 恢复时无需重跑成功 node |

## 核心概念

### Threads

- thread 是分配给每个 checkpoint 的唯一 ID(`thread_id`), 包含一串 run 累积起来的 state。
- 用 checkpointer 调用 graph **必须**在 config 的 `configurable` 中指定 `thread_id`:

```python
{"configurable": {"thread_id": "1"}}
```

- checkpointer 用 `thread_id` 作为存取 checkpoint 的主键; 没有它无法保存 state, 也无法在 interrupt 后恢复。
- thread 的当前 state 与历史 state 均可读取, 执行 run 前必须先创建 thread。

### Checkpoints

- checkpoint = thread 在某个时间点的 state, 即每个 super-step 保存的 graph state snapshot, 由 `StateSnapshot` 对象表示。

### Super-steps

- LangGraph 在每个 super-step 边界创建一个 checkpoint。super-step 是 graph 的一次 "tick", 该步中所有被调度的 node 都会执行(可能并行)。
- 顺序 graph `START -> A -> B -> END`: 输入、node A、node B 各有独立 super-step, 每完成一个产生一个 checkpoint。
- 只能从 checkpoint(即 super-step 边界)恢复执行 —— 这对 time travel 很关键。
- 除 super-step checkpoint 外, 还在 **node(task) 级别**持久化写入: 每个 node 完成时输出以 task 条目写入 `checkpoint_writes` 表, 与进行中的 checkpoint 关联。这些 per-task writes 支撑 pending writes 恢复。
- 注意: task writes 不是完整的 `StateSnapshot` checkpoint, 因此 time travel 仍从 super-step 边界的完整 checkpoint 恢复。

### 示例: 简单 graph 会产生 4 个 checkpoint

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.runnables import RunnableConfig
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class State(TypedDict):
    foo: str
    bar: Annotated[list[str], add]

def node_a(state: State):
    return {"foo": "a", "bar": ["a"]}

def node_b(state: State):
    return {"foo": "b", "bar": ["b"]}

workflow = StateGraph(State)
workflow.add_node(node_a)
workflow.add_node(node_b)
workflow.add_edge(START, "node_a")
workflow.add_edge("node_a", "node_b")
workflow.add_edge("node_b", END)

checkpointer = InMemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

config: RunnableConfig = {"configurable": {"thread_id": "1"}}
graph.invoke({"foo": "", "bar": []}, config)
```

运行后正好 4 个 checkpoint:

1. 空 checkpoint, 下一个要执行的 node 是 `START`
2. 含用户输入 `{'foo': '', 'bar': []}`, 下一个是 `node_a`
3. 含 `node_a` 输出 `{'foo': 'a', 'bar': ['a']}`, 下一个是 `node_b`
4. 含 `node_b` 输出 `{'foo': 'b', 'bar': ['a', 'b']}`, 无下一个 node

> `bar` 通道的值包含两个 node 的输出, 因为为它设置了 reducer。

### Checkpoint namespace

每个 checkpoint 有 `checkpoint_ns` 字段, 标识它属于哪个 graph / subgraph:

- `""`(空字符串): 属于父(根)graph。
- `"node_name:uuid"`: 属于作为某 node 被调用的 subgraph。嵌套 subgraph 用 `|` 连接, 如 `"outer_node:uuid|inner_node:uuid"`。

```python
def my_node(state: State, config: RunnableConfig):
    checkpoint_ns = config["configurable"]["checkpoint_ns"]
    # "" 表示父 graph, "node_name:uuid" 表示 subgraph
```

## 获取并更新 state

### 获取 state

与已保存 state 交互**必须**指定 thread identifier:

```python
# 最新 state snapshot
config = {"configurable": {"thread_id": "1"}}
graph.get_state(config)

# 指定 checkpoint_id 的 snapshot
config = {"configurable": {"thread_id": "1", "checkpoint_id": "1ef663ba-..."}}
graph.get_state(config)
```

#### StateSnapshot 字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `values` | `dict` | 该 checkpoint 处的 state 通道值 |
| `next` | `tuple[str, ...]` | 接下来要执行的 node 名; 空 `()` 表示 graph 已完成 |
| `config` | `dict` | 含 `thread_id`、`checkpoint_ns`、`checkpoint_id` |
| `metadata` | `dict` | 执行元数据: `source`(`"input"`/`"loop"`/`"update"`)、`writes`(node 输出)、`step`(super-step 计数器) |
| `created_at` | `str` | ISO 8601 时间戳 |
| `parent_config` | `dict \| None` | 上一个 checkpoint 的 config; 第一个为 `None` |
| `tasks` | `tuple[PregelTask, ...]` | 该步要执行的 task; 每个含 `id`、`name`、`error`、`interrupts`, 可选 `state`(subgraph snapshot, 需 `subgraphs=True`) |

### 获取 state 历史

```python
config = {"configurable": {"thread_id": "1"}}
list(graph.get_state_history(config))
```

- 返回该 thread 的完整执行历史(StateSnapshot 列表)。
- **最新的 checkpoint 在列表首位**(按时间倒序)。

### 查找特定的 checkpoint

```python
history = list(graph.get_state_history(config))

# 特定 node 执行前的 checkpoint
before_node_b = next(s for s in history if s.next == ("node_b",))

# 按 step 号查找
step_2 = next(s for s in history if s.metadata["step"] == 2)

# 由 update_state 产生的 checkpoint(分叉)
forks = [s for s in history if s.metadata["source"] == "update"]

# 发生 interrupt 的 checkpoint
interrupted = next(
    s for s in history
    if s.tasks and any(t.interrupts for t in s.tasks)
)
```

### 重放

- 用先前的 `checkpoint_id` 调用 graph, 会重新运行该 checkpoint 之后的 node。
- checkpoint 之前的 node 被跳过(结果已保存)。
- checkpoint 之后的 node 会重新执行, **包括 LLM 调用、API 请求或 interrupt —— 重放期间总会重新触发**。

### 更新 state

```python
graph.update_state(config, {"foo": "new value"})
```

- 用更新后的值创建一个新 checkpoint, **不修改原始 checkpoint**。
- 处理方式与 node 更新相同: 定义了 reducer 的通道会**累积**值而非覆盖。
- 可选 `as_node` 控制该更新被视为来自哪个 node, 影响接下来哪个 node 执行(time travel 相关)。

## 持久性模式

在调用任何 graph 执行方法时可指定 durability:

```python
graph.stream(
    {"input": "test"},
    durability="sync"
)
```

按持久性从低到高:

| 模式 | 行为 | 权衡 |
|------|------|------|
| `"exit"` | 仅在 graph 执行退出时持久化(成功 / 出错 / interrupt) | 长时运行 graph 性能最佳; 中间 state 不保存, 进程崩溃无法中途恢复 |
| `"async"` | 在下一步执行时异步持久化 | 性能与持久性平衡; 崩溃时小概率漏写 checkpoint |
| `"sync"` | 在下一步开始前同步持久化 | 每步都先写 checkpoint, 持久性最高, 有性能开销 |

## 优化 checkpoint 存储

- 默认每个 super-step 写入每个 state 通道的**完整值**; 长时运行 thread 存储会显著增长。
- `DeltaChannel` 只存储增量 delta 而非完整累积值, 对追加为主的通道能大幅减小 checkpoint 体积。
- 注意: `DeltaChannel` 需要 `langgraph>=1.2`, 目前处于 beta, API 未来可能变化。

## Checkpointer 库

底层由符合 `BaseCheckpointSaver` 接口的 checkpointer 驱动, 均为独立可安装库:

| 库 | 内容 | 适用 |
|----|------|------|
| `langgraph-checkpoint` | 基础接口 `BaseCheckpointSaver`、序列化接口 `SerializerProtocol`、内存实现 `InMemorySaver` | LangGraph 自带 |
| `langgraph-checkpoint-sqlite` | `SqliteSaver` / `AsyncSqliteSaver` | 实验与本地 workflow, 需单独安装 |
| `langgraph-checkpoint-postgres` | `PostgresSaver` / `AsyncPostgresSaver` | 生产环境, 需单独安装 |
| `langgraph-checkpoint-mongodb` | `MongoDBSaver` / `AsyncMongoDBSaver` | 生产环境, 需单独安装 |
| `langchain-azure-cosmosdb` | `CosmosDBSaverSync` / `CosmosDBSaver` | Azure 生产环境, 需单独安装 |

### Checkpointer 接口

每个 checkpointer 实现 `BaseCheckpointSaver` 的以下方法:

| 方法 | 作用 |
|------|------|
| `.put` | 存储一个 checkpoint 及其 config 与 metadata |
| `.put_writes` | 存储与某 checkpoint 关联的中间写入(pending writes) |
| `.get_tuple` | 按 config(`thread_id` + `checkpoint_id`)获取 checkpoint tuple, 填充 `graph.get_state()` |
| `.list` | 列出匹配 config 与筛选条件的 checkpoint, 填充 `graph.get_state_history()` |

- async 执行(`ainvoke`/`astream`/`abatch`)会用到 async 版本: `.aput`、`.aput_writes`、`.aget_tuple`、`.alist`。
- async 运行可用 `InMemorySaver`, 或 Sqlite/Postgres 的 async 版本 `AsyncSqliteSaver` / `AsyncPostgresSaver`。

### Serializer

- 保存 state 时需序列化通道值, 由 serializer 对象完成。
- 默认实现 `JsonPlusSerializer`, 底层用 ormsgpack + JSON, 支持 LangChain/LangGraph 原语、datetime、enum 等。
- **pickle 回退**: 对 msgpack 不支持的对象(如 Pandas dataframe)可用 `pickle_fallback=True`:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

graph.compile(
    checkpointer=InMemorySaver(serde=JsonPlusSerializer(pickle_fallback=True))
)
```

- **加密**: 把 `EncryptedSerializer` 实例传入 `serde` 参数即可加密所有持久化 state。最简单用 `from_pycryptodome_aes`(从 `LANGGRAPH_AES_KEY` 读取 key, 或接受 `key` 参数):

```python
import sqlite3
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

serde = EncryptedSerializer.from_pycryptodome_aes()  # 读取 LANGGRAPH_AES_KEY
checkpointer = SqliteSaver(sqlite3.connect("checkpoint.db"), serde=serde)
```

在 LangSmith 上运行时, 只要存在 `LANGGRAPH_AES_KEY`, 加密就自动启用。

## 构建自定义 checkpointer(进阶)

### 存储抽象

persistence 层建立在两个存储抽象上:

- **Checkpoints 表** — 每个 superstep 一行; 存序列化后的 graph state(`channel_values`、`channel_versions`、`versions_seen`), 链接父 checkpoint。
- **Writes 表** — superstep 内每个 node 输出一行; 存 `(task_id, channel, value)` tuple。

`put` 写一行 checkpoint; `put_writes` 写 node 输出行; `get_tuple` 把两者读回为 `CheckpointTuple`。

### 基础契约: 五个必需方法

继承 `BaseCheckpointSaver`, 缺任一都会在 runtime 抛 `NotImplementedError`:
`aput`、`aput_writes`、`aget_tuple`、`alist`、`adelete_thread`。

关键要求:

- 用 `self.serde.dumps_typed(checkpoint)` 序列化 checkpoint(能处理 delta channel 的 `_DeltaSnapshot` blob)。
- **完整存储 `metadata`**, 不要剔除未知键 —— LangGraph 会在小版本新增 metadata 字段, 丢弃会静默破坏功能。
- 把 `config["configurable"].get("checkpoint_id")` 存为父 checkpoint ID, 以便 `get_tuple` 填充 `parent_config`。
- `put_writes` 从 `langgraph.checkpoint.base` 导入 `WRITES_IDX_MAP`, 把特殊通道(`__error__`、`__interrupt__` 等)映射到预留负索引。
- `get_tuple` 的 config 有两种路径, **都必须正确工作**:
  - 没有 `checkpoint_id` -> 返回最新 checkpoint
  - 指定 `checkpoint_id` -> 返回那个确切 checkpoint(用于 time travel, 以及每次 graph 调用时的 delta channel state 重建)
- `list` 返回最新在前, 遵循 `before` 与 `limit`。
- `delete_thread` 必须同时删 checkpoint 行与 write 行。

### 行键 / 索引设计

推荐 SQL schema(节选):

```sql
CREATE TABLE checkpoints (
    thread_id          TEXT NOT NULL,
    checkpoint_ns      TEXT NOT NULL DEFAULT '',
    checkpoint_id      TEXT NOT NULL,   -- ULID, 字典序可排序
    parent_checkpoint_id TEXT,
    type               TEXT,
    checkpoint         BYTEA,
    metadata           JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE writes (
    thread_id     TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id       TEXT NOT NULL,
    task_path     TEXT NOT NULL DEFAULT '',
    idx           INTEGER NOT NULL,
    channel       TEXT NOT NULL,
    type          TEXT,
    value         BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, task_path, idx)
);
```

- `checkpoint_id` 是 ULID, 字典序排序, 越大越新。"Get latest" = `ORDER BY checkpoint_id DESC LIMIT 1`; "get by id" 是主键等值查找。
- 非 SQL 存储同理: 按 `(thread_id, checkpoint_ns, checkpoint_id)` 的直接查找必须 O(1) 或接近 O(1), 避免扫描整个 thread。

### 序列化

- 始终使用 `self.serde`(默认 `JsonPlusSerializer`)。不要直接对 metadata 用 `pickle`。
- `JsonPlusSerializer` 自动处理 `_DeltaSnapshot`(msgpack 扩展码 7)、Pydantic v2 模型、dataclass、numpy 数组、datetime、enum 等。
- 自定义 serializer 必须能对 `_DeltaSnapshot` 做往返处理。

### 可选扩展能力

| 方法 | 启用的功能 |
|------|-----------|
| `adelete_for_runs` | 回滚多任务策略 |
| `acopy_thread` | 高效的 thread 分叉 |
| `aprune` | thread 历史裁剪 |
| `aget_delta_channel_history` | 高效的 delta channel state 重建 |

Agent Server 启动时会自动检测实现了哪些能力并激活对应功能。

### Delta channel support(beta)

- `DeltaChannel` 是 reducer 通道, checkpoint blob 中只存哨兵 `MISSING`, state 通过把祖先写入经 reducer 重放来重建。使 `messages` 这类累积通道的 checkpoint blob 每步为 O(1) 而非 O(N)。
- 加载 checkpoint 时若 delta channel 不在 `channel_values` 中, LangGraph 调用 `get_delta_channel_history(config, channels)`, 返回:
  - `writes`: 祖先链中对该通道的所有写入(最早在前, 直到最近 snapshot)
  - `seed`(可选): 最近拥有 `_DeltaSnapshot` blob 的祖先处存的 blob
- 然后 runtime 调用 `channel.from_checkpoint(seed)` 与 `channel.replay_writes(writes)` 重建当前值。
- **关键依赖**: 默认实现沿祖先链每次都调用 `get_tuple(cursor)`, 且总是带具体 `checkpoint_id`。若该查找返回 `None`, 遍历立即停止, 每个 delta channel 会被**静默重建为空** —— 这就是 specific-id 路径必须正确的原因。
- 性能覆写: 查询支持好的 backend 可覆写 `get_delta_channel_history`, 用两次查询拿到祖先链与写入。
- 裁剪(custom `prune` / `delete_for_runs`)时**绝不能删除**存留 checkpoint 的 delta channel 所依赖的 write 行。安全选项: 裁剪前先遍历标记; 裁剪前强制生成 snapshot(重写 `channel_values[ch] = _DeltaSnapshot(重建值)`); 或对 delta-channel thread 跳过裁剪。
- `copy_thread` 要复制完整的祖先链而非仅头部 checkpoint, 否则 delta channel 复制后会重建为空。

### 一致性测试

```python
pip install langgraph-checkpoint-conformance
```

```python
import asyncio
from langgraph.checkpoint.conformance import checkpointer_test, validate

@checkpointer_test(name="MyCheckpointer")
async def my_checkpointer():
    async with MyCheckpointer.create() as saver:
        yield saver

async def main():
    report = await validate(my_checkpointer)
    report.print_report()
    if not report.passed_all_base():
        raise RuntimeError("Checkpointer failed conformance suite")

asyncio.run(main())
```

- 套件覆盖全部五个基础方法以及扩展能力(含 `aget_delta_channel_history`), 自动检测实现了哪些扩展并逐项测试。发布前应作为 CI 一部分运行。

## 易错点 / 混淆概念区分

- **`thread_id` 是必需的**: 忘记传就完全无法保存 / 恢复 state。
- **super-step 边界才恢复**: 只能从完整 checkpoint(time travel)恢复; node 级 task writes 不是完整 snapshot。
- **`get_state_history` 最新在前**: 不是最早在前, 遍历时注意顺序。
- **`update_state` 不修改原 checkpoint**, 而是生成新 checkpoint; 带 reducer 的通道会累积而非覆盖。
- **重放会重新触发 LLM / API / interrupt**, 有副作用或花钱的 node 要小心。
- **`as_node` 影响后续执行哪条边**, 用错会导致从错误的 node 继续。
- **durability="exit" 不等于能中途恢复**: 中间 state 未保存, 进程崩溃无法续跑。
- **自定义 checkpointer 的 specific-id 查找**: 若返回 `None`, delta channel 会静默变空, 且不报错 —— 最难排查的坑。
- **不要剔除 metadata 未知键**。
- **`DeltaChannel` 是 beta**, 需要 `langgraph>=1.2`。

## 心智模型

> checkpointer 是一台"每个 super-step 拍一张快照的录像机", `thread_id` 是带编号的录像带; super-step 边界是唯一可回放的帧; node 级 writes 只是可断点续传的临时草稿。
