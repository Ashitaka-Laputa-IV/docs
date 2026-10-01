# Streaming（stream-mode API）速读笔记

> 源文件: `src/oss/langgraph/streaming.mdx`
> 主题: LangGraph 通过 `stream_mode` 暴露 graph 执行的底层 streaming API。

## 0. 定位与选型

- 本页是 **stream-mode API**：用 `stream_mode` 把 graph 执行以七种模式暴露：`updates / values / messages / custom / checkpoints / tasks / debug`。
- 适用场景：需要直接访问 graph-runtime 事件，或需要某个特定 stream mode 的原始输出。
- 新应用推荐 **事件 streaming**（见 `event-streaming` 笔记）：类型化投影 API，每个投影（messages、values、subgraphs、output）各有独立迭代器，不必按 `stream_mode` 分块做分支判断。
- 入口方法：`graph.stream(...)`（同步）/ `graph.astream(...)`（async），返回迭代器。
- **强烈建议统一加 `version="v2"`**（需 LangGraph 1.1+），本页示例均使用它。

## 1. 快速开始

```python
for chunk in graph.stream(
    {"topic": "ice cream"},
    stream_mode=["updates", "custom"],  # 可传单个字符串或列表
    version="v2",                        # 统一输出格式
):
    if chunk["type"] == "updates":
        for node_name, state in chunk["data"].items():
            print(f"Node {node_name} updated: {state}")
    elif chunk["type"] == "custom":
        print(f"Status: {chunk['data']['status']}")
```

自定义数据由 node 内的 `get_stream_writer()` 发出：

```python
from langgraph.config import get_stream_writer

def generate_joke(state):
    writer = get_stream_writer()
    writer({"status": "thinking of a joke..."})
    return {"joke": "..."}
```

## 2. v2 输出格式（核心心智模型）

传入 `version="v2"` 后，**每个 chunk 都是同一个形状的 `StreamPart` dict**，与 stream mode 数量、subgraph 设置都无关：

```python
{
    "type": "values" | "updates" | "messages" | "custom" | "checkpoints" | "tasks" | "debug",
    "ns": (),          # namespace 元组，subgraph 事件才非空
    "data": ...,       # 实际 payload，类型随 mode 变化
}
```

- 每种 mode 有对应 `TypedDict`：`ValuesStreamPart`、`UpdatesStreamPart`、`MessagesStreamPart`、`CustomStreamPart`、`CheckpointStreamPart`、`TasksStreamPart`、`DebugStreamPart`，均可从 `langgraph.types` 导入。
- 联合类型 `StreamPart` 是基于 `part["type"]` 的**不相交联合**，因此 `if part["type"] == "values":` 之后编辑器/类型检查器能正确收窄 `part["data"]` 的类型。

v1 vs v2 对比：

```python
# v2（新）
for chunk in graph.stream(inputs, stream_mode="updates", version="v2"):
    print(chunk["type"])  # "updates"
    print(chunk["ns"])    # ()
    print(chunk["data"])  # {"node_name": {"key": "value"}}

# v1（当前默认）
for chunk in graph.stream(inputs, stream_mode="updates"):
    print(chunk)  # {"node_name": {"key": "value"}}
```

v2 多 mode 类型收窄示例：

```python
for part in graph.stream({"topic": "ice cream"},
                         stream_mode=["values", "updates", "messages", "custom"],
                         version="v2"):
    if part["type"] == "values":
        print(f"State: topic={part['data']['topic']}")
    elif part["type"] == "updates":
        for node_name, state in part["data"].items():
            print(f"Node `{node_name}` updated: {state}")
    elif part["type"] == "messages":
        msg, metadata = part["data"]
        print(msg.content, end="", flush=True)
    elif part["type"] == "custom":
        print(f"Progress: {part['data']['progress']}%")
```

## 3. stream mode 总览

| Mode | Python 类型 | 说明 |
| :--- | :--- | :--- |
| `values` | `ValuesStreamPart` | 每一步之后的**完整 state**。 |
| `updates` | `UpdatesStreamPart` | 每一步之后的 state **增量更新**；同一步中多个更新会分别 stream。 |
| `messages` | `MessagesStreamPart` | 来自 LLM 调用的 `(LLM token, metadata)` 二元组。 |
| `custom` | `CustomStreamPart` | node 通过 `get_stream_writer()` 发出的自定义数据。 |
| `checkpoints` | `CheckpointStreamPart` | checkpoint 事件（格式同 `get_state()`）。**需要 checkpointer**。 |
| `tasks` | `TasksStreamPart` | task 启动/完成事件，含结果与错误。**需要 checkpointer**。 |
| `debug` | `DebugStreamPart` | 所有可用信息 = `checkpoints` + `tasks` + 额外 metadata。 |

> JS 侧独有 `tools` mode（tool-call 生命周期事件）；Python 侧 tool 进度用 `custom` 实现。

## 4. Graph state：updates vs values

```python
* updates: 每步之后 stream state 的「更新」（只含变化的 key）。
* values : 每步之后 stream state 的「完整值」（整个快照）。
```

同一个双节点 graph（`refine_topic` → `generate_joke`）：

```python
# updates：每个 node 各自一条
for chunk in graph.stream({"topic": "ice cream"}, stream_mode="updates", version="v2"):
    if chunk["type"] == "updates":
        for node_name, state in chunk["data"].items():
            print(f"Node `{node_name}` updated: {state}")
# Node `refine_topic` updated: {'topic': 'ice cream and cats'}
# Node `generate_joke` updated: {'joke': 'This is a joke about ice cream and cats'}

# values：每步一个完整快照（含尚未填充的 key）
for chunk in graph.stream({"topic": "ice cream"}, stream_mode="values", version="v2"):
    if chunk["type"] == "values":
        print(f"topic: {chunk['data']['topic']}, joke: {chunk['data']['joke']}")
# topic: ice cream, joke:
# topic: ice cream and cats, joke:
# topic: ice cream and cats, joke: This is a joke about ice cream and cats
```

心智模型：`values` 第 0 条是**输入初值**，之后每步是合并后的完整 state；`updates` 只给增量，消费方需自行 merge。

## 5. LLM token：messages mode

- stream 输出是元组 `(message_chunk, metadata)`：
  - `message_chunk`：LLM 的 token / 消息片段。
  - `metadata`：包含 graph node、LLM 调用等详细信息的 dict。
- **即使用 `model.invoke()` 而非 `.stream()`，message 事件仍会被发出**（LangGraph 内部仍按 token 回调）。

```python
model = init_chat_model(model="gpt-5.4-mini")

def call_model(state):
    model_response = model.invoke([{"role": "user", "content": f"Generate a joke about {state.topic}"}])
    return {"joke": model_response.content}

for chunk in graph.stream({"topic": "ice cream"}, stream_mode="messages", version="v2"):
    if chunk["type"] == "messages":
        message_chunk, metadata = chunk["data"]
        if message_chunk.content:
            print(message_chunk.content, end="|", flush=True)
```

若 LLM 不是 LangChain integration，可用 `custom` mode 自行 stream（见第 9 节）。

### 5.1 按 LLM 调用过滤（tags）

给 model 打 `tags`，再按 `metadata["tags"]` 过滤：

```python
model_1 = init_chat_model(model="gpt-5.4-mini", tags=["joke"])
model_2 = init_chat_model(model="gpt-5.4-mini", tags=["poem"])

async for chunk in graph.astream({"topic": "cats"}, stream_mode="messages", version="v2"):
    if chunk["type"] == "messages":
        msg, metadata = chunk["data"]
        if metadata["tags"] == ["joke"]:   # Python：精确匹配列表
            print(msg.content, end="|", flush=True)
```

### 5.2 从 stream 中省略消息（nostream tag）

- 给 LLM 调用打 `nostream` tag → 调用仍会运行并产生输出，但 token **不会**在 `messages` mode 中发出。
- 用途：内部处理用的结构化输出不暴露给客户端；或用自定义 channel stream 同一内容、避免重复。
- 具体用法见源码 snippets `snippets/code-samples/nostream-tag-py.mdx`。

### 5.3 按 node 过滤

按 metadata 里的 `langgraph_node` 字段过滤：

```python
for chunk in graph.stream(inputs, stream_mode="messages", version="v2"):
    if chunk["type"] == "messages":
        msg, metadata = chunk["data"]
        if msg.content and metadata["langgraph_node"] == "write_poem":
            print(msg.content, end="|", flush=True)
```

## 6. 自定义数据（custom mode）

步骤：

1. 用 `get_stream_writer()` 获取 writer 并发出自定义数据。
2. 调用 `.stream()`/`.astream()` 时设置 `stream_mode="custom"`（或与其他 mode 组合，但**至少要有一个是 `custom`**）。

node 内：

```python
from langgraph.config import get_stream_writer

def node(state):
    writer = get_stream_writer()
    writer({"custom_key": "Generating custom data inside node"})
    return {"answer": "some data"}

for chunk in graph.stream(inputs, stream_mode="custom", version="v2"):
    if chunk["type"] == "custom":
        print(f"Custom event: {chunk['data']['custom_key']}")
```

tool 内（同样用 `get_stream_writer()`）：

```python
@tool
def query_database(query: str) -> str:
    """Query the database."""
    writer = get_stream_writer()
    writer({"data": "Retrieved 0/100 records", "type": "progress"})
    writer({"data": "Retrieved 100/100 records", "type": "progress"})
    return "some-answer"
```

## 7. Subgraph 输出

- 在父 graph 的 `.stream()` 设置 `subgraphs=True`，父 graph 与任意 subgraph 的输出都会 stream 出来。
- v2 下 subgraph 事件同样是 `StreamPart`，用 `chunk["ns"]` 判断来源：
  - `()` → 根 graph。
  - `("node_name:<task_id>",)` → 某个 subgraph。
- v1 下输出是 `(namespace, data)` 元组，即 `("parent_node:<task_id>", "child_node:<task_id>")`。

```python
for chunk in graph.stream({"foo": "foo"}, subgraphs=True,
                          stream_mode="updates", version="v2"):
    if chunk["type"] == "updates":
        if chunk["ns"]:
            print(f"Subgraph {chunk['ns']}: {chunk['data']}")
        else:
            print(f"Root: {chunk['data']}")
```

输出示意：

```text
Root: {'node_1': {'foo': 'hi! foo'}}
Subgraph ('node_2:dfdd...',): {'subgraph_node_1': {'bar': 'bar'}}
Subgraph ('node_2:dfdd...',): {'subgraph_node_2': {'foo': 'hi! foobar'}}
Root: {'node_2': {'foo': 'hi! foobar'}}
```

**高频坑**：`subgraphs=True` 适用于所有 mode，包括 `messages`。像 `create_agent(...)` 这样的 builder 返回的是**已编译 graph**，把它 `add_node` 后就变成 subgraph——此时若不设 `subgraphs=True`，父 graph 的 `stream_mode="messages"` **收不到内部 agent 的 LLM token**。直接调用 `agent.stream(...)` 则能收到，所以该问题常常只在「包装之后」才暴露。

```python
graph = (
    StateGraph(State)
    .add_node("agent", create_agent(model, tools, state_schema=State))
    .add_edge(START, "agent")
    .add_edge("agent", END)
    .compile()
)
for chunk in graph.stream(inputs, stream_mode="messages", subgraphs=True, version="v2"):
    print(chunk["type"], chunk["ns"], chunk["data"])
```

## 8. Checkpoint / Task / Debug

三者都需要（checkpoint/task）checkpointer：

```python
from langgraph.checkpoint.memory import MemorySaver

graph = StateGraph(State)... .compile(checkpointer=MemorySaver())
config = {"configurable": {"thread_id": "1"}}

# checkpoints：每个 checkpoint 事件格式同 get_state()
for chunk in graph.stream({"topic": "ice cream"}, config=config,
                          stream_mode="checkpoints", version="v2"):
    if chunk["type"] == "checkpoints":
        print(chunk["data"])

# tasks：node 启动/完成事件，含结果与错误
for chunk in graph.stream({"topic": "ice cream"}, config=config,
                          stream_mode="tasks", version="v2"):
    if chunk["type"] == "tasks":
        print(chunk["data"])

# debug：尽可能多的信息（= checkpoints + tasks + 额外 metadata）
for chunk in graph.stream({"topic": "ice cream"}, stream_mode="debug", version="v2"):
    if chunk["type"] == "debug":
        print(chunk["data"])
```

> `debug` = `checkpoints` + `tasks` + 额外 metadata；只需要子集时直接用更窄的 mode。

## 9. 同时使用多个 mode

- 传列表即可。
- **v2**：每个 chunk 都是 `StreamPart`，用 `chunk["type"]` 区分。
- **v1**：输出是 `(mode, data)` 元组。

```python
# v2
for chunk in graph.stream(inputs, stream_mode=["updates", "custom"], version="v2"):
    if chunk["type"] == "updates":
        for node_name, state in chunk["data"].items():
            print(f"Node `{node_name}` updated: {state}")
    elif chunk["type"] == "custom":
        print(f"Custom event: {chunk['data']}")

# v1
for mode, chunk in graph.stream(inputs, stream_mode=["updates", "custom"]):
    print(chunk)
```

## 10. 高级

### 10.1 与任意 LLM 一起使用（custom mode）

即使 LLM API **没有**实现 LangChain chat model 接口，也能用 `custom` mode 把它的 token stream 出来：

```python
from langgraph.config import get_stream_writer

def call_arbitrary_model(state):
    writer = get_stream_writer()
    for chunk in your_custom_streaming_client(state["topic"]):
        writer({"custom_llm_chunk": chunk})
    return {"result": "completed"}

for chunk in graph.stream({"topic": "cats"}, stream_mode="custom", version="v2"):
    if chunk["type"] == "custom":
        print(chunk["data"])
```

典型做法（原始 OpenAI SDK）：自定义 `stream_tokens` 异步生成器逐 token `yield`，tool/node 内用 `writer(msg_chunk)` 转发，消费侧读 `chunk["data"]["content"]`。

### 10.2 为特定 chat model 禁用 streaming

混用支持/不支持 streaming 的 model 时，给不支持的显式关闭：

```python
# init_chat_model
model = init_chat_model("claude-sonnet-4-6", streaming=False)
# 或用 chat model 接口
model = ChatOpenAI(model="gpt-5.5", streaming=False)
```

> 并非所有 integration 都支持 `streaming` 参数；不支持时改用所有 chat model 基类都提供的 `disable_streaming=True`。

### 10.3 Python < 3.11 的 async（两个硬限制）

Python < 3.11 的 asyncio task 不支持 `context` 参数，导致：

1. **必须**把 `RunnableConfig` 显式传给 async LLM 调用（如 `ainvoke(..., config)`），否则 callback 不会传播、无法收到 token。
2. **不能**在 async node/tool 中用 `get_stream_writer()`，必须把 `writer` 作为参数直接传入。

```python
# 1) 手动传 config
async def call_model(state, config):
    joke_response = await model.ainvoke(
        [{"role": "user", "content": f"Write a joke about {state['topic']}"}],
        config,   # 显式传递，保证 context 传播
    )
    return {"joke": joke_response.content}

# 2) writer 作参数
from langgraph.types import StreamWriter

async def generate_joke(state: State, writer: StreamWriter):
    writer({"custom_key": "Streaming custom data while generating a joke"})
    return {"joke": f"This is a joke about {state['topic']}"}
```

### 10.4 迁移到 v2

| 场景 | v1（默认） | v2（`version="v2"`） |
|---|---|---|
| 单一 stream mode | 原始数据 dict | 带 `type`/`ns`/`data` 的 `StreamPart` |
| 多个 stream mode | `(mode, data)` 元组 | 同一 `StreamPart`，按 `chunk["type"]` 过滤 |
| Subgraph streaming | `(namespace, data)` 元组 | 同一 `StreamPart`，检查 `chunk["ns"]` |
| 多个 mode + subgraph | `(namespace, mode, data)` 三元组 | 同一 `StreamPart` |
| `invoke()` 返回类型 | 普通 dict（state） | 带 `.value` 与 `.interrupts` 的 `GraphOutput` |
| Interrupt 位置（stream） | state 中的 `__interrupt__` 键 | `values` stream part 上的 `interrupts` 字段 |
| Interrupt 位置（invoke） | result 中的 `__interrupt__` 键 | `GraphOutput.interrupts` |
| Pydantic/dataclass 输出 | 返回普通 dict | 强制转换为 model/dataclass 实例 |

**v2 invoke 格式**：

```python
from langgraph.types import GraphOutput

result = graph.invoke(inputs, version="v2")
assert isinstance(result, GraphOutput)
result.value       # 你的输出（dict / Pydantic / dataclass）
result.interrupts  # tuple[Interrupt, ...]，无中断时为空
```

- 使用非默认 `"values"` mode 时，`invoke(..., stream_mode="updates", version="v2")` 返回 `list[StreamPart]` 而非 `list[tuple]`。
- 对 `GraphOutput` 的 dict 风格访问（`result["key"]`、`"key" in result`、`result["__interrupt__"]`）仍可用但**已弃用**，未来会移除；请迁移到 `result.value` / `result.interrupts`。

**Pydantic 与 dataclass 强制转换**：state 是 Pydantic model 或 dataclass 时，v2 的 `values` mode 会把 `chunk["data"]` 转成正确类型实例：

```python
for chunk in graph.stream({"value": "x", "items": []}, stream_mode="values", version="v2"):
    print(type(chunk["data"]))  # <class 'MyState'>
```

## 11. 易错点 / 坑 / 概念区分

1. **v1 和 v2 输出格式完全不同**：忘了 `version="v2"` 时，多 mode 会得到 `(mode, data)` 元组、subgraph 会得到 `(namespace, data)`，而你写的是 `chunk["type"]` 就会报错。
2. **`updates` vs `values`**：`updates` 只含变化的 key 且同一 superstep 内多个更新会分别产出；`values` 是每步完整快照（首条是输入初值）。需要累加/覆盖语义时用 `values` 更省心。
3. **`messages` 与 `.invoke` 的误会**：即便 model 用 `.invoke` 调用，LangGraph 仍会发出 `messages` 事件（逐 token 回调）。
4. **subgraph token 丢失**：把 `create_agent(...)` 等已编译 graph 作为 node 时，必须在父 graph 加 `subgraphs=True`，否则 `messages` mode 收不到内部 LLM token（高频坑）。
5. **`checkpoints`/`tasks` 需要 checkpointer**，且要传带 `thread_id` 的 config；没有会报错或拿不到事件。
6. **`debug` 是超集**：它 = `checkpoints` + `tasks` + 额外 metadata，只在需要全集时用，否则用更窄的 mode 减负。
7. **`custom` mode 必须显式出现在 `stream_mode` 里**（组合时至少含一个 `"custom"`），否则 `writer()` 发出的数据收不到。
8. **Python < 3.11 async**：必须手动传 `config` 给 `ainvoke`，且不能用 `get_stream_writer()`（改用 `writer: StreamWriter` 参数）。
9. **按 tag 过滤的匹配方式**：Python 用 `metadata["tags"] == ["joke"]`（列表精确匹配）；若 model 有多个 tag 需注意。
10. **按 node 过滤**用 `metadata["langgraph_node"]`，不是 node 名直接当 key。
11. **`nostream` tag 只影响 `messages` mode 是否发出 token**，调用本身照常运行。
12. **禁用 streaming** 优先 `streaming=False`；integration 不支持该参数时退到 `disable_streaming=True`（基类通用）。

## 12. 一句话心智模型

> `stream_mode` 决定「看什么」（state 增量/全量、LLM token、自定义数据、checkpoint、task、debug），`version="v2"` 决定「怎么给」（统一 `StreamPart`：`type` + `ns` + `data`）；多个 mode 只是把多种视图混进同一条流，用 `chunk["type"]` 分流即可。
