# Workflow 与 agent —— 速读笔记

> 源文件: `src/oss/langgraph/workflows-agents.mdx`
> 一句话: 梳理 7 种常见的 workflow / agent 编排模式, 每种给出 Graph API 与 Functional API 两套 Python 写法。

## 0. 总纲

| 概念 | 定义 |
|------|------|
| **Workflow** | 代码路径**预先确定**, 按特定顺序运行 |
| **Agent** | **动态**的, 自行决定流程与 tool 使用方式 |

**本页覆盖的 7 种模式:**

1. LLM 与增强 (基础能力)
2. Prompt chaining (提示链)
3. Parallelization (并行化)
4. Routing (路由)
5. Orchestrator-worker (编排器-工人)
6. Evaluator-optimizer (评估器-优化器)
7. Agents (智能体)

> LangGraph 为构建这些模式提供: persistence、streaming、调试与部署支持。

### 环境准备

```bash
pip install langchain_core langchain-anthropic langgraph
```

```python
from langchain_anthropic import ChatAnthropic
llm = ChatAnthropic(model="claude-sonnet-4-6")
```

> 可使用任何支持结构化输出与 tool calling 的 chat model。

---

## 1. LLM 与增强 (LLM augmentations)

> workflows 与 agentic 系统都以 LLM 为基础, 再叠加各种增强能力 (tool calling、structured outputs、short term memory)。

### 关键代码 (Python)

```python
from pydantic import BaseModel, Field

# 结构化输出 schema
class SearchQuery(BaseModel):
    search_query: str | None = Field(default=None, description="Query that is optimized web search.")
    justification: str | None = Field(default=None, description="Why this query is relevant ...")

structured_llm = llm.with_structured_output(SearchQuery)
output = structured_llm.invoke("How does Calcium CT score relate to high cholesterol?")
# 模型返回 SearchQuery 实例

# 定义 tool
def multiply(a: int, b: int) -> int:
    return a * b

llm_with_tools = llm.bind_tools([multiply])
msg = llm_with_tools.invoke("What is 2 times 3?")
print(msg.tool_calls)  # 模型返回一个 tool 调用请求
```

> **心智模型**: `with_structured_output` → 拿**结构化对象**; `bind_tools` → 拿**tool 调用请求** (还要你自己执行)。

---

## 2. Prompt chaining (提示链)

### 核心概念
**每一次 LLM 调用都处理上一次调用的输出**。适合可拆解成更小、可验证步骤的明确定义任务。

典型用途: 文档翻译成多语言、校验生成内容一致性。

### 关键结构 (Graph API)
`generate_joke` → 条件边 `check_punchline` (Pass→END / Fail→`improve_joke`) → `polish_joke` → END。

```python
workflow = StateGraph(State)
workflow.add_node("generate_joke", generate_joke)
workflow.add_node("improve_joke", improve_joke)
workflow.add_node("polish_joke", polish_joke)
workflow.add_edge(START, "generate_joke")
workflow.add_conditional_edges(
    "generate_joke", check_punchline, {"Fail": "improve_joke", "Pass": END}
)
workflow.add_edge("improve_joke", "polish_joke")
workflow.add_edge("polish_joke", END)
chain = workflow.compile()
```

**门控函数 (gate)**:
```python
def check_punchline(state: State):
    if "?" in state["joke"] or "!" in state["joke"]:
        return "Pass"
    return "Fail"
```

### Functional API 写法要点
- 用 `@task` 定义每个步骤, 用 `@entrypoint()` 定义编排函数。
- 调用 `.result()` 取得 task 结果。
- 门控判断在 entrypoint 内部用普通 `if`。

```python
@entrypoint()
def prompt_chaining_workflow(topic: str):
    original_joke = generate_joke(topic).result()
    if check_punchline(original_joke) == "Pass":
        return original_joke
    improved_joke = improve_joke(original_joke).result()
    return polish_joke(improved_joke).result()
```

> **注意 (文档原样)**: Graph API 示例中 `check_punchline` 的 Pass/Fail 与 Functional API 示例相反 —— Graph API: 含 `?`/`!` 返回 `"Pass"` 并走向 END; Functional API: 含 `?`/`!` 返回 `"Pass"` 并**提前返回**。两版语义一致, 但映射方向不同, 阅读时勿混淆。

---

## 3. Parallelization (并行化)

### 核心概念
**多个 LLM 同时处理一项任务**。两种形态:
- 同时运行多个**彼此独立的子任务** (提升速度)
- **重复运行同一个任务**以检查不同输出 (提升置信度)

典型用途: 一个子任务提取关键词、另一个查格式错误; 多次运行同一任务按不同标准打分。

### 关键结构 (Graph API)
从 `START` 同时连出 3 条边, 每个 node 再连到 `aggregator`, 由它汇总:

```python
parallel_builder.add_edge(START, "call_llm_1")
parallel_builder.add_edge(START, "call_llm_2")
parallel_builder.add_edge(START, "call_llm_3")
parallel_builder.add_edge("call_llm_1", "aggregator")
parallel_builder.add_edge("call_llm_2", "aggregator")
parallel_builder.add_edge("call_llm_3", "aggregator")
parallel_builder.add_edge("aggregator", END)
```

### Functional API 写法要点
多个 task 先**发起**(返回 future) 再统一 `.result()`, 天然并发:

```python
@entrypoint()
def parallel_workflow(topic: str):
    joke_fut = call_llm_1(topic)
    story_fut = call_llm_2(topic)
    poem_fut = call_llm_3(topic)
    return aggregator(topic, joke_fut.result(), story_fut.result(), poem_fut.result()).result()
```

> **易错点**: 若写成 `call_llm_1(topic).result()` 逐个求解, 就退化成串行, 失去并行效果。

---

## 4. Routing (路由)

### 核心概念
先**处理输入**判断类型, 再把请求**引导到专门的处理流程**。适合"复杂任务拆成多条专用路径"。

例: 产品问答 workflow 先判断问题类型, 再路由到定价 / 退款 / 退货各自流程。

### 关键结构 (Graph API)
用一个"路由 node"产出结构化 decision, 再用条件边映射到各处理 node:

```python
class Route(BaseModel):
    step: Literal["poem", "story", "joke"] = Field(None, description="The next step ...")

router = llm.with_structured_output(Route)

def llm_call_router(state: State):
    decision = router.invoke([
        SystemMessage(content="Route the input to story, joke, or poem based on the user's request."),
        HumanMessage(content=state["input"]),
    ])
    return {"decision": decision.step}

def route_decision(state: State):
    if state["decision"] == "story":
        return "llm_call_1"
    elif state["decision"] == "joke":
        return "llm_call_2"
    elif state["decision"] == "poem":
        return "llm_call_3"

router_builder.add_edge(START, "llm_call_router")
router_builder.add_conditional_edges(
    "llm_call_router", route_decision,
    {"llm_call_1": "llm_call_1", "llm_call_2": "llm_call_2", "llm_call_3": "llm_call_3"},
)
```

**两段式设计**:
1. `llm_call_router` (node): 用 LLM 做**分类决策** → 写进 state。分离出来便于直接测试路由逻辑。
2. `route_decision` (条件边函数): 把 decision **映射**到具体 node。

### Functional API 写法要点
在 entrypoint 内用 `if/elif` 选 task 再调用:

```python
@entrypoint()
def router_workflow(input_: str):
    next_step = llm_call_router(input_)
    if next_step == "story":
        llm_call = llm_call_1
    elif next_step == "joke":
        llm_call = llm_call_2
    elif next_step == "poem":
        llm_call = llm_call_3
    return llm_call(input_).result()
```

> **坑**: 文档中 Python Functional API 路由示例只覆盖 `story/joke/poem` 三种分支, 没有兜底 else —— 真实代码应补默认分支, 否则模型返回意外值时 `llm_call` 未定义。

---

## 5. Orchestrator-worker (编排器-工人)

### 核心概念
**orchestrator**:
1. 把任务**拆解**成子任务
2. 把子任务**分派**给 workers
3. **汇总**各 worker 输出成最终结果

> 比并行化更**灵活**, 适合**子任务数量无法预先定义**的场景 (如跨多个文件改代码)。

### 5.1 纯 Functional API 版 (无 Send)

用 `@task` 分别定义 `orchestrator` / `llm_call` / `synthesizer`, 在 entrypoint 中先规划再并发执行:

```python
# planner 输出结构化 plan
class Section(BaseModel):
    name: str = Field(description="Name for this section of the report.")
    description: str = Field(description="Brief overview ...")

class Sections(BaseModel):
    sections: List[Section] = Field(description="Sections of the report.")

planner = llm.with_structured_output(Sections)

@entrypoint()
def orchestrator_worker(topic: str):
    sections = orchestrator(topic).result()
    section_futures = [llm_call(section) for section in sections]
    final_report = synthesizer([fut.result() for fut in section_futures]).result()
    return final_report
```

### 5.2 Graph API + `Send` API 版 (推荐, 内置支持)

`Send` 让你**动态创建 worker nodes** 并把特定输入发过去。每个 worker 有**自己的 state**, 所有 worker 输出写入一个**共享 state key** (用 `Annotated[list, operator.add]` 聚合)。

```python
from langgraph.types import Send

class State(TypedDict):
    topic: str
    sections: list[Section]
    completed_sections: Annotated[list, operator.add]  # 所有 worker 并行写这里
    final_report: str

class WorkerState(TypedDict):
    section: Section
    completed_sections: Annotated[list, operator.add]

def assign_workers(state: State):
    """为 plan 里每个 section 分配一个 worker"""
    return [Send("llm_call", {"section": s}) for s in state["sections"]]

orchestrator_worker_builder.add_edge(START, "orchestrator")
orchestrator_worker_builder.add_conditional_edges("orchestrator", assign_workers, ["llm_call"])
orchestrator_worker_builder.add_edge("llm_call", "synthesizer")
orchestrator_worker_builder.add_edge("synthesizer", END)
```

> **关键点**: `Send("llm_call", {"section": s})` = "以这个输入启动一个 `llm_call` worker"。返回列表即可一次派发 N 个。所有 worker 的 `completed_sections` 通过 reducer 累加进主 state。

---

## 6. Evaluator-optimizer (评估器-优化器)

### 核心概念
**一次 LLM 调用生成响应, 另一次 LLM 调用评估该响应**。若评估方 (或 human-in-the-loop) 认为需改进, 就给出反馈并**重新生成**。循环直到可接受。

适用: 任务**有明确成功标准**但需反复迭代才能达标 (如两种语言间翻译, 很难一次到位)。

### 关键结构 (Graph API)
环状结构: `generator → evaluator → 条件边` (Accepted→END / Rejected→回 generator)。

```python
class Feedback(BaseModel):
    grade: Literal["funny", "not funny"] = Field(description="Decide if the joke is funny or not.")
    feedback: str = Field(description="If the joke is not funny, provide feedback ...")

evaluator = llm.with_structured_output(Feedback)

def llm_call_generator(state: State):
    if state.get("feedback"):
        msg = llm.invoke(f"Write a joke about {state['topic']} but take into account the feedback: {state['feedback']}")
    else:
        msg = llm.invoke(f"Write a joke about {state['topic']}")
    return {"joke": msg.content}

def llm_call_evaluator(state: State):
    grade = evaluator.invoke(f"Grade the joke {state['joke']}")
    return {"funny_or_not": grade.grade, "feedback": grade.feedback}

def route_joke(state: State):
    if state["funny_or_not"] == "funny":
        return "Accepted"
    elif state["funny_or_not"] == "not funny":
        return "Rejected + Feedback"

optimizer_builder.add_conditional_edges(
    "llm_call_evaluator", route_joke,
    {"Accepted": END, "Rejected + Feedback": "llm_call_generator"},
)
```

### Functional API 写法要点
用普通 `while True` 循环:

```python
@entrypoint()
def optimizer_workflow(topic: str):
    feedback = None
    while True:
        joke = llm_call_generator(topic, feedback).result()
        feedback = llm_call_evaluator(joke).result()
        if feedback.grade == "funny":
            break
    return joke
```

> **坑**: 这是**无上限循环**。生产中应加最大迭代次数 / 超时, 否则可能无限循环。文档示例未加保护。

---

## 7. Agents (智能体)

### 核心概念
Agent = **LLM 使用 tools 执行操作**, 在**持续反馈循环**中运行, 适合问题与解法都不确定的场景。比 workflow 更自主, 但仍是**你来定义可用 toolset 与行为准则**。

### 7.1 定义 tools (Python)

```python
from langchain.tools import tool

@tool
def multiply(a: int, b: int) -> int:
    """Multiply `a` and `b`."""
    return a * b

@tool
def add(a: int, b: int) -> int:
    """Adds `a` and `b`."""
    return a + b

@tool
def divide(a: int, b: int) -> float:
    """Divide `a` and `b`."""
    return a / b

tools = [add, multiply, divide]
tools_by_name = {tool.name: tool for tool in tools}
llm_with_tools = llm.bind_tools(tools)
```

> **坑 (文档示例)**: `tools_by_name = {tool.name: tool for tool in tools}` 会因为列表元素本身也叫 `tool` (未遮蔽, 但名字与实际对象语义易混) 阅读时注意 —— 元素是 **tool 对象**, 不是 `tool` 装饰器。

### 7.2 Graph API 版: 经典 ReAct 循环

两个 node + 一条条件边:

```python
from langgraph.graph import MessagesState

def llm_call(state: MessagesState):
    """LLM 决定是否调用 tool"""
    return {"messages": [
        llm_with_tools.invoke(
            [SystemMessage(content="You are a helpful assistant tasked with performing arithmetic ...")]
            + state["messages"]
        )
    ]}

def tool_node(state: MessagesState):
    """执行 tool 调用"""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}

def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"
    return END

agent_builder = StateGraph(MessagesState)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "llm_call")   # 关键: tool → llm 形成循环
agent = agent_builder.compile()
```

> **心智模型**: `llm_call ⇄ tool_node` 的循环 = ReAct。`should_continue` 是循环的**退出条件** (没有 tool_calls 就结束)。

### 7.3 Functional API 版
用 `@task` 定义 `call_llm` / `call_tool`, entrypoint 内 `while True` 循环, 用 `add_messages` 累积消息:

```python
@entrypoint()
def agent(messages: list[BaseMessage]):
    llm_response = call_llm(messages).result()
    while True:
        if not llm_response.tool_calls:
            break
        tool_result_futures = [call_tool(tool_call) for tool_call in llm_response.tool_calls]
        tool_results = [fut.result() for fut in tool_result_futures]
        messages = add_messages(messages, [llm_response, *tool_results])
        llm_response = call_llm(messages).result()
    messages = add_messages(messages, llm_response)
    return messages
```

> 多个 tool 调用通过"先发起 future、再统一 `.result()`"实现并行。

### 7.4 ToolNode (prebuilt)

`ToolNode` 是一个 prebuilt node, 用于执行 tools, 自动处理: **并行执行、错误处理、state 注入**。

```python
from langgraph.prebuilt import ToolNode

builder = StateGraph(MessagesState)
builder.add_node("tools", ToolNode([search, calculator]))
graph = builder.compile()
```

> 当你需要对 graph 执行 tools 的方式做**精细控制**时用它; 它是许多 LangGraph agent 模式中 tool 执行的构建块。

#### 从 tools 中访问 graph state 与 context

由 `ToolNode` 执行的 tools 只把 **model 生成的参数**作为第一个参数接收。要读取**非 model 生成**的 graph 侧数据:

- **Python**: 从注入的 `ToolRuntime` 参数读取 state 与 run 级上下文。
- **JS**: 从 tool 的第二个参数 (类型 `ToolRuntime`) 读取。

> **关键坑**: Tools **只能访问传给 `ToolNode` 的 state 取值**。
> - 直接把 `ToolNode` 作为 `StateGraph` 的 node 添加时, 输入 = 当前完整 graph state。
> - 若从**另一个 node 手动调用** `ToolNode`: `tool_node.invoke(state)` 会暴露完整 state; 而只传 `{"messages": state["messages"]}` 就**只暴露 `messages`**, 自定义字段会丢失!

---

## 模式选择速查表

| 模式 | 何时用 | 关键机制 |
|------|--------|----------|
| LLM 增强 | 所有场景的基础 | `with_structured_output` / `bind_tools` |
| Prompt chaining | 可拆成固定小步骤的明确任务 | 线性 edges + gate 条件边 |
| Parallelization | 独立子任务, 追求速度/置信度 | 多起点边 + aggregator |
| Routing | 输入多样, 需分流到专用流程 | 路由 node + 条件边 |
| Orchestrator-worker | 子任务数量无法预先知道 | `Send` API / task futures |
| Evaluator-optimizer | 有明确标准但需迭代 | 环状条件边 / while 循环 |
| Agents | 问题与解法都不确定 | `llm ⇄ tool` ReAct 循环 / ToolNode |

> **Workflow vs Agent 的取舍**: workflow 可控、可预测、易调试; agent 灵活、自主, 但更需要 guardrail。可组合使用 (agent 内部嵌入 workflow)。

---

## 易错点 / 坑 / 注意事项汇总

| # | 坑 | 说明 |
|---|----|------|
| 1 | Parallelization 退化成串行 | Functional API 中要**先发起所有 future 再统一 `.result()`** |
| 2 | Routing 缺兜底分支 | 模型返回意外值时可能 `llm_call` 未定义 |
| 3 | Evaluator-optimizer 无限循环 | 无上限 `while True` / 条件边环, 生产需加最大迭代 |
| 4 | `Send` 的 worker state 隔离 | 每个 worker 有独立 state, 输出必须写进**带 reducer 的共享 key** 才能汇总 |
| 5 | 手动调用 ToolNode 时丢 state | 只传 `messages` 会丢失自定义 state 字段, 需传完整 state |
| 6 | tool 参数顺序 | ToolNode 执行的 tool 第一个参数来自 model; graph 侧数据要走 `ToolRuntime` |
| 7 | 混淆两种 API | Graph API 用 node+edge; Functional API 用 `@task`/`@entrypoint`+`.result()`, 二选一或组合 |
| 8 | 忘记 `Annotated[list, operator.add]` | 多个 worker 并行写同一 key 需要 reducer 聚合, 否则会互相覆盖 |
