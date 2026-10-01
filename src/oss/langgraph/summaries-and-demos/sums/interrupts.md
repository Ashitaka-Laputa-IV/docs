# LangGraph Interrupts 速读笔记

> 来源: `src/oss/langgraph/interrupts.mdx`

## 0. 一句话总结

`interrupt()` 让 graph 在 **node 内任意位置动态暂停**, 由 checkpointer 保存 state, 无限期等待外部输入; 你用 `Command(resume=...)` 恢复后, resume 值会成为 `interrupt()` 的**返回值**。

## 1. 核心概念

| 概念 | 说明 |
|------|------|
| 动态断点 | 与静态断点 (`interrupt_before` / `interrupt_after`) 不同, 可放在代码任意位置, 也可按业务逻辑条件触发 |
| 三件套 | ① checkpointer (生产用持久化) ② config 里的 `thread_id` ③ `interrupt()` 调用 |
| `thread_id` = 持久化游标 | 复用同一 ID → 恢复同一 checkpoint; 换新 ID → 开启全新 thread, state 为空 |
| 跨语言差异 | Python 用 `response_schema`, JS 用 `responseSchema`; Python 从 `langgraph.types` 导入, JS 从 `@langchain/langgraph` |

### 心智模型

- interrupt 的本质是**抛出一个特殊异常**来挂起执行; runtime 捕获它并保存 state。
- 恢复时 **node 从头重跑**, 而不是从 `interrupt()` 那一行继续。这是理解所有"规则/坑"的总钥匙。
- `thread_id` 就是你的"存档槽", checkpointer 就是存档本身。

## 2. `interrupt()` 执行时发生了什么

1. graph 执行被挂起, 停在调用 `interrupt` 的确切位置。
2. state 被 checkpointer 保存 (生产环境应为持久化 checkpointer)。
3. value 返回给调用方: `invoke()` 时在 `result["__interrupt__"]`; event streaming 时在 `stream.interrupts`。payload 必须是 **JSON 可序列化**的值 (字符串、对象、数组等)。
4. graph 无限期等待, 直到你带响应恢复。
5. resume 值传回 node, 成为 `interrupt()` 的返回值。

## 3. 恢复 interrupts

```python
from langgraph.types import Command

config = {"configurable": {"thread_id": "thread-1"}}

# 首次运行: 命中 interrupt 并暂停
graph.invoke({"input": "data"}, config)

# 恢复: resume 值成为 interrupt() 的返回值
graph.invoke(Command(resume=True), config)
```

**关于恢复的要点**:

- 恢复必须用与中断时**相同的 thread ID**。
- `Command(resume=...)` 的值 → 成为 `interrupt()` 的返回值。
- 恢复时 node 从**开头**重跑, `interrupt()` 之前的代码会**再次执行**。
- resume 值可以是任意 JSON 可序列化值; 指定 `response_schema` 时受校验约束。

### 获取 interrupt payload 的两种方式

| API | 读取方式 |
|-----|----------|
| `graph.invoke(...)` | `result["__interrupt__"]` |
| `graph.stream_events(..., version="v3")` | `stream.interrupts`, `stream.interrupted` |

> ⚠️ **最重要的坑**: `Command(resume=...)` 是**唯一**被设计为 `invoke()` / `stream()` 输入的 `Command` 用法。`update` / `goto` / `graph` 这些参数只用于**从 node 函数返回**。不要把 `Command(update=...)` 当输入来继续多轮对话 —— 那应该传一个普通 input dict。

## 4. 定义 interrupt response schema

- 作用: 描述恢复时预期输入的格式, 客户端据此渲染**带类型的输入表单**。
- 版本要求: Python `langgraph>=1.2.12`; JS `@langchain/langgraph>=1.4.16`。
- 可传入: Pydantic model 类 / `typing_extensions.TypedDict` / dataclass (Python); Zod schema (JS)。
- LangGraph 会把它转成 JSON Schema, 放在 `Interrupt.response_schema` 中, 与 `value` payload 分开。
- 有类型 schema 时 `interrupt()` 返回**校验后的对象** (Pydantic 实例 / dict / dataclass 实例), 会应用校验与强制转换。无效输入抛 `pydantic.ValidationError` (JS 为 `ZodError`), 可用**同一 thread ID** 通过修正后的 `Command(resume=...)` 重试。
- 传 **JSON Schema 字典**时: 原样暴露, **不校验**。
- 省略 `response_schema`: 值为 `None` (JS 无该字段), resume 值无校验直接通过。
- Studio 会把它渲染为带类型的输入字段而非 JSON 编辑器。

## 5. 常见模式

| 模式 | 用途 |
|------|------|
| 审批/拒绝 | 关键操作 (API 调用、数据库变更、金融交易) 前暂停 |
| 处理多个 interrupts | 单次调用内恢复多个 interrupt, 按 ID 配对 |
| 审查并编辑 state | 继续前让人修改 LLM 输出或 tool 调用 |
| Tool 中的 interrupts | tool 执行前暂停, 执行前审查/编辑 |
| 校验人工输入 | 进入下一步前校验输入, 无效则重新提示 |

### 5.1 通过 streaming 处理 HITL (推荐交互式做法)

在循环中用 `graph.stream_events(..., version="v3")` 直到 run 结束:

- `stream.messages`: 逐 token 的 AI 响应 (遍历 `message.text` 取 token delta); 嵌套 subgraph 从 `stream.subgraphs[*].messages` 读。
- `stream.values`: 每一步之后的完整 state snapshot。
- `stream.interrupted` / `stream.interrupts`: 每次都检查 graph 是否暂停, 并读 payload。
- `Command(resume=...)` 作为下一次 `stream_events` 的输入, 循环直到不再 interrupt。

### 5.2 处理多个 interrupts

并行分支同时 interrupt 时 (扇出到多个各自 `interrupt()` 的 node), 需要**一次恢复多个**。做法: 把每个 interrupt 的 **ID 映射到 resume 值** 的字典作为 resume 值传入。

```python
resume_map = {i.id: f"answer for {i.value}" for i in stream.interrupts}
graph.invoke(Command(resume=resume_map), config)
```

> 单个 resume 值只对应单个 interrupt; 多 interrupt 必须用 `{id: value}` 映射, 否则无法配对。

### 5.3 审批或拒绝

```python
def approval_node(state) -> Command[Literal["proceed", "cancel"]]:
    is_approved = interrupt({"question": "Do you want to proceed?", "details": state["action_details"]})
    return Command(goto="proceed") if is_approved else Command(goto="cancel")
```

恢复时传 `True` 批准 / `False` 拒绝。返回类型标注 `Command[Literal[...]]` 便于路由与类型检查。

### 5.4 审查并编辑 state

`interrupt()` 传入待审内容, 恢复时传编辑后的值, node 用返回值覆盖 state。

### 5.5 Tool 中的 interrupts

把 `interrupt()` 放进 tool 函数, 每次该 tool 被调用时暂停等待审批; resume 值可**覆盖 tool 入参**后再执行。适合希望审批逻辑与 tool 一起复用、可被 LLM 自然调用的场景。

### 5.6 校验人工输入 (重点)

✅ **正确模式**: 

1. 把重新提示的问题存入 state (如 `pending_question`)。
2. node 中**恰好调用一次** `interrupt()`, 传入来自 state 的当前问题。
3. 无效则返回更新后的 `pending_question`。
4. 用 `add_conditional_edges` **回环到该 node**, 直到收集到有效值。

于是每次恢复恰好调用一次 node、运行一次 `interrupt()`、然后退出, 循环体内代码不会重复执行。

> ⚠️ **绝对不要**在单个 node 内写 `while True` + `interrupt()` 循环。因为恢复时 node 从头重跑, 每次恢复都会**重放之前所有迭代**: 第 1 次恢复重放 1 次, 第 2 次重放 2 次 …… 循环体代码被**指数级**重复执行。

## 6. Interrupts 的规则 (坑清单)

### 6.1 不要用 try/except 包裹 `interrupt()` 调用

`interrupt` 靠抛异常暂停; 裸 `try/except Exception` 会把它吞掉, interrupt 无法传回 graph。

- ✅ 把 `interrupt()` 与易错代码**分开**
- ✅ 如必须捕获, 用**具体异常类型** (不会命中 interrupt 异常)
- 🔴 不要用裸 `try/except` 包住 `interrupt()`

### 6.2 不要在 node 内重排 `interrupt()` 调用

每个 node 的执行 task 维护一个**专属 resume 值列表**, 匹配**严格按索引**, 因此 node 内 interrupt 调用**顺序**至关重要。

- ✅ 各次执行中 interrupt 调用顺序保持一致
- 🔴 不要有条件地跳过 `interrupt()` (顺序变化 → 索引错配)
- 🔴 不要用非确定逻辑循环 `interrupt()` (含 `while True` 校验循环); 改用 conditional edge

### 6.3 不要在 `interrupt()` 中返回复杂值

取决于 checkpointer, 复杂值可能无法序列化。

- ✅ 简单 JSON 可序列化类型; 值为简单类型的 dict/对象
- 🔴 不要传函数、类实例或其他复杂对象 (会失败)

### 6.4 `interrupt()` 之前的副作用必须幂等

因为 node 会重跑, `interrupt()` **之前**的副作用会被多次执行。

- ✅ 用幂等操作 (如 `upsert`)
- ✅ 把副作用放在 `interrupt()` **之后**
- ✅ 尽量把副作用拆分到**单独的 node**
- 🔴 不要在 `interrupt()` 前创建新记录 / 追加列表 (恢复时产生重复)

## 7. 与"作为函数调用的 subgraph"配合

在 node 内调用 subgraph 并触发 interrupt 时:

- **父 graph** 从调用该 subgraph 的**那个 node 的开头**恢复。
- **subgraph** 也从调用 `interrupt()` 的那个 node 的开头恢复。
- 即两层 node 都会重跑, 各自 `interrupt()` 之前的代码都会再次执行。

## 8. 用 interrupts 调试

- 静态断点: 编译时传 `interrupt_before` / `interrupt_after` (JS: `interruptBefore` / `interruptAfter`), 可在确定位置 (node 之前/之后) 暂停, 一个 node 一个 node 地单步。
- 也可在**运行时**通过 `graph.invoke(..., interrupt_before=[...])` 传入, 每次调用可改。
- 恢复方式: `graph.invoke(None, config=config)` 运行到下一个断点。
- 断点需要 checkpointer。
- 🔴 静态中断**不**推荐用于 HITL workflow, 请改用 `interrupt()` 函数。
- 可在 LangSmith Studio UI 中设置静态中断并检查 state。

## 9. 易错点 / 混淆概念速查表

| 混淆点 | 正确理解 |
|--------|----------|
| `interrupt()` vs 静态 interrupt | `interrupt()` 动态、可条件触发; 静态 `interrupt_before/after` 只在编译/调用时按 node 固定位置触发, 调试用 |
| `Command(resume=...)` vs `Command(update/goto=...)` | 只有 `resume` 可作为 **graph 输入**; 其余用于**从 node 返回** |
| 恢复是否从断点续行? | 否, node **从头重跑**, 断点前代码再次执行 |
| resume 后 interrupt 返回什么? | 就是 `Command(resume=...)` 传入的值 (有 schema 时是校验后的对象) |
| 单值 resume 恢复多 interrupt? | 不行, 必须用 `{interrupt_id: value}` 映射 |
| 校验循环怎么写? | 一次 `interrupt()` + conditional edge 回环, 绝不用 `while True` |
| 多 interrupt 顺序 | 严格按索引匹配, 顺序必须稳定 |
