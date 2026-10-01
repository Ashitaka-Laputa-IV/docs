# Stores(存储)速读笔记

> 源文件: `src/oss/langgraph/stores.mdx`
> 一句话: store 提供跨 thread 的 long-term memory, 保存可从任意 thread 访问的任意键值数据, 与按 thread 划分的 checkpointer 互补。

## 核心概念

- **checkpointer** 保存的是作用域限定在单个 thread 的完整 graph state。
- **store** 保存的是可从任意 thread 访问的任意键值数据: 用户偏好、积累的知识、应超越单次对话而留存的事实。
- Agent Server 会自动处理 store, 无需手动实现。
- `InMemoryStore` 适合开发与测试; 生产用 `PostgresStore`、`MongoDBStore`、`RedisStore` 或 `UpstashStore`。所有实现都继承 `BaseStore`, 它就是 node 函数签名中使用的类型注解。

## 基本用法

```python
from langgraph.store.memory import InMemoryStore
store = InMemoryStore()
```

- memory 按 `tuple` 划分 namespace, 例如 `("1", "memories")` 或 `(user_id, "memories")`。
- namespace 可以是任意长度, 表示任意内容, 不必是用户特定的。

```python
user_id = "1"
namespace_for_memory = (user_id, "memories")
```

### 写入: store.put

```python
memory_id = str(uuid.uuid4())
memory = {"food_preference": "I like pizza"}
store.put(namespace_for_memory, memory_id, memory)
```

- `key` 只是 memory 的唯一标识符(`memory_id`), `value`(dict)才是 memory 本身。

### 读取: store.search

```python
memories = store.search(namespace_for_memory)
memories[-1].dict()
# {'value': {'food_preference': 'I like pizza'},
#  'key': '07e0caf4-1631-47b7-b15f-65515d4c1843',
#  'namespace': ['1', 'memories'],
#  'created_at': '2024-10-02T17:22:31.590602+00:00',
#  'updated_at': '2024-10-02T17:22:31.590605+00:00'}
```

- 最多返回 `limit` 个(默认 `10`)。
- `InMemoryStore` 按插入顺序返回, **最近的 memory 在列表末尾**; 其他 backend 排序可能不同。

### Item 对象属性

| 属性 | 说明 |
|------|------|
| `value` | 该 memory 的 value(本身是一个 dict) |
| `key` | 该 memory 在此 namespace 中的唯一 key |
| `namespace` | 字符串 tuple; 转 JSON 时可能被序列化为 list(如 `['1', 'memories']`) |
| `created_at` | 创建时间戳 |
| `updated_at` | 更新时间戳 |

> 每种 memory 类型是 Python class `Item`, 用 `.dict()` 转字典访问。

## 列出 namespace 中的条目

- 调用 `store.search`(async 版 `store.asearch`), **不传 `query` 也不传 `filter`**, 会返回 `namespace_prefix` 下最多 `limit` 个条目; 不需要 semantic ranking 时用它枚举 namespace 中所有内容。

```python
# 返回 ("alice", "memories") 下最多 100 个条目
items = store.search(("alice", "memories"), limit=100)
```

### 三点行为需要留意

- **`namespace_prefix` 是前缀匹配, 非精确匹配**: `("alice",)` 也会返回 `("alice", "memories")`、`("alice", "preferences")` 下的条目。要限定单一层级, 传完整 namespace 或在客户端按 `item.namespace` 过滤。
- **超过 `limit` 的结果会被静默截断**, 无溢出信号。把 `limit` 设得足够大, 或用 `offset` 分页。
- **默认排序取决于 backend**: `PostgresStore` / `AsyncPostgresStore` 按 `updated_at` 降序(最近更新在前); `InMemoryStore` 按插入顺序(最近插入在后)。不要依赖跨实现一致的顺序, 顺序重要时在客户端按 `item.updated_at` 排序。

### 分页遍历

```python
page_size = 50
offset = 0
while True:
    page = store.search(("alice", "memories"), limit=page_size, offset=offset)
    if not page:
        break
    for item in page:
        pass
    offset += page_size
```

### 发现有哪些 namespace

```python
# 所有以 ("alice",) 开头、截断到两层深的 namespace
namespaces = store.list_namespaces(prefix=("alice",), max_depth=2)
```

- 对应 async 版 `store.alist_namespaces`。
- 用途: 例如在列出每个用户的 memory 之前先遍历所有用户。

## 语义搜索

- 基于含义而非精确匹配查找 memory, 需为 store 配置 embedding model:

```python
from langchain.embeddings import init_embeddings

store = InMemoryStore(
    index={
        "embed": init_embeddings("openai:text-embedding-3-small"),  # embedding provider
        "dims": 1536,                                  # embedding 维度
        "fields": ["food_preference", "$"],            # 要嵌入的字段
    }
)
```

- 用自然语言 query 查找:

```python
memories = store.search(
    namespace_for_memory,
    query="What does the user like to eat?",
    limit=3,
)
```

- 控制哪些部分被嵌入: 配置 `fields` 参数, 或在 `store.put` 时指定 `index` 参数:

```python
# 只嵌入 "food_preference" 字段
store.put(
    namespace_for_memory,
    str(uuid.uuid4()),
    {"food_preference": "I love Italian cuisine", "context": "Discussing dinner plans"},
    index=["food_preference"],
)

# 不嵌入(仍可检索, 但不可语义搜索)
store.put(
    namespace_for_memory,
    str(uuid.uuid4()),
    {"system_info": "Last updated: 2024-01-01"},
    index=False,
)
```

## 在 LangGraph 中使用

store 与 checkpointer 协同: checkpointer 把 state 保存到 thread, store 让信息**跨** thread 访问。

```python
from dataclasses import dataclass
from langgraph.checkpoint.memory import InMemorySaver

@dataclass
class Context:
    user_id: str

checkpointer = InMemorySaver()

builder = StateGraph(MessagesState, context_schema=Context)
# ... add nodes and edges ...
graph = builder.compile(checkpointer=checkpointer, store=store)
```

调用时同时传 `thread_id` 与 `user_id`(作为该用户 memory 的 namespace):

```python
config = {"configurable": {"thread_id": "1"}}

for update in graph.stream(
    {"messages": [{"role": "user", "content": "hi"}]},
    config,
    stream_mode="updates",
    context=Context(user_id="1"),
):
    print(update)
```

### 在 node 中访问 store

通过 `Runtime` 对象从任意 node 访问 store 和 `user_id`, LangGraph 会自动注入:

```python
from langgraph.runtime import Runtime

async def update_memory(state: MessagesState, runtime: Runtime[Context]):
    user_id = runtime.context.user_id          # 从 runtime context 取 user id
    namespace = (user_id, "memories")          # 给 memory 分 namespace

    memory_id = str(uuid.uuid4())
    await runtime.store.aput(namespace, memory_id, {"memory": memory})
```

### 读取 memory 并用于 model 调用

```python
async def call_model(state: MessagesState, runtime: Runtime[Context]):
    user_id = runtime.context.user_id
    namespace = (user_id, "memories")

    memories = await runtime.store.asearch(
        namespace,
        query=state["messages"][-1].content,
        limit=3,
    )
    info = "\n".join([d.value["memory"] for d in memories])

    # ... 在 model 调用中使用 memories
```

**关键点**: 创建新 thread 时, 只要 `user_id` 相同, 仍能访问相同 memory —— 这就是 store 跨 thread 的意义。

### 托管环境

- 在 Studio 或托管环境使用 LangSmith 时, base store 默认可用, 无需在编译 graph 时指定。
- 但启用语义搜索**必须**在 `langgraph.json` 配置索引:

```json
{
    "store": {
        "index": {
            "embed": "openai:text-embeddings-3-small",
            "dims": 1536,
            "fields": ["$"]
        }
    }
}
```

## 构建自定义 store(进阶)

继承 `BaseStore` 并实现必需方法。内置 `InMemoryStore` 是最简单的参考实现。

### 基础契约

五个 async 方法必需; 对应同步方法(`put`、`get`、`delete`、`search`、`list_namespaces`)可选, 但为兼容同步 graph 执行建议实现。

| 方法 | 说明 |
|------|------|
| `aput(namespace, key, value, index=None)` | 存储或覆盖单个条目 |
| `aget(namespace, key)` | 按键检索单个条目; 不存在返回 `None` |
| `adelete(namespace, key)` | 删除单个条目 |
| `asearch(namespace_prefix, *, query=None, filter=None, limit=10, offset=0)` | 在 namespace 前缀下搜索; 可选按语义 query 搜索 |
| `alist_namespaces(*, prefix=None, suffix=None, max_depth=None, limit=100, offset=0)` | 列出匹配前缀/后缀模式的 namespace |

实现前可查准确签名:

```python
import inspect
from langgraph.store.base import BaseStore
print(inspect.getsource(BaseStore))
```

### namespace 设计

namespace 是字符串 tuple。实现必须支持:

- **前缀匹配**: `asearch(("alice",))` 返回 `("alice",)`、`("alice", "memories")` 及其他子 namespace 的条目。
- **精确 key 查找**: `aget(("alice", "memories"), "some-key")` 必须 O(1) 或接近 O(1)。

SQL backend 常见 schema:

```sql
CREATE TABLE store_items (
    namespace   TEXT[] NOT NULL,
    key         TEXT NOT NULL,
    value       JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (namespace, key)
);

CREATE INDEX ON store_items USING gin(namespace);
```

### 序列化

- store 的 value 是普通 Python dict, **不需要特殊序列化器**。用 `json.dumps` / `json.loads`, 或直接用 JSONB 列。
- 不要存储无法 JSON 序列化的原始 Python 对象。

### 语义搜索支持

- 接受 `query: str | None` 参数。
- `query` 不为 `None` 时对它嵌入, 按余弦相似度排序, 每个 `Item` 附带 `score` 字段。
- 不支持向量搜索的 backend 在传入 `query` 时应抛 `NotImplementedError`。

### 测试

- 目前**没有**自定义 store 的一致性测试套件。以 `InMemoryStore` 为参考写 pytest:

```python
import pytest
from langgraph.store.memory import InMemoryStore
from your_module import YourStore

@pytest.fixture
def reference():
    return InMemoryStore()

async def test_put_and_get(store, reference):
    ns = ("test", "ns")
    for s in [store, reference]:
        await s.aput(ns, "k1", {"val": 1})
        item = await s.aget(ns, "k1")
        assert item is not None
        assert item.value == {"val": 1}
```

## 易错点 / 混淆概念区分

- **checkpointer vs store**: checkpointer 保存 thread 内完整 graph state; store 保存跨 thread 的任意键值数据。想让另一 thread 读到信息, 只能用 store。
- **namespace 前缀匹配**: `search(("alice",))` 会连带子 namespace; 用完整 namespace 或客户端过滤。
- **`limit` 静默截断**: 不报错, 易漏数据。
- **排序因 backend 而异**: `InMemoryStore` 最近在后, `PostgresStore` 最近在前; 顺序重要时显式排序。
- **`namespace` 类型**: Python 是 `tuple[str, ...]`, JSON 序列化后可能变成 list。
- **`store.put(..., index=False)`** 的条目仍可检索, 但**不可语义搜索**。
- **生产必须换持久化 store**(`InMemoryStore` 仅开发)。
- **托管环境语义搜索需在 `langgraph.json` 配置索引**。
- **自定义 store value 必须可 JSON 序列化**。

## 心智模型

> checkpointer 是每个 thread 私有的笔记本; store 是一块按 namespace 分区的共享白板, 任何 thread 都能按 key 读写, 还能用自然语言在上面"找相关记忆"。
