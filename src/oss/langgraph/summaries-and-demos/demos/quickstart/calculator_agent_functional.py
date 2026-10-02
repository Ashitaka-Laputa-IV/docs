"""LangGraph 计算器 agent —— Functional API 版本。

对应教程: src/oss/langgraph/quickstart.mdx (Tab: 使用 Functional API)

不显式定义 nodes/edges, 而是在单个 @entrypoint 函数里写标准控制流 (循环/条件):
  调 LLM -> 若它要调 tool 就执行 tool -> 把结果并回 messages -> 再调 LLM, 直到结束

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python calculator_agent_functional.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找仓库根目录的 .env

from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain.messages import (
    SystemMessage,
    HumanMessage,
    ToolCall,
)
from langchain_core.messages import BaseMessage

from langgraph.graph import add_messages
from langgraph.func import entrypoint, task


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
# 2. 定义 model task
# ---------------------------------------------------------------------------
@task
def call_llm(messages: list[BaseMessage]):
    """LLM decides whether to call a tool or not."""
    return model_with_tools.invoke(
        [
            SystemMessage(
                content=(
                    "You are a helpful assistant tasked with "
                    "performing arithmetic on a set of inputs."
                )
            )
        ]
        + messages
    )


# ---------------------------------------------------------------------------
# 3. 定义 tool task
# ---------------------------------------------------------------------------
@task
def call_tool(tool_call: ToolCall):
    """Performs the tool call."""
    tool_ = tools_by_name[tool_call["name"]]
    return tool_.invoke(tool_call)


# ---------------------------------------------------------------------------
# 4. 定义 agent (entrypoint)
# ---------------------------------------------------------------------------
@entrypoint()
def agent(messages: list[BaseMessage]):
    model_response = call_llm(messages).result()

    while True:
        if not model_response.tool_calls:
            break

        # Execute tools
        tool_result_futures = [
            call_tool(tool_call) for tool_call in model_response.tool_calls
        ]
        tool_results = [fut.result() for fut in tool_result_futures]
        messages = add_messages(messages, [model_response, *tool_results])
        model_response = call_llm(messages).result()

    messages = add_messages(messages, model_response)
    return messages


def main():
    messages = [HumanMessage(content="Add 3 and 4.")]
    result = agent.invoke(messages)
    for message in result:
        message.pretty_print()


if __name__ == "__main__":
    main()
