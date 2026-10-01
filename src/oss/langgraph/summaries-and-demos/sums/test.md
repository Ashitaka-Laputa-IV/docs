# 测试 (Testing) — 速读笔记

源文件: `src/oss/langgraph/test.mdx`

## 核心概念

- 本页是 **LangGraph 专属**的测试模式, 针对**有自定义结构的 graph**。
- 若你刚入门、用的是 LangChain 内置 `create_agent`, 应看 LangChain 的测试指南 (本页面向自定义 graph)。
- 由于 agent 依赖 state, 实用模式是: **每次用到 graph 的测试前创建它, 并用全新的 checkpointer 实例编译** —— 保证测试间相互隔离。
- 三大测试模式:
  1. 端到端执行整个 graph (快速开始)
  2. 单独测试某个 node / edge
  3. 部分执行 (只测内部某一段路径)

## 关键步骤

### 前置条件
```bash
pip install -U pytest      # Python
npm install -D vitest       # JS
```

### 模式一: 快速开始 (端到端)
- 在测试内新建 checkpointer 并编译 graph, 用 `invoke` + `thread_id` 跑。
```python
def test_basic_agent_execution() -> None:
    checkpointer = MemorySaver()
    graph = create_graph()
    compiled_graph = graph.compile(checkpointer=checkpointer)
    result = compiled_graph.invoke(
        {"my_key": "initial_value"},
        config={"configurable": {"thread_id": "1"}}
    )
    assert result["my_key"] == "hello from node2"
```

### 模式二: 测试单个 node 与 edge
- 编译后的 graph 以 **`graph.nodes`** 暴露对每个单独 node 的引用, 可直接调用。
```python
result = compiled_graph.nodes["node1"].invoke({"my_key": "initial_value"})
assert result["my_key"] == "hello from node1"
```

### 模式三: 部分执行 (只跑内部一段)
- 适用场景: 不想端到端测试整个流程, 又不想改动 graph 结构。
- (另一种做法是把部分**重构为 subgraph**, 然后单独调用; 但若不想改结构, 就用下面的 persistence 技巧。)
- 步骤:
  1. 用 checkpointer 编译 agent (测试用内存 checkpointer `InMemorySaver` 即可)。
  2. 调用 `update_state`, 把 `as_node` 设为**想要开始测试的那个 node 之前**的 node 名。
  3. 用**同一个 thread_id** 调用 agent, 把 `interrupt_after` 设为**想要停止的那个 node** 名。
```python
def test_partial_execution_from_node2_to_node3() -> None:
    checkpointer = MemorySaver()
    graph = create_graph()
    compiled_graph = graph.compile(checkpointer=checkpointer)
    compiled_graph.update_state(
        config={"configurable": {"thread_id": "1"}},
        values={"my_key": "initial_value"},   # 模拟 node1 结束时传入 node2 的 state
        as_node="node1",                       # 假装这个 state 来自 node1 → 从 node2 继续
    )
    result = compiled_graph.invoke(
        None,                                  # 传 None 表示"恢复执行"
        config={"configurable": {"thread_id": "1"}},
        interrupt_after="node3",               # 到 node3 后停, node4 不跑
    )
    assert result["my_key"] == "hello from node3"
```

## 心智模型

- **隔离优先**: 每个测试自建 graph + 新 checkpointer, 避免测试间 state 污染。
- **三层粒度**: 整个 graph → 单个 node → 内部一段路径, 按需要选择。
- **部分执行借用 persistence**: `update_state(as_node=...)` 相当于"伪造一个中间 state", `interrupt_after=...` 相当于"在目标后设一个停靠点"。`as_node` 的语义是"这个 state 是由哪个 node 产生的", 因此执行会从**它之后**的 node 恢复。

## 易错点 / 注意事项

- **`graph.nodes[...]` 会绕过 checkpointer**: 直接调用单个 node 时, 编译时传入的 checkpointer 被忽略 (文档明确说明), 所以不能靠它测持久化行为。
- **`as_node` 要填目标节点的前一个节点**, 不是目标节点本身 —— 填错会导致起点不对。
- **`interrupt_after` 是"在该 node 之后停"**, 想让 node4 不跑就设成 `"node3"`。
- **恢复执行时 invoke 的第一个参数传 `None`**, 不是新 state; 传了别的会覆盖。
- `update_state` 与 `invoke` 必须用**同一个 `thread_id`**, 否则 state 对不上。
- `MemorySaver` (JS) / `InMemorySaver` (Python) 仅测试用; 生产要用真正的持久化 checkpointer。
- JS 端参数名不同: `asNode` / `interruptAfter` / `interruptBefore`; Python 用 `as_node` / `interrupt_after`。
