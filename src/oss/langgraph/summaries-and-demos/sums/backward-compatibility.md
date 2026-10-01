# 向后兼容性 —— 速读笔记

> 源文件: `src/oss/langgraph/backward-compatibility.mdx`
> 一句话: 生产环境更新 LangGraph graph 代码时, 如何不破坏正在进行的 run。

## 0. 核心前提 (为什么这很重要)

**关键事实**: LangGraph 会把**最新部署的 graph** 立即应用到**每一个** thread —— 无论是新 thread, 还是从 checkpoint 恢复的 thread。

对比: 传统 workflow 引擎会把一次 run **锁定**在它启动时的代码版本。

**推论:**
- 好处: bug 修复无需繁琐流程就能传播到进行中的对话与 agent。
- 代价: 你发布的**每一处改动**, 相对于现有 checkpoint 而言, **实质上都是一次"向后兼容的 API 变更"**。
- 所以: 必须仔细思考每处改动会如何与"在上一版代码下启动的 run"相互作用。

### 三类兼容性问题 (按遇到频率排序)

| # | 类型 | 频率 | 说明 | 适用 API |
|---|------|------|------|----------|
| 1 | **技术兼容性** | 最常见 | 新代码必须仍能针对现有 State 加载并执行 | 全部 |
| 2 | **业务兼容性** | 较少见 | 代码变了, 但现有 run 应继续遵循**旧业务逻辑** | 全部 |
| 3 | **非确定性** | 特殊 | 重放时结果不一致导致控制流漂移 | 仅 Functional API |

> 本文讨论的是"改动**超出** runtime 默认支持范围"时的应对模式。默认支持哪些拓扑/state 变更见 `graph 迁移` 文档。

---

## 1. 技术兼容性

### 核心概念
技术兼容性 ≈ 微服务中的 **API 破坏性变更**。这里的 "API" = **graph 代码** 与 **checkpointer 已持久化的数据**之间的契约。

恢复流程: thread 恢复时 → LangGraph 反序列化已保存的 state → **按名称**分派给某个 node → 期望 node 返回符合 state schema 的值。

### 常见的技术性破坏 (三个)

1. **重命名或删除某个 node**
   - 触发条件: thread 正停在该 node 处或即将进入 (例如停在 `interrupt` 处, 或经由一条已 checkpoint 但仍路由到旧名称的 conditional edge)。
   - 后果: 恢复时按保存的名称找不到该 node, run **失败**。
   - 原因: 恢复的**起点是"执行停止处所在 node 的开头"**, 缺失的 node 没有可恢复的起点。

2. **重命名或删除某个 State key**
   - 触发条件: 较旧 checkpoint 仍含该 key, 或下游 node 仍会读取它。

3. **收紧某个 State 字段**
   - 例: 把 `Optional` 改为必填、收窄类型、新增无默认值的必填字段。
   - 后果: 现有 checkpoint 无法满足新 schema。

### 重要澄清: 什么**不会**破坏
**edge 拓扑本身不会持久化到 checkpoint 中**。因此:
- 在**仍然存在的 node 之间**新增、删除或改接 edge → 对进行中的 thread **安全**。
- **唯一**会破坏"处于 interrupt 状态的 thread"的拓扑变更 = **重命名或删除某个 node**。

### 推荐的兼容模式 (Python)

```python
# 1) 新字段用 NotRequired (或 Optional[...] = None), 旧 checkpoint 仍能通过校验
from typing import NotRequired
from typing_extensions import TypedDict

class State(TypedDict):
    messages: list
    summary: NotRequired[str]   # 新字段

# JS 对应: z.string().optional() 或 .nullish()
```

其余模式:
- **删除当作弃用**: 至少在一个排空周期内保留该字段在 state 上的定义, 即使没有 node 读它, 这样旧 checkpoint 仍能加载。
- **重命名 = 先添加后删除**: 新旧字段/node 并排放置, 在一个弃用窗口内**双写 / 同时路由到两者**, 确认没有进行中 thread 依赖后再删除旧的。
- **让 node 容忍未知 key**: `TypedDict` 在 runtime 会**忽略多余 key**, 所以旧版本残留 state 不会报错 —— 除非某个 node 显式读取了缺失的 key。
- **发布前预检**: 用 time travel + `graph.get_state` 在预发布部署中用新代码抽查现有 thread。

### 检测进行中的 thread

LangGraph **本身不维护** thread state 的搜索索引, 答案取决于 graph 运行在哪里。

| 场景 | 方法 |
|------|------|
| 部署到 LangSmith | Agent Server 的 thread 搜索按状态过滤: `status` 接受 `idle` / `busy` / `interrupted` / `error`, 可批量查 `interrupted`/`busy` 并叠加元数据过滤 |
| 任意部署 | 用 LangSmith 追踪监控生产环境中哪些 node 正被进入/退出 —— 判断某 node/state 字段"不再可达"的最可靠信号 |
| 已有 `thread_id` | 直接查该 thread |

**单 thread 查询 (Python):**
- `graph.get_state(config)` → 最新 checkpoint, 含 thread 当前停在哪个 node、以及待处理的 interrupt。
- `graph.get_state_history(config)` → 该 thread 完整按时间顺序的 checkpoint 列表。

> **兜底原则**: 拿不准时, **保留**已弃用的 node 或字段, 直到 thread 列表与追踪都显示它不再有任何活动为止。

---

## 2. 业务兼容性

### 核心概念
某处改动**技术上合法** (每个 checkpoint 仍能加载、每个 node 仍能解析), 但新 graph 的**含义**与旧的**不同**。新行为对新 thread 正确, 但**不该追溯**到在旧逻辑下启动的 thread。

### 示例
原流程 `intake → triage → respond`, 现在想在 `triage` 与 `respond` 之间插入 `policy_check`:
- 已经过 `triage` 的旧 thread → 应直接到 `respond` (旧流程)。
- 新 thread → 运行完整新流程。

### 推荐做法: state 上记录"行为版本" + 条件边分支

```python
class State(TypedDict):
    request: str
    flow_version: NotRequired[int]
    response: NotRequired[str]

def intake(state: State) -> dict:
    # 给新 thread 打上当前流程版本。已经越过 intake 的旧 thread
    # 会保留它已保存的值。
    return {"flow_version": state.get("flow_version", 2)}

def after_triage(state: State) -> str:
    if state.get("flow_version", 1) >= 2:
        return "policy_check"
    return "respond"

builder.add_edge("intake", "triage")
builder.add_conditional_edges("triage", after_triage, ["policy_check", "respond"])
```

**效果**: 在 `triage` 之后恢复的旧 thread 读取其保存的 `flow_version` (或回退到 v1 默认值), 跳过 `policy_check`; 新 thread 从 `intake` 开始被打上 `flow_version=2`, 走新路径。

**清理**: 一旦所有 v1 thread 完成, 即可移除版本标志与那条 conditional edge。

> **关键约束**: 只有在 **thread 启动时**、在任何需要版本化的分支**之前**就设置好版本, 这个模式才有效。**稍后再设置 = 现有 thread 在需要它的时候还没被设置**, 模式失效。

---

## 3. 非确定性 (仅 Functional API)

### 适用范围 (重要)
只适用于:
- Functional API
- 以及 Graph API **node 内部**的 **tasks** 或 `interrupt` 调用。

**普通 Graph API node** 在恢复时会**从 node 函数开头重新运行**; 应把**副作用设计为幂等**, 但除非该 node 用了 tasks 或 `interrupt`, **无需保留 task 调用顺序**。

### 运行模型
一个 Functional API **entrypoint 会编译为单个 node**。run 恢复时, 该 node **从头重放 entrypoint 函数体**, 并用**已缓存的 `@task` 结果**跳过已完成的工作。

### 两类破坏这个模型的改动

1. **在恢复点之前新增/删除/重排 `@task` 或 `interrupt` 调用**
   - 原因: LangGraph 依据各次调用在**重放中的位置**来匹配缓存结果与恢复值。
   - 后果: 挪动位置可能把**错误的缓存值**重放到另一个调用上。

2. **在 `@task` 之外引入非确定性操作**
   - 例: `time.time()`、`random.random()`, 或内联在 entrypoint 函数体中的网络调用。
   - 后果: 重放时产生的值与首次运行不同, 可能**改变控制流**。

### 安全的重构选项 (若 `@entrypoint` 仍有进行中 run)
1. **排空**: 部署改动前先让进行中的 run 全部结束。
2. **包进新 `@task`**: 把任何新逻辑包进一个新的 `@task`, 让它的结果被**独立 checkpoint**。
3. **换新 entrypoint**: 在 `langgraph.json` 中以新的 graph 名称注册一个新 entrypoint 承载新行为, 把新 thread 路由到它。

---

## 决策清单 (改代码前自查)

1. 我是否重命名/删除了**任何 node**? → 若有 thread 停在其上或在途, 会破坏。
2. 我是否重命名/删除了**任何 State key**? → 旧 checkpoint 或下游 node 可能仍依赖。
3. 我是否**收紧了字段** (Optional→必填 / 收窄类型 / 加必填无默认值)?
4. 我的改动是否**改变了流程语义**? → 考虑"版本标记 + 条件边"。
5. 我是否在 **Functional API** 里动了 `@task` / `interrupt` 的**顺序或位置**? → 危险。
6. 我是否在 `@task` **之外**引入了非确定性?
7. 发布前是否用 `get_state` / 追踪**抽查过预发布**?

---

## 易错点 / 坑 / 注意事项

| # | 坑 | 说明 |
|---|----|------|
| 1 | 以为"新增 edge 安全"涵盖了重命名 node | 新增/删除/改接 edge 在**仍存在的 node 之间**安全; 但重命名/删除 node 会破坏 interrupt 中的 thread |
| 2 | 直接删字段或 node | 应**先弃用、后删除**, 留一个排空周期 |
| 3 | 忘记 edge 拓扑不持久化 | 所以拓扑改动通常安全, 不要过度保守 |
| 4 | 版本标记设晚了 | 必须在 thread **启动时**设置, 否则旧 thread 在需要时拿到的是默认值 |
| 5 | 只在 Functional API 才担心非确定性 | 普通 Graph API node 需保证**副作用幂等**, 但不用管 task 顺序 |
| 6 | 假设 LangGraph 有 thread 索引 | 它**没有**; 检测靠 Agent Server 的 thread 搜索 / LangSmith 追踪 / `get_state` |
| 7 | 重排 `@task` 顺序 | 会因位置匹配错位而重放**错误的缓存值** |
| 8 | 在 `@task` 外放 `random/time/网络调用` | 重放结果不一致, 控制流漂移 |

### 概念区分
- **技术兼容性**: "代码还能不能加载/解析现有 state" —— 结构问题。
- **业务兼容性**: "代码能跑, 但行为语义变了" —— 语义问题。
- **非确定性**: "重放时结果不一致" —— 仅 Functional API 的重放模型问题。
