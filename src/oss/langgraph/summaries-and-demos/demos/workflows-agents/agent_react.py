"""Agents —— 经典 ReAct 循环, Graph API 版本。

llm_call 决定是否调用 tool; tool_node 执行 tool; 二者循环直到没有 tool_calls。
依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python agent_react.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

from typing import Literal

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph

llm = init_chat_model("deepseek:deepseek-chat", temperature=0)


# 定义 tools
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
tools_by_name = {t.name: t for t in tools}  # 注意: 元素是 tool 对象
llm_with_tools = llm.bind_tools(tools)


def llm_call(state: MessagesState):
    """LLM 决定是否调用 tool"""
    return {
        "messages": [
            llm_with_tools.invoke(
                [
                    SystemMessage(
                        content="You are a helpful assistant tasked with performing "
                        "arithmetic on a set of inputs."
                    )
                ]
                + state["messages"]
            )
        ]
    }


def tool_node(state: MessagesState):
    """执行 tool 调用"""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        t = tools_by_name[tool_call["name"]]
        observation = t.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}


def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    """有 tool 调用就继续循环, 否则结束"""
    if state["messages"][-1].tool_calls:
        return "tool_node"
    return END


agent_builder = StateGraph(MessagesState)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "llm_call")  # 循环

agent = agent_builder.compile()


if __name__ == "__main__":
    messages = [HumanMessage(content="Add 3 and 4.")]
    messages = agent.invoke({"messages": messages})["messages"]
    for m in messages:
        m.pretty_print()
