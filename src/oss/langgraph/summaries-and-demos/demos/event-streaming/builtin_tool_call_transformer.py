"""event-streaming.mdx: 使用内置 ToolCallTransformer 暴露 stream.tool_calls。

在普通 StateGraph 上注册 ToolCallTransformer, 即可消费工具调用投影:
    for tool_call in stream.tool_calls:
        print(tool_call.tool_name, tool_call.input)

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python builtin_tool_call_transformer.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

from typing import TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolCallTransformer

model = init_chat_model("deepseek:deepseek-chat")


@tool
def get_weather(city: str) -> str:
    """Return the weather for a city."""
    return f"It is sunny in {city}."


model_with_tools = model.bind_tools([get_weather])


class State(TypedDict):
    messages: list


def call_model(state: State):
    return {"messages": state["messages"] + [model_with_tools.invoke(state["messages"])]}


def call_tools(state: State):
    last = state["messages"][-1]
    outputs = []
    for call in getattr(last, "tool_calls", []) or []:
        outputs.append(get_weather.invoke(call))
    return {"messages": state["messages"] + outputs}


graph = (
    StateGraph(State)
    .add_node("call_model", call_model)
    .add_node("call_tools", call_tools)
    .add_edge(START, "call_model")
    .add_edge("call_model", "call_tools")
    .add_edge("call_tools", END)
    .compile()
)


if __name__ == "__main__":
    stream = graph.stream_events(
        {"messages": [{"role": "user", "content": "What is the weather in Paris?"}]},
        version="v3",
        transformers=[ToolCallTransformer],
    )

    for tool_call in stream.tool_calls:
        print(tool_call.tool_name, tool_call.input)
