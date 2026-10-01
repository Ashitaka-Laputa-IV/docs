# 用 LangGraph 思考 —— 速读笔记

> 源文件: `src/oss/langgraph/thinking-in-langgraph.mdx`
> 一句话: 用"客服邮件 agent"这一条主线, 演示用 LangGraph 构建 agent 的**五步思考法**。

## 0. 核心心智模型

用 LangGraph 构建 agent 的总纲:

1. 把流程拆成一个个**离散步骤** → 每个步骤是一个 **node**。
2. 描述每个 node 可能做出的**不同决策与跳转**。
3. 用一个**共享 state** 把 nodes 连接起来, 每个 node 都能读写它。

> 一句话记忆: **拆步骤 → 定跳转 → 共享 state**。

### 贯穿全篇的五步法

| 步骤 | 名称 | 产物 |
|------|------|------|
| Step 1 | 把工作流画成离散步骤 | node 清单 + 跳转关系图 |
| Step 2 | 确定每个步骤要做什么 | 操作类型分类 + 所需上下文 |
| Step 3 | 设计 state | 共享数据结构 (只存原始数据) |
| Step 4 | 构建 nodes | 每个 node 一个函数 + 错误处理策略 |
| Step 5 | 把一切接起来 | `StateGraph` + edges + compile |

---

## Step 1: 把工作流拆成离散步骤

### 核心概念
- 先识别流程中**彼此独立的步骤**, 每个步骤 = 一个 **node** (只做一件具体事的函数)。
- 再画出步骤之间**如何连接** (箭头表示可能的路径)。

### 案例: 客服邮件 agent 的需求

agent 应当: 读取邮件 → 按紧急度/主题分类 → 检索文档 → 起草回复 → 复杂问题升级人工 → 需要时安排跟进。

示例场景 (用于测试路由):
1. 简单产品问题: "How do I reset my password?"
2. Bug 报告: "The export feature crashes when I select PDF format"
3. 紧急账单问题: "I was charged twice for my subscription!"
4. 功能请求: "Can you add dark mode to the mobile app?"
5. 复杂技术问题: "Our API integration fails intermittently with 504 errors"

### 识别出的 nodes

| Node | 职责 |
|------|------|
| `Read Email` | 提取并解析邮件内容 |
| `Classify Intent` | 用 LLM 分类紧急度与主题, 再路由 |
| `Doc Search` | 在知识库中查询相关信息 |
| `Bug Track` | 在跟踪系统中创建/更新 issue |
| `Draft Reply` | 生成合适的回复 |
| `Human Review` | 升级给人工审批或处理 |
| `Send Reply` | 发送邮件回复 |

### 关键区分 (易混淆)
- **决策型 node**: `Classify Intent`、`Draft Reply`、`Human Review` —— 它们会决定接下来去哪里。
- **直连型 node**: `Read Email` 总是 → `Classify Intent`; `Doc Search` 总是 → `Draft Reply` —— 固定进入同一个下一步。

> 心智模型: **图中的箭头只表示"可能路径", 真正决定走哪条路的逻辑发生在每个 node 内部。**

---

## Step 2: 确定每个步骤要做什么

对每个 node 判断两件事: **属于哪类操作** + **正常工作需要哪些上下文**。

### 四类操作 (CardGroup 分类)

| 类型 | 何时使用 |
|------|----------|
| **LLM steps** | 需要理解、分析、生成文本或做出推理决策时 |
| **Data steps** | 需要从外部来源检索信息时 |
| **Action steps** | 需要执行外部操作时 |
| **User input steps** | 需要人工介入时 |

### LLM steps 示例

- **Classify intent**
  - 静态上下文 (prompt): 分类类别、紧急程度定义、响应格式
  - 动态上下文 (来自 state): 邮件内容、发件人信息
  - 期望结果: 决定路由的**结构化**分类结果
- **Draft reply**
  - 静态上下文 (prompt): 语气准则、公司政策、响应模板
  - 动态上下文 (来自 state): 分类结果、搜索结果、客户历史
  - 期望结果: 可供审阅的专业邮件回复

### Data steps 示例

- **Document search**: 参数 = 由 intent 与 topic 构造; 重试 = 是 (指数退避); 缓存 = 可缓存常见查询。
- **Customer history lookup**: 参数 = 客户邮箱/ID; 重试 = 是 (数据不可用时回退到基本信息); 缓存 = 是 (设 TTL 平衡新鲜度与性能)。

### Action steps 示例

- **Send reply**: 执行时机 = 获得批准后; 重试 = 是 (指数退避); **不应缓存** (每次发送唯一)。
- **Bug track**: intent 为 "bug" 时**总是**执行; 重试 = 是 (不能丢 bug 报告); 返回值需含工单 ID 以便写进回复。

### User input steps 示例

- **Human review node**: 决策所需上下文 = 原始邮件 + 回复草稿 + 紧急度 + 分类结果; 期望输入格式 = 审批布尔值 (+可选修改后回复); 触发 = 高紧急度、复杂问题或质量隐患。

---

## Step 3: 设计 state

### 核心概念
state 是所有 nodes 都能访问的**共享 memory**, 相当于 agent 的笔记本。

### 判定规则 (两条黄金问题)
- 它需要**跨步骤持续存在**吗? → 是则放进 state。
- 你能**从其他数据推导**出它吗? → 能则在需要时计算, **不要**存进 state。

邮件 agent 需要跟踪: 原始邮件与发件人 (之后无法重建)、分类结果 (多个下游 node 需要)、搜索结果与客户数据 (重新获取代价高)、回复草稿 (审阅过程中保留)、执行元数据 (调试与恢复)。

### 关键原则: state 存原始数据, 按需格式化 prompt

- 不同 node 可**以不同方式**格式化同一份数据。
- 改 prompt 模板**无需改** state schema。
- 调试更清晰: 能准确看到每个 node 收到什么数据。
- agent 可持续演进而不破坏已有 state。

### State 定义 (Python)

```python
from typing import TypedDict, Literal

class EmailClassification(TypedDict):
    intent: Literal["question", "bug", "billing", "feature", "complex"]
    urgency: Literal["low", "medium", "high", "critical"]
    topic: str
    summary: str

class EmailAgentState(TypedDict):
    # 原始邮件数据
    email_content: str
    sender_email: str
    email_id: str
    # 分类结果
    classification: EmailClassification | None
    # 原始检索/API 结果
    search_results: list[str] | None
    customer_history: dict | None
    # 生成内容
    draft_response: str | None
    messages: list[str] | None
```

> state 中**只有原始数据**: 没有 prompt 模板、没有格式化字符串、没有指令。分类输出以字典形式直接来自 LLM 并原样存入。

---

## Step 4: 构建 nodes

### 核心概念
LangGraph 中的 **node = 接收当前 state、返回 state 更新的函数**。

### 4.1 错误处理策略 (重要表格)

| 错误类型 | 谁来修复 | 策略 | 使用场景 |
|----------|----------|------|----------|
| 瞬时错误 (网络、限流) | 系统 (自动) | `RetryPolicy` 重试 | 重试即可解决的临时故障 |
| LLM 可恢复 (tool 失败、解析问题) | LLM | 把错误存入 state 并**回环** | LLM 能看到错误并调整 |
| 用户可修复 (缺信息、指令不清) | 人工 | `interrupt()` 暂停 | 需用户输入才能继续 |
| 重试后仍可恢复的失败 | 开发者 (声明式) | `error_handler` | 重试耗尽后运行补偿/恢复分支 |
| 意料之外的错误 | 开发者 | 让它向上抛出 | 需要调试的未知问题 |

### 4.2 各策略代码要点 (Python)

瞬时错误 —— 加重试策略 (可与 `timeout=` 配合):
```python
from langgraph.types import RetryPolicy

workflow.add_node(
    "search_documentation",
    search_documentation,
    retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0),
)
```

LLM 可恢复 —— 把错误写进 state 并 `Command(goto=...)` 回环给 LLM:
```python
def execute_tool(state: State) -> Command[Literal["agent", "execute_tool"]]:
    try:
        result = run_tool(state['tool_call'])
        return Command(update={"tool_result": result}, goto="agent")
    except ToolError as e:
        return Command(update={"tool_result": f"Tool error: {str(e)}"}, goto="agent")
```

用户可修复 —— `interrupt()` 收集信息后回到同一 node:
```python
def lookup_customer_history(state: State):
    if not state.get('customer_id'):
        user_input = interrupt({
            "message": "Customer ID needed",
            "request": "Please provide the customer's account ID ...",
        })
        return Command(update={"customer_id": user_input['customer_id']},
                       goto="lookup_customer_history")
    customer_data = fetch_customer_history(state['customer_id'])
    return Command(update={"customer_history": customer_data}, goto="draft_response")
```

意料之外 —— **不要捕获你处理不了的错误**:
```python
def send_reply(state: EmailAgentState):
    try:
        email_service.send(state["draft_response"])
    except Exception:
        raise  # 让意料之外的错误冒出来便于调试
```

Saga / 补偿 —— 重试耗尽后运行恢复函数 (需 `langgraph>=1.2`):
```python
from langgraph.errors import NodeError

def payment_error_handler(state: State, error: NodeError) -> Command:
    return Command(update={"status": f"compensated: {error.error}"}, goto="finalize")

workflow.add_node(
    "charge_payment", charge_payment,
    retry_policy=RetryPolicy(max_attempts=3, retry_on=ConnectionError),
    error_handler=payment_error_handler,
)
```
> 想对全部 node 统一配置, 用 `StateGraph.set_node_defaults(...)`; 单个 node 上的取值仍然优先。

### 4.3 实现 email agent nodes (Python 核心)

**读邮件 + 分类** —— 用 `with_structured_output` 拿到 dict, 再按分类决定 `goto`:
```python
def classify_intent(state: EmailAgentState) -> Command[Literal[...]]:
    structured_llm = llm.with_structured_output(EmailClassification)
    classification_prompt = f"Analyze this customer email ... Email: {state['email_content']} ..."
    classification = structured_llm.invoke(classification_prompt)

    if classification['intent'] == 'billing' or classification['urgency'] == 'critical':
        goto = "human_review"
    elif classification['intent'] in ['question', 'feature']:
        goto = "search_documentation"
    elif classification['intent'] == 'bug':
        goto = "bug_tracking"
    else:
        goto = "draft_response"

    return Command(update={"classification": classification}, goto=goto)
```

**检索 + 建单** —— 存原始结果, 检索失败时把错误也当结果存下继续:
```python
def search_documentation(state: EmailAgentState) -> Command[Literal["draft_response"]]:
    classification = state.get('classification', {})
    query = f"{classification.get('intent', '')} {classification.get('topic', '')}"
    try:
        search_results = ["...", "..."]  # 你的检索逻辑
    except SearchAPIError as e:
        search_results = [f"Search temporarily unavailable: {str(e)}"]
    return Command(update={"search_results": search_results}, goto="draft_response")
```

**起草 + 人工审批 + 发送** —— 在 node 内**按需**格式化上下文:
```python
def draft_response(state: EmailAgentState) -> Command[Literal["human_review", "send_reply"]]:
    # 从原始 state 按需拼装 prompt 上下文
    ...
    response = llm.invoke(draft_prompt)
    needs_review = (classification.get('urgency') in ['high', 'critical']
                    or classification.get('intent') == 'complex')
    goto = "human_review" if needs_review else "send_reply"
    return Command(update={"draft_response": response.content}, goto=goto)

def human_review(state: EmailAgentState) -> Command[Literal["send_reply", END]]:
    # interrupt() 必须放在最前面
    human_decision = interrupt({... "action": "Please review and approve/edit ..."})
    if human_decision.get("approved"):
        return Command(update={"draft_response": human_decision.get("edited_response", ...)},
                       goto="send_reply")
    else:
        return Command(update={}, goto=END)
```

> **坑**: `interrupt()` 必须放在 node 函数**最前面** —— 它之前的任何代码在恢复时都会**重新运行**。

---

## Step 5: 把一切接起来

### 核心概念
因为 nodes 自己负责路由 (`Command`), 所以只需要**少量必要的 edges**。

要让 `interrupt()` 支持 human-in-the-loop, 编译时必须传入 **checkpointer** 以在多次运行间保存 state。

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import RetryPolicy

workflow = StateGraph(EmailAgentState)
workflow.add_node("read_email", read_email)
workflow.add_node("classify_intent", classify_intent)
workflow.add_node("search_documentation", search_documentation,
                  retry_policy=RetryPolicy(max_attempts=3))
workflow.add_node("bug_tracking", bug_tracking)
workflow.add_node("draft_response", draft_response)
workflow.add_node("human_review", human_review)
workflow.add_node("send_reply", send_reply)

workflow.add_edge(START, "read_email")
workflow.add_edge("read_email", "classify_intent")
workflow.add_edge("send_reply", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
```

> graph 结构精简的原因: **路由通过 `Command` 对象在 node 内部完成**。每个 node 用 `Command[Literal["node1","node2"]]` 类型标注声明可去哪里, 使流程显式且可追踪。

### 运行与恢复 (interrupt 暂停机制)

```python
config = {"configurable": {"thread_id": "customer_123"}}
result = app.invoke(initial_state, config)   # 会在 human_review 处暂停
# ... 人工给出输入后恢复:
human_response = Command(resume={"approved": True, "edited_response": "..."})
final_result = app.invoke(human_response, config)
```

> **机制**: graph 遇到 `interrupt()` 会暂停, 把一切保存到 checkpointer 后等待; 可以过几天再恢复, 从中断处**精确**继续。`thread_id` 确保该会话所有 state 保存在一起。

---

## 关键要点总结 (六条)

1. **拆分为离散步骤** —— 每个 node 只做好一件事, 这让 streaming 进度、可暂停/恢复的 durable execution、清晰调试成为可能。
2. **state 是共享 memory** —— 存原始数据, 不存格式化文本, 让不同 node 以不同方式使用同一份信息。
3. **nodes 就是函数** —— 接收 state、完成工作、返回更新; 需要路由时同时指定 state 更新与下一个目标。
4. **错误是流程的一部分** —— 瞬时故障重试, LLM 可恢复错误带上下文回环, 用户可修复问题暂停等输入, 意料之外错误向上抛出。
5. **人工输入是一等公民** —— `interrupt()` 无限期暂停、保存全部 state、提供输入后精确恢复; 与其他操作共存时必须放最前。
6. **graph 结构自然浮现** —— 只定义必要连接, nodes 自行处理路由; 控制流显式可追踪。

---

## 进阶考量: node 粒度的取舍

> 大多数应用可跳过本节。

**为什么要拆这么细?** 涉及**韧性 (容错)** 与**可观测性**之间的取舍。

**韧性考量**: persistence layer 在 **node 边界**处创建 checkpoints。恢复时从"执行停止处所在 node 的开头"重新开始。**node 越小 → checkpoints 越频繁 → 出错时要重做的工作越少**。把多个操作合并成大 node, 若失败发生在接近末尾, 就要从该 node 开头重执行全部内容。

**本案例的拆分理由:**
- **隔离外部服务**: Doc Search / Bug Track 独立成 node, 因其调用外部 API, 可只给它们加重试策略。
- **中间过程可见**: `Classify Intent` 独立, 能在行动前检查 LLM 判定 —— 对调试/监控很有价值。
- **不同失败模式**: LLM 调用、数据库查询、邮件发送重试策略不同, 拆开可分别配置。
- **可复用与测试**: 更小的 node 更易单测、更易复用。

**替代方案**: 也可把 `Read Email` + `Classify Intent` 合并成一个 node —— 代价是失去"分类前检查原始邮件"的能力, 且失败要重做两者。对多数应用, 保留拆分的收益更大。

**应用层 vs 框架层**: Step 2 讨论的"是否缓存搜索结果"是**应用级决策**, 需在 node 函数内部自行实现, LangGraph 不规定。

**性能考量**: node 更多**不代表**执行更慢。LangGraph 默认在后台异步写 checkpoints (`async` durability mode), graph 继续运行不等待。可调整: `"exit"` 只在完成时写, `"sync"` 每次写入阻塞执行。

---

## 易错点 / 坑 / 注意事项

| # | 坑 | 正确做法 |
|---|----|----------|
| 1 | 在 `interrupt()` 之前写逻辑 | `interrupt()` 必须放 node 函数**最前面**, 否则恢复时前面的代码会重跑 |
| 2 | 把格式化后的 prompt 文本存进 state | 只存**原始数据**, 在 node 内按需格式化 |
| 3 | 捕获所有异常 | **意料之外**的错误应向上抛出以便调试; 只处理你明确知道怎么处理的 |
| 4 | 忘记传 checkpointer | 用 `interrupt()` 时必须 `compile(checkpointer=...)`, 否则无法跨运行保存 state |
| 5 | 忘记传 `thread_id` | 用 `config={"configurable": {"thread_id": ...}}`, 否则 state 无法关联到同一会话 |
| 6 | 混淆"箭头"与"决策" | 箭头只表示**可能路径**, 真正路由逻辑在 node 内部 (`Command(goto=...)`) |
| 7 | 在 state 里存可推导的数据 | 能推导的就别存, 需要时计算 |
| 8 | 认为 node 越多越慢 | 默认异步写 checkpoint, node 多影响很小 |
| 9 | 用 `interrupt()` 收集用户输入却回到新 node | 应 `Command(goto=同一个node)` 回到本 node, 让它带着新数据继续 |

### 概念区分
- **`RetryPolicy` vs `error_handler`**: 前者是"再试几次", 后者是"试完都失败后走补偿分支"。
- **`Command(update=..., goto=...)` 与普通返回值**: 普通 node 返回 dict 只更新 state; 需要**跳转**时返回 `Command`。
- **`interrupt()` 的暂停 vs 报错退出**: 暂停是设计行为, state 被完整保存, 可精确恢复。
