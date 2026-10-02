"""LangGraph 计算器 agent —— Graph API 版本。

对应教程: src/oss/langgraph/quickstart.mdx (Tab: 使用 Graph API)

把 agent 定义为由 nodes 与 edges 组成的 graph:
  START -> llm_call -> (should_continue) -> tool_node -> llm_call -> ... -> END

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python calculator_agent_graph.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找仓库根目录的 .env

from typing import Literal

from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain.messages import (
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from typing_extensions import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END


# ---------------------------------------------------------------------------
# 1. 定义 tools 与 model
# ---------------------------------------------------------------------------
model = init_chat_model("deepseek:deepseek-chat", temperature=0)


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


# ---------------------------------------------------------------------------
# 2. 定义 state
# ---------------------------------------------------------------------------
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


# ---------------------------------------------------------------------------
# 3. 定义 model node
# ---------------------------------------------------------------------------
def llm_call(state: MessagesState):
    """LLM decides whether to call a tool or not."""
    return {
        "messages": [
            model_with_tools.invoke(
                [
                    SystemMessage(
                        content=(
                            "You are a helpful assistant tasked with "
                            "performing arithmetic on a set of inputs."
                        )
                    )
                ]
                + state["messages"]
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# ---------------------------------------------------------------------------
# 4. 定义 tool node
# ---------------------------------------------------------------------------
def tool_node(state: MessagesState):
    """Performs the tool call."""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool_ = tools_by_name[tool_call["name"]]
        observation = tool_.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}


# ---------------------------------------------------------------------------
# 5. 定义结束逻辑 (conditional edge)
# ---------------------------------------------------------------------------
def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    """Decide if we should continue the loop or stop."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"
    return END


# ---------------------------------------------------------------------------
# 6. 构建并编译 agent
# ---------------------------------------------------------------------------
def build_agent():
    agent_builder = StateGraph(MessagesState)
    agent_builder.add_node("llm_call", llm_call)
    agent_builder.add_node("tool_node", tool_node)
    agent_builder.add_edge(START, "llm_call")
    agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
    agent_builder.add_edge("tool_node", "llm_call")
    return agent_builder.compile()


def main():
    agent = build_agent()
    result = agent.invoke({"messages": [HumanMessage(content="Add 3 and 4.")]})
    for message in result["messages"]:
        message.pretty_print()
    print(f"\nLLM 调用次数: {result['llm_calls']}")


if __name__ == "__main__":
    main()
