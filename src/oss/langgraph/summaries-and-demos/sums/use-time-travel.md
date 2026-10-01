# LangGraph Time Travel 速读笔记

> 来源: `src/oss/langgraph/use-time-travel.mdx`

## 0. 一句话总结

Time travel 通过 checkpoint 实现: **重放 (replay)** = 从旧 checkpoint 重跑; **分叉 (fork)** = 先 `update_state` 改过去的 state, 再从该点重跑, 从而探索替代路径。

## 1. 核心概念

| 概念 | 说明 |
|------|------|
| Replay (重放) | 从**先前 checkpoint 的 config** 调用 graph, 重跑其后的 node |
| Fork (分叉) | 在先前 checkpoint 上调用 `update_state` 创建新分支, 再用 `None` 调用 `invoke` 继续 |
| Checkpoint | graph state 的历史快照, 是 time travel 的基础 |
| checkpoint 之前的 node | **不会**重新执行 (结果已保存) |
| checkpoint 之后的 node | **会**重新执行 (含 LLM 调用、API 请求、interrupts) |

### 心智模型

- checkpoint 是"时间轴上的存档点"; replay 是"回到该存档重玩", fork 是"回到该存档并先改装备再重玩"。
- `get_state_history(config)` 返回**逆时间序** (最新在前) 的 state 列表, 用 `state.next` 判断"这个 checkpoint 之后要做哪个 node"。

## 2. 重放 (Replay)

```python
# 1. 运行 graph
config = {"configurable": {"thread_id": str(uuid7())}}
graph.invoke({}, config)

# 2. 找到要重放的 checkpoint (history 为逆时间序)
history = list(graph.get_state_history(config))
before_joke = next(s for s in history if s.next == ("write_joke",))

# 3. 从该 checkpoint 重放
graph.invoke(None, before_joke.config)
# write_joke 重新执行, generate_topic 不执行
```

> ⚠️ 重放是**真正重新执行 node**, 不是读缓存。LLM 调用、API 请求、interrupts 会再次触发, 可能返回不同结果。
> ⚠️ 从**最终 checkpoint** (没有 `next` node) 重放是**空操作**。

关键判定: `s.next == ("write_joke",)` 表示"该 checkpoint 之后即将执行 write_joke", 即它是 write_joke 之前的存档。

## 3. 分叉 (Fork)

```python
history = list(graph.get_state_history(config))
before_joke = next(s for s in history if s.next == ("write_joke",))

# 分叉: 修改 state
fork_config = graph.update_state(before_joke.config, values={"topic": "chickens"})

# 从分叉点继续
fork_result = graph.invoke(None, fork_config)
print(fork_result["joke"])  # 关于 chickens 的笑话, 而非 socks
```

> ⚠️ `update_state` **不会回滚 thread**。它创建一个**从指定点分出的新 checkpoint**, 原始执行历史保持完整。

## 4. 从特定 node 分叉 (`as_node`)

`update_state` 时, 值会使用**指定 node 的 writer** 来应用 (包括 reducers)。checkpoint 记录"是该 node 产生了该更新", 执行从该 node 的**后继节点**恢复。

- 默认: LangGraph 从 checkpoint 版本历史**推断** `as_node`; 从特定 checkpoint 分叉时这种推断几乎总是正确。
- 需**显式指定** `as_node` 的场景:
  1. **并行分支**: 多个 node 在同一步骤更新 state, 无法确定谁是最后一个 → `InvalidUpdateError`。
  2. **没有执行历史**: 在全新 thread 上设置 state (常见于测试)。
  3. **跳过 node**: 把 `as_node` 设为更靠后的 node, 让 graph 认为该 node 已运行过。

```python
fork_config = graph.update_state(
    before_joke.config,
    values={"topic": "chickens"},
    as_node="generate_topic",   # 装作是 generate_topic 产出的更新
)
# 执行从 generate_topic 的后继 write_joke 恢复
```

## 5. Time travel 与 Interrupts

> ⚠️ 若 graph 使用 `interrupt()` 做 HITL, 那么 time travel 期间 **interrupt 总会被重新触发**。包含该 interrupt 的 node 会重跑, `interrupt()` 再次暂停等待**新的** `Command(resume=...)`。

```python
# graph: ask_human -> final_step
graph.invoke({"value": []}, config)              # 命中 interrupt
graph.invoke(Command(resume="Alice"), config)    # 恢复正常

# 从 ask_human 之前重放
before_ask = [s for s in history if s.next == ("ask_human",)][-1]
graph.invoke(None, before_ask.config)            # 又暂停在 interrupt

# 从 ask_human 之前分叉
fork_config = graph.update_state(before_ask.config, {"value": ["forked"]})
graph.invoke(None, fork_config)                  # 又暂停在 interrupt

# 用不同答案恢复分叉出的 interrupt
graph.invoke(Command(resume="Bob"), fork_config)
# 结果: {"value": ["forked", "Hello, Bob!", "Done"]}
```

### 多个 interrupts

多步表单场景可从**两个 interrupt 之间**分叉, 从而改后续答案而不重问先前问题。用 `s.next == ("ask_age",)` 定位"ask_name 之后、ask_age 之前"的 checkpoint。

## 6. 对 Subgraphs 做 time travel

取决于 subgraph **是否拥有自己的 checkpointer**。

| 模式 | 编译方式 | 粒度 |
|------|----------|------|
| 继承的 checkpointer (默认) | `.compile()` | 父级把整个 subgraph 视为**单个 super-step**, 只有一个父级 checkpoint; 无法在 subgraph 内部 node 之间 time travel |
| Subgraph 自己的 checkpointer | `.compile(checkpointer=True)` | 在 subgraph **内部**每一步创建 checkpoint, 可从内部某点 (如两个 interrupt 之间) time travel |

### 继承的 checkpointer (默认)

- 父级视整个 subgraph 为一个 super-step。
- 从 subgraph **之前** time travel 会**从头重新执行整个 subgraph**。
- 无法到达 subgraph 内 node 之间的点。

### Subgraph 自己的 checkpointer

```python
parent_state = graph.get_state(config, subgraphs=True)
sub_config = parent_state.tasks[0].state.config   # subgraph 自己的 checkpoint config

fork_config = graph.update_state(sub_config, {"value": ["forked"]})
graph.invoke(None, fork_config)
# step_b 重新执行, step_a 的结果被保留
```

关键 API: `graph.get_state(config, subgraphs=True)` 访问 subgraph 自己的 checkpoint config (via `tasks[0].state.config`)。

## 7. 易错点 / 混淆概念速查表

| 混淆点 | 正确理解 |
|--------|----------|
| Replay 是读缓存吗? | 否, 是**重新执行** node; LLM/API/interrupt 会再次触发, 结果可能不同 |
| 从哪个 checkpoint 重放? | `s.next` 指向"接下来要执行的 node", 选 `next == ("write_joke",)` 即 write_joke 之前的存档 |
| `update_state` 会回滚吗? | 不会, 只**追加**一条从该点分出的新 checkpoint, 旧历史完整保留 |
| `get_state_history` 顺序 | **逆时间序**, 最新的在最前 |
| 何时需要显式 `as_node`? | 并行分支歧义 / 全新 thread 无历史 / 想跳过 node |
| Fork 后如何继续? | `graph.invoke(None, fork_config)` |
| time travel 遇 interrupt | 一律**重新触发**, 需提供新的 `Command(resume=...)` |
| subgraph time travel 粒度 | 默认 (继承) 只能从父级整块; `checkpointer=True` 才能到内部点 |
| 从最终 checkpoint 重放 | 空操作 |
