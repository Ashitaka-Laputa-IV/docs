# 快速入门: 计算器 agent — 速读笔记

源文件: `src/oss/langgraph/quickstart.mdx`

目标: 用 LangGraph 构建一个能调用 add / multiply / divide 三个 tools 的计算器 agent。
提供两条路径: **Graph API** (把 agent 定义为由 nodes 与 edges 组成的 graph) 与 **Functional API** (把 agent 定义为单个函数)。

## 前置准备

- 需要 Anthropic (Claude) 账号并获取 API key, 在终端设置 `ANTHROPIC_API_KEY`。
- 示例默认模型: `claude-sonnet-4-6`, `temperature=0`。
- 如需其他 provider, 参阅 chat model integrations。

## 路径选择

| 你的偏好 | 用哪个 API |
|----------|-----------|
| 把 agent 定义为 nodes + edges 组成的 graph | Graph API |
| 把 agent 定义为单个函数, 用普通控制流 | Functional API |

概念说明分别见 Graph API overview 与 Functional API overview。

---

## 路径 A: Graph API (推荐默认)

六个步骤: 定义 tools/model → 定义 state → model node → tool node → 结束逻辑 → 构建编译。

### 1. 定义 tools 与 model

```python
from langchain.tools import tool
from langchain.chat_models import init_chat_model

model = init_chat_model("claude-sonnet-4-6", temperature=0)

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
model_with_tools = model.bind_tools(tools)
```

### 2. 定义 state

state 存储 messages 与 LLM 调用次数。用 `Annotated[list, operator.add]` 让新消息**追加**而不是覆盖。

```python
from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator

class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
```

### 3. 定义 model node

调用 LLM, 决定是否调 tool; 同时把 `llm_calls` 加一。

```python
from langchain.messages import SystemMessage

def llm_call(state: dict):
    return {
        "messages": [
            model_with_tools.invoke(
                [SystemMessage(content="You are a helpful assistant tasked with performing arithmetic on a set of inputs.")]
                + state["messages"]
            )
        ],
        "llm_calls": state.get('llm_calls', 0) + 1
    }
```

### 4. 定义 tool node

遍历最后一条消息的 `tool_calls`, 逐个执行并把结果包成 `ToolMessage`。

```python
from langchain.messages import ToolMessage

def tool_node(state: dict):
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}
```

### 5. 定义结束逻辑 (conditional edge)

根据最后一条 LLM 消息是否含 tool_calls, 决定去 `tool_node` 还是 `END`。

```python
from typing import Literal
from langgraph.graph import END

def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"
    return END
```

### 6. 构建并编译 agent

```python
from langgraph.graph import StateGraph, START, END

agent_builder = StateGraph(MessagesState)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "llm_call")
agent = agent_builder.compile()

from langchain.messages import HumanMessage
messages = [HumanMessage(content="Add 3 and 4.")]
messages = agent.invoke({"messages": messages})
for m in messages["messages"]:
    m.pretty_print()
```

可选可视化:

```python
from IPython.display import Image, display
display(Image(agent.get_graph(xray=True).draw_mermaid_png()))
```

---

## 路径 B: Functional API

不用显式定义 nodes/edges, 而是在一个 `@entrypoint` 函数里写标准控制流 (循环、条件)。用 `@task` 标记可执行单元。

### 1. 定义 tools 与 model

同 Graph API 的 Step 1, 额外导入:

```python
from langgraph.graph import add_messages
from langchain.messages import SystemMessage, HumanMessage, ToolCall
from langchain_core.messages import BaseMessage
from langgraph.func import entrypoint, task
```

### 2. 定义 model task

```python
@task
def call_llm(messages: list[BaseMessage]):
    return model_with_tools.invoke(
        [SystemMessage(content="You are a helpful assistant tasked with performing arithmetic on a set of inputs.")]
        + messages
    )
```

### 3. 定义 tool task

```python
@task
def call_tool(tool_call: ToolCall):
    tool = tools_by_name[tool_call["name"]]
    return tool.invoke(tool_call)
```

### 4. 定义 agent (entrypoint)

```python
@entrypoint()
def agent(messages: list[BaseMessage]):
    model_response = call_llm(messages).result()

    while True:
        if not model_response.tool_calls:
            break
        tool_result_futures = [call_tool(tool_call) for tool_call in model_response.tool_calls]
        tool_results = [fut.result() for fut in tool_result_futures]
        messages = add_messages(messages, [model_response, *tool_results])
        model_response = call_llm(messages).result()

    messages = add_messages(messages, model_response)
    return messages

messages = [HumanMessage(content="Add 3 and 4.")]
stream = agent.stream_events(messages, version="v3")
for snapshot in stream.values:
    print(snapshot)
    print("\n")
```

---

## 心智模型

- **两种 API 是同一件事的两种表达**: Graph API = 显式的 nodes/edges 图; Functional API = 隐式的、写在函数里的控制流。
- **Agent = LLM 循环 + tool 执行**。核心就是: 调 LLM → 若它要调 tool 就执行 tool → 把结果塞回 messages → 再调 LLM, 直到不再调 tool。
- **state 是累加的容器**: `operator.add` (Graph) / `add_messages` (Functional) 让消息**追加**, 而 `llm_calls` 这类标量字段靠节点返回增量、由 reducer 累加。
- **`@task` 是可并行/可恢复的执行单元**, 在 entrypoint 内同步或异步调用, 用 `.result()` 取结果 (返回的是 future)。

## 易错点 / 混淆概念区分

- **`MessagesState` 重名**: quickstart 里自定义了一个 `MessagesState` TypedDict (含 `messages` + `llm_calls`), 与 `langgraph.graph` 内置的 `MessagesState` 不是同一个东西 (overview 用的是内置那个)。别混用。
- **tool_calls 的访问前提**: `state["messages"][-1]` 必须是带 `tool_calls` 属性的 AIMessage。直接访问前应确认类型, 否则可能 AttributeError。
- **tool node 必须回填 `tool_call_id`**: `ToolMessage(content=..., tool_call_id=tool_call["id"])` 的 `id` 不能漏, 否则协议不匹配。
- **Graph API 边方向**: `START → llm_call`; `llm_call` 条件边 → `tool_node` 或 `END`; `tool_node → llm_call` (形成循环)。别把 tool_node 回到 START。
- **`Annotated` reducer 的作用**: 不加 `operator.add` 时, 节点返回的 `messages` 会**覆盖**整个列表而不是追加, 历史丢失。
- **Functional API 的 `add_messages`**: 手动用它合并消息, 别用普通列表拼接 (`+`) 替代, 否则语义/id 处理不一致。
- **`temperature=0`**: 示例刻意设为 0, 让工具调用更确定。
- **`LANGSMITH_TRACING`**: 追踪需显式开启; 生产部署另见部署文档。
- **Graph API 文档里分步代码有重复 import**: 完整示例 (Accordion) 是权威合并版本, 分步片段可能缺少 import, 直接照抄分步片段会报未定义。
