# 记忆(Add memory)速读笔记

> 源文件: `src/oss/langgraph/add-memory.mdx`
> 一句话: 在 LangGraph 中加两类 memory —— short-term memory(随 state 走, 支撑多轮对话) 与 long-term memory(跨会话, 存用户 / 应用级数据); 并管理长对话带来的 context window 问题。

## 总览

AI 应用需要 memory 在多次交互之间共享上下文。LangGraph 中两类 memory:

| 类型 | 挂载方式 | 作用 |
|------|----------|------|
| Short-term memory | 作为 agent state 的一部分, 配合 checkpointer | 多轮对话 |
| Long-term memory | 用 store | 跨会话存储用户特定或应用级数据 |

## 添加 short-term memory

Short-term memory 是 thread 级的 persistence, 让 agent 跟踪多轮对话:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph

checkpointer = InMemorySaver()

builder = StateGraph(...)
graph = builder.compile(checkpointer=checkpointer)

graph.invoke(
    {"messages": [{"role": "user", "content": "hi! i am Bob"}]},
    {"configurable": {"thread_id": "1"}},   # 必须指定 thread_id
)
```

### 在生产环境使用

用数据库支持的 checkpointer:

```python
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable"
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    builder = StateGraph(...)
    graph = builder.compile(checkpointer=checkpointer)
```

可选的数据库 checkpointer:

| 数据库 | 同步类 | 异步类 | 安装 |
|--------|--------|--------|------|
| Postgres | `PostgresSaver` | `AsyncPostgresSaver` | `pip install -U "psycopg[binary,pool]" langgraph langgraph-checkpoint-postgres` |
| MongoDB | `MongoDBSaver` | `AsyncMongoDBSaver` | `pip install -U pymongo langgraph langgraph-checkpoint-mongodb` |
| Redis | `RedisSaver` | `AsyncRedisSaver` | `pip install -U langgraph langgraph-checkpoint-redis` |
| Oracle | `OracleSaver` | `AsyncOracleSaver` | `pip install -U langgraph langgraph-oracledb` |

- 首次使用 Postgres / Redis / Oracle checkpointer 时需调用 `checkpointer.setup()`。
- 用 `from_conn_string(...)` 作为上下文管理器打开连接。
- 典型用法: 同一 `thread_id` 先问 "hi! I'm bob", 再问 "what's my name?", 第二次能答出 Bob —— 体现 thread 内记忆。

### 在 subgraphs 中使用

只需在编译**父 graph** 时提供 checkpointer, LangGraph 会自动向子 subgraphs 传播:

```python
from langgraph.graph import START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver

class State(TypedDict):
    foo: str

def subgraph_node_1(state: State):
    return {"foo": state["foo"] + "bar"}

subgraph_builder = StateGraph(State)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph = subgraph_builder.compile()

builder = StateGraph(State)
builder.add_node("node_1", subgraph)
builder.add_edge(START, "node_1")

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
```

也可配置 subgraph 特定的 checkpointing 行为:

```python
subgraph_builder = StateGraph(...)
subgraph = subgraph_builder.compile(checkpointer=True)   # 让 subgraph 拥有自己的 checkpointing
```

## 添加 long-term memory

跨对话存储用户特定或应用特定数据:

```python
from langgraph.store.memory import InMemoryStore
from langgraph.graph import StateGraph

store = InMemoryStore()

builder = StateGraph(...)
graph = builder.compile(store=store)
```

### 在 node 内部访问 store

用 store 编译 graph 后, LangGraph 会自动把 store 注入 node 函数; **推荐通过 `Runtime` 对象访问**:

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime
import uuid

@dataclass
class Context:
    user_id: str

async def call_model(state: MessagesState, runtime: Runtime[Context]):
    user_id = runtime.context.user_id
    namespace = (user_id, "memories")

    # 检索相关 memory
    memories = await runtime.store.asearch(
        namespace, query=state["messages"][-1].content, limit=3
    )
    info = "\n".join([d.value["data"] for d in memories])

    # ... 在 model 调用中使用

    # 写入新 memory
    await runtime.store.aput(
        namespace, str(uuid.uuid4()), {"data": "User prefers dark mode"}
    )

builder = StateGraph(MessagesState, context_schema=Context)
builder.add_node(call_model)
builder.add_edge(START, "call_model")
graph = builder.compile(store=store)

graph.invoke(
    {"messages": [{"role": "user", "content": "hi"}]},
    {"configurable": {"thread_id": "1"}},
    context=Context(user_id="1"),   # 调用时传 context
)
```

### 在生产环境使用

用数据库支持的 store:

```python
from langgraph.store.postgres import PostgresStore

DB_URI = "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable"
with PostgresStore.from_conn_string(DB_URI) as store:
    builder = StateGraph(...)
    graph = builder.compile(store=store)
```

可选持久化 store: Postgres (`AsyncPostgresStore`)、Redis (`RedisStore` / `AsyncRedisStore`)、Oracle (`OracleStore` / `AsyncOracleStore`)。首次使用需 `store.setup()`。

典型工程模式(Postgres store + checkpointer):

```python
async def call_model(state: MessagesState, runtime: Runtime[Context]):
    user_id = runtime.context.user_id
    namespace = ("memories", user_id)
    memories = await runtime.store.asearch(namespace, query=str(state["messages"][-1].content))
    info = "\n".join([d.value["data"] for d in memories])
    system_msg = f"You are a helpful assistant talking to the user. User info: {info}"

    # 仅当用户要求记住时才写 memory
    if "remember" in state["messages"][-1].content.lower():
        await runtime.store.aput(namespace, str(uuid.uuid4()), {"data": "User name is Bob"})

    response = await model.ainvoke(
        [{"role": "system", "content": system_msg}] + state["messages"]
    )
    return {"messages": response}
```

- 在 thread 1 说 "Hi! Remember: my name is Bob", 在 **thread 2** 问 "what is my name?" 仍能答出 —— 因为 `user_id` 相同, store 跨 thread 共享。

### 使用语义搜索

```python
from langchain.embeddings import init_embeddings
from langgraph.store.memory import InMemoryStore

embeddings = init_embeddings("openai:text-embedding-3-small")
store = InMemoryStore(
    index={
        "embed": embeddings,
        "dims": 1536,
    }
)

store.put(("user_123", "memories"), "1", {"text": "I love pizza"})
store.put(("user_123", "memories"), "2", {"text": "I am a plumber"})

items = store.search(("user_123", "memories"), query="I'm hungry", limit=1)
```

- 在 node 中用 `runtime.store.asearch(ns, query=..., limit=...)` 按语义检索, 拼进 system prompt。
- `InMemoryStore` 适合开发; 生产用 `PostgresStore`、`MongoDBStore` 或 `RedisStore`。

## 管理 short-term memory

启用 short-term memory 后, 长对话可能超出 LLM context window。常见方案:

- **裁剪消息**: 调用 LLM 前移除最前或最后 N 条。
- **删除消息**: 从 LangGraph state 中永久删除。
- **总结消息**: 对较早消息做摘要, 用一段摘要替换。
- **管理 checkpoints**: 存储和检索消息历史。
- 自定义策略(如消息过滤)。

### 裁剪消息(trim_messages)

用 token 数判断何时截断:

```python
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately,
)

def call_model(state: MessagesState):
    messages = trim_messages(
        state["messages"],
        strategy="last",                    # 保留最后 max_tokens
        token_counter=count_tokens_approximately,
        max_tokens=128,
        start_on="human",                   # 以 human 消息开头
        end_on=("human", "tool"),           # 以 human/tool 结尾
    )
    response = model.invoke(messages)
    return {"messages": [response]}

builder = StateGraph(MessagesState)
builder.add_node(call_model)
```

- 即使中间消息被裁掉, 完整历史仍在 checkpointer 中, 需要时可通过 checkpoint 找回。
- `end_on=("human", "tool")` 是为了保证裁剪后历史对 LLM provider 合法。

### 删除消息(RemoveMessage)

要注意: 删除只影响 graph state, 是永久移除。需要 state key 使用带 `add_messages` reducer 的通道(如 `MessagesState`)。

移除特定消息:

```python
from langchain.messages import RemoveMessage

def delete_messages(state):
    messages = state["messages"]
    if len(messages) > 2:
        # 移除最早的两条
        return {"messages": [RemoveMessage(id=m.id) for m in messages[:2]]}
```

移除**全部**消息:

```python
from langgraph.graph.message import REMOVE_ALL_MESSAGES

def delete_messages(state):
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}
```

> 警告: 删除时**必须确保结果消息历史有效**。检查所用 LLM provider 的限制, 例如某些 provider 期望历史以 `user` 消息开头; 大多数 provider 要求带 tool calls 的 `assistant` 消息后面跟着对应的 `tool` 结果消息。

### 总结消息(summarization)

裁剪 / 删除的问题是会丢信息; 更精细的做法是用 chat model 总结历史。

思路: 扩展 state 增加 `summary` key:

```python
from langgraph.graph import MessagesState

class State(MessagesState):
    summary: str
```

生成摘要并把已有摘要作为下一次总结的上下文:

```python
def summarize_conversation(state: State):
    summary = state.get("summary", "")

    if summary:
        summary_message = (
            f"This is a summary of the conversation to date: {summary}\n\n"
            "Extend the summary by taking into account the new messages above:"
        )
    else:
        summary_message = "Create a summary of the conversation above:"

    messages = state["messages"] + [HumanMessage(content=summary_message)]
    response = model.invoke(messages)

    # 删除除最近 2 条外的所有消息
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
    return {"summary": response.content, "messages": delete_messages}
```

- 当 `messages` 累积到一定数量后调用该 node。
- 也可用 `langmem.short_term.SummarizationNode` 自动处理: 它在 `context` 中维护 `RunningSummary`, 并用私有输入 state 隔离总结节点返回的消息。

```python
from langmem.short_term import SummarizationNode, RunningSummary

summarization_node = SummarizationNode(
    token_counter=count_tokens_approximately,
    model=summarization_model,
    max_tokens=256,
    max_tokens_before_summary=256,
    max_summary_tokens=128,
)
```

### 管理 checkpoints

#### 查看 thread state

```python
config = {
    "configurable": {
        "thread_id": "1",
        # 可选: 指定 checkpoint_id, 否则显示最新
        # "checkpoint_id": "1f029ca3-1f5b-6704-8004-820c16b69a5a"
    }
}
graph.get_state(config)          # Graph / Functional API
checkpointer.get_tuple(config)   # Checkpointer API(返回 CheckpointTuple)
```

#### 查看 thread 历史

```python
config = {"configurable": {"thread_id": "1"}}
list(graph.get_state_history(config))   # Graph API, 最新在前
list(checkpointer.list(config))         # Checkpointer API
```

#### 删除某个 thread 的所有 checkpoints

```python
thread_id = "1"
checkpointer.delete_thread(thread_id)
```

## 数据库管理

- 使用数据库支持的 persistence(Postgres、Redis、Oracle 等)存 short-term / long-term memory 前, 需运行迁移设置 schema。
- 惯例: 大多数库在 checkpointer 或 store 实例上定义 `setup()` 方法运行迁移。
- 应查阅所用 `BaseCheckpointSaver` / `BaseStore` 具体实现确认准确方法名与用法。
- 建议把迁移作为专门的部署步骤, 或确保服务器启动时运行。

## 易错点 / 混淆概念区分

- **short-term vs long-term**: short-term 用 checkpointer + `thread_id`, 只在同一 thread 内有效; long-term 用 store + namespace(常含 `user_id`), 跨 thread 共享。
- **调用必须传 `thread_id`**, 否则无法保存 / 恢复对话。
- **生产不要用 `InMemorySaver` / `InMemoryStore`**, 换数据库实现。
- **无数据库的 saver / store 首次使用需 `setup()`**; async 版本是 `asetup()` / `await setup()`。
- **subgraph checkpointer 只需在父 graph 编译时传入**, 会自动传播; 想让 subgraph 独立 checkpointing 用 `compile(checkpointer=True)`。
- **`RemoveMessage` 只在带 `add_messages` reducer 的通道上生效**(如 `MessagesState`)。
- **删除消息后要保证历史合法**(provider 对开头消息、tool call / tool 结果配对有要求)。
- **裁剪 vs 删除**: 裁剪只在发送给 LLM 前过滤, history 仍完整保存在 checkpoint; 删除是永久改 state。
- **store 写入时机**: 例子中只在用户说 "remember" 时才 `aput`, 避免无脑写爆 memory。
- **语义搜索需配置 embedding**(`index.embed` / `dims`); 托管环境还要在 `langgraph.json` 配置索引。

## 心智模型

> short-term memory = 当前这条对话线的"工作记忆"(checkpointer 保存, 有 context window 上限); long-term memory = 关于用户的"长期档案"(store 保存, 按 namespace 跨对话共享)。对话太长时, 用裁剪 / 删除 / 总结去压缩工作记忆, 但档案始终留着。
