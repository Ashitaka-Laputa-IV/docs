# LangGraph Subgraphs 速读笔记

> 来源: `src/oss/langgraph/use-subgraphs.mdx`

## 0. 一句话总结

subgraph 就是"被当作另一个 graph 的 node 来用的 graph"; 关键在于**两种通信方式** (调函数 vs 作 node) 和 **三种 persistence 模式** (`None` / `True` / `False`)。

## 1. 核心概念

subgraph 的适用场景:

- 构建 **multi-agent 系统**
- 在多个 graph 中**复用**一组 node
- **分散开发**: 各团队独立定义自己那部分; 只要遵守 subgraph 接口 (输入/输出 schema), 父 graph 无需了解其细节

## 2. 定义 subgraph 通信 (两种模式)

| 模式 | 适用场景 | state schema |
|------|----------|--------------|
| 在 node 内部调用 subgraph | 父子拥有**不同的 state schema** (无共享 key), 或需在两者间转换 | 自己写包装函数: 父 state → subgraph 输入, subgraph 输出 → 父 state |
| 把 subgraph 作为 node 添加 | 父子**共享 state key** (subgraph 读写同一通道) | 把编译好的 subgraph 直接传给 `add_node`, **无需包装函数** |

### 2.1 在 node 内部调用 subgraph (不同 schema)

```python
def call_subgraph(state: State):
    subgraph_output = subgraph.invoke({"bar": state["foo"]})  # 父 → 子
    return {"foo": subgraph_output["bar"]}                    # 子 → 父
```

- 典型用途: multi-agent 中给每个 agent 保留**私有 message 历史**。
- 子 graph 内部**看不到**父/祖父的 key, 反之亦然; 完全靠包装函数显式转换。
- 可支持**多级嵌套** (parent → child → grandchild), 逐层转换 schema。

### 2.2 把 subgraph 作为 node 添加 (共享 schema)

```python
builder.add_node("node_1", subgraph)   # 直接传编译好的 subgraph
```

- subgraph 自动读写父 graph 的 state 通道。
- subgraph 可以有**父 graph 看不到的私有 key** (如 `bar`), 同时向共享 key (`foo`) 写更新。
- 典型用途: multi-agent 中各 agent 通过共享的 `messages` key 通信。

## 3. Subgraph persistence (关键决策)

`.compile()` 的 `checkpointer` 参数控制内部数据在多次调用间如何处理。

| 模式 | `checkpointer=` | 行为 |
|------|-----------------|------|
| 按调用 (per-invocation) | `None` (默认) | 每次调用从头开始; 继承父 checkpointer 以在**单次调用内**支持 interrupts 与持久化执行 |
| 按 thread (per-thread) | `True` | state 在同一 thread 上**跨调用累积**, 每次从上次离开处继续 |
| 无状态 (stateless) | `False` | 完全不 checkpoint, 像普通函数调用; **无 interrupts, 无持久化执行** |

> 父 graph 必须用 checkpointer 编译, subgraph persistence 的各项功能 (interrupts、state inspection、按 thread memory) 才生效。

### 3.1 按调用 (默认, 推荐)

- 每次调用相互独立, subagent 不记得先前调用。
- 支持 interrupts、persistence、并行调用。
- 最适合 subagent 处理一次性请求的 multi-agent 系统。
- 多次调用同一 subgraph **安全** (每次调用获得自己的 checkpoint namespace)。
- state inspection: **仅当前调用有效** (interrupt 期间), 调用结束没有累积状态。

### 3.2 按 thread

- subagent 跨调用保留对话历史 (如逐步构建上下文的研究助理 / 追踪已编辑文件的编程助理)。
- **不支持并行 tool 调用**: LLM 可能并发多次调用同一个按 thread 的 tool → 两次调用写同一 namespace → checkpoint 冲突。用 `ToolCallLimitMiddleware(tool_name=..., run_limit=1)` 规避; 纯 `StateGraph` 需自行禁用并行或加锁。
- **namespace 隔离**: 多个**不同的**按 thread subgraph 各自需要独立存储, 否则互相覆盖。
  - 在 node 内调用 subgraph 时, namespace 按**调用顺序**分配 → 重排顺序会打乱 state。解决: 把每个 subagent 包进自己的 `StateGraph` 并用**唯一 node 名称**, 获得稳定唯一 namespace。
  - 作为 node 添加的 subgraph **自动**获得基于名称的 namespace, 无需包装。

### 3.3 无状态

```python
subgraph = subgraph_builder.compile(checkpointer=False)
```

- 像普通函数调用, 无 checkpoint 开销。
- **无法暂停/恢复**, 无法享受持久化执行; 进程中途崩溃需要从头重跑。

### 3.4 checkpointer 能力对照表

| 功能 | 按调用 (`None`) | 按 thread (`True`) | 无状态 (`False`) |
|------|---|---|---|
| Interrupts (HITL) | ✅ | ✅ | ❌ |
| 多轮 memory | ❌ | ✅ | ❌ |
| 多次调用 (不同的 subgraph) | ✅ | ⚠️ (需 namespace 隔离) | ✅ |
| 多次调用 (同一个 subgraph) | ✅ | ❌ (冲突) | ✅ |
| state inspection | ⚠️ (仅当前调用) | ✅ | ❌ |

## 4. 查看 subgraph state

- 启用 persistence 后, 用 `graph.get_state(config, subgraphs=True)` 检查。
- 无状态 (`checkpointer=False`) 下不保存 subgraph checkpoint, 无法获取。
- 按调用: 仅返回**当前调用**的 subgraph state。
- 按 thread: 返回该 thread 上**所有调用累积**的 state。

```python
subgraph_state = graph.get_state(config, subgraphs=True).tasks[0].state
```

> ⚠️ **前提**: LangGraph 必须能**静态发现**该 subgraph —— 即它被"作为 node 添加"或"在 node 内部调用"。若 subgraph 在 **tool 函数内部**或其他间接层被调用 (如 subagents 模式), **查看功能不生效**。但无论嵌套多深, **interrupts 仍会传播到顶层 graph**。

## 5. Stream subgraph 输出

推荐用 event streaming (`version="v3"`):

```python
stream = graph.stream_events({"foo": "foo"}, version="v3")
for subgraph in stream.subgraphs:
    print(subgraph.graph_name, subgraph.path)
    for snapshot in subgraph.values:
        print(subgraph.path, snapshot)
```

- `stream.subgraphs` 投影会发现每个嵌套 run, 暴露 `path` / `messages` / `values`, **无需解析 namespace 字符串**。
- 若需原始 protocol 事件, 可迭代 stream 并按 `event["method"]` 与 `event["params"]["namespace"]` 过滤 (用 `UpdatesTransformer`)。
- JS: `graph.streamEvents(..., { subgraphs: true, version: "v3" })`。
- namespace 空 (`[]`) = 父 graph 的事件; 非空 = 对应 subgraph 内部事件。

## 6. 易错点 / 混淆概念速查表

| 混淆点 | 正确理解 |
|--------|----------|
| 调函数 vs 作 node | 不同 schema → 调函数 (需转换); 共享 key → 作 node (直接传) |
| `checkpointer=True` 的含义 | 不是"开启 checkpoint", 而是"**拥有自己的按 thread 持久化历史**" |
| `checkpointer=None` | 继承父 checkpointer, 但**每次调用重置** |
| `checkpointer=False` | 完全无 checkpoint: 无 interrupt、无持久化执行 |
| 按 thread subgraph 并行调用 | ❌ 冲突; 用 `ToolCallLimitMiddleware` 限制 |
| 多个不同按 thread subgraph | 需 **namespace 隔离**: 包进带唯一 node 名的 `StateGraph` |
| 子 graph 能看到父 key 吗? | 调函数模式下不能 (schema 隔离), 需显式转换 |
| state inspection 何时失效 | subgraph 藏在 tool 函数/间接层里时 (非静态可发现) |
| 隐藏 subgraph 的 interrupt | 仍会传播到顶层 graph |
